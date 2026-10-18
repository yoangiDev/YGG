"""Sample of matches from the best players of each role, to study what makes you win.

For each player in the roster it downloads this season's SoloQ matches, from the most
recent backwards, until it gathers `--games` in THEIR role: matches in another role are looked at and
don't count. Each match is stored whole (with the compacted timeline) in a
.jsonl.gz, and one timeline serves everyone in the roster who played that
match in their role.

It is resumable: what is stored isn't requested again. If the Riot key expires (the
development one lasts 24 h), the script stops and it is enough to relaunch it with the new one.

    python scripts/ladder_dataset.py ../../research/ladder/roster.json ../../research/ladder/data
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from ygg_core.domain.roles import role_from_position  # noqa: E402
from ygg_core.riot.client import RiotAPIClient  # noqa: E402
from ygg_core.riot.http import create_secure_session  # noqa: E402
from ygg_core.riot.match_record import FRAME_FIELDS, KEEP_EVENTS, match_record  # noqa: E402, F401
from ygg_core.riot.parsers import REMAKE_MAX_SECONDS  # noqa: E402
from ygg_core.riot.rate_limiter import RiotRateLimiter  # noqa: E402

from app.core.config import settings  # noqa: E402

JsonDict = dict[str, Any]

# Development key: 20/s and 100 per 2 min. A hair below to avoid eating 429s.
PER_SECOND, PER_TWO_MINUTES = 18, 95
SOLOQ = 420
IDS_PAGE = 100



class KeyExpired(Exception):
    pass


async def get(client: RiotAPIClient, session: Any, url: str) -> Any:
    """GET to Riot. None if it doesn't exist (404). KeyExpired on 401/403. Retries the rest."""
    for attempt in range(6):
        status, data = await client._riot_get(session, url)
        if status == 200:
            return data
        if status in (401, 403):
            raise KeyExpired(f"HTTP {status}")
        if status == 404:
            return None
        await asyncio.sleep(5 * (attempt + 1))  # persistent 429, 5xx or network error
    raise RuntimeError(f"Riot is not responding: {url}")


# ── Store ─────────────────────────────────────────────────────────────────────


class Store:
    """matches.jsonl.gz: one match per line, each its own gzip member (a cut doesn't break the previous ones)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.index: dict[str, JsonDict] = {}  # match_id → {roles: {puuid: rol}, remake, timeline}
        if not path.exists():
            return
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line in fh:
                    self._index(json.loads(line))
        except (EOFError, OSError, json.JSONDecodeError):
            print("  (last line cut off: ignored and it will be requested again)")

    def _index(self, record: JsonDict) -> None:
        self.index[record["match_id"]] = {
            "roles": {p["puuid"]: p["role"] for p in record.get("participants", [])},
            "remake": record.get("remake", False),
            "timeline": record.get("frames") is not None,
            "missing": record.get("missing", False),
            "version": record.get("game_version") or "",
        }

    def add(self, record: JsonDict) -> None:
        with gzip.open(self.path, "at", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._index(record)


# ── Collection ─────────────────────────────────────────────────────────────────


class Collector:
    def __init__(self, client: RiotAPIClient, session: Any, store: Store, roster_roles: dict[str, str]) -> None:
        self.client, self.session, self.store = client, session, store
        self.roster_roles = roster_roles  # puuid → declared role
        self.calls = 0

    async def _get(self, url: str) -> Any:
        self.calls += 1
        return await get(self.client, self.session, url)

    def _needs_timeline(self, roles: dict[str, str]) -> bool:
        return any(self.roster_roles.get(puuid) == role for puuid, role in roles.items())

    async def match(self, match_id: str) -> JsonDict | None:
        """The match's index, downloading it if missing (with a timeline if someone in the roster played its role)."""
        known = self.store.index.get(match_id)
        if known and (known["timeline"] or known["missing"] or known["remake"] or not self._needs_timeline(known["roles"])):
            return known
        base = f"{self.client.base_routing}/lol/match/v5/matches/{match_id}"
        match = await self._get(base)
        if match is None:
            self.store.add({"match_id": match_id, "missing": True})
            return self.store.index[match_id]
        roles = {p["puuid"]: role_from_position(p.get("teamPosition")) for p in match["info"]["participants"]}
        remake = match["info"].get("gameDuration", 0) < REMAKE_MAX_SECONDS
        timeline = await self._get(f"{base}/timeline") if not remake and self._needs_timeline(roles) else None
        self.store.add(match_record(match, timeline))
        return self.store.index[match_id]

    async def player(self, puuid: str, role: str, target: int, since: int) -> tuple[list[str], int, str]:
        """The `target` most recent matches of the season in their role. Returns (ids, looked at, status)."""
        in_role: list[str] = []
        scanned = start = 0
        while len(in_role) < target:
            url = (
                f"{self.client.base_routing}/lol/match/v5/matches/by-puuid/{puuid}/ids"
                f"?queue={SOLOQ}&start={start}&count={IDS_PAGE}&startTime={since}"
            )
            ids = await self._get(url) or []
            if not ids:
                return in_role, scanned, "no more matches this season"
            for match_id in ids:
                scanned += 1
                try:
                    known = await self.match(match_id)
                except RuntimeError as exc:
                    print(f"\n    skipped {match_id}: {exc}")
                    continue
                if known and not known["remake"] and not known["missing"] and known["roles"].get(puuid) == role:
                    in_role.append(match_id)
                    print(f"    {len(in_role)}/{target} in role · {scanned} looked at · {self.calls} calls", end="\r")
                    if len(in_role) >= target:
                        break
            start += len(ids)
        return in_role, scanned, "full"


async def resolve(collector: Collector, riot_id: str) -> tuple[str | None, str | None]:
    name, _, tag = riot_id.partition("#")
    account = await collector._get(
        f"{collector.client.base_routing}/riot/account/v1/accounts/by-riot-id/"
        f"{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}"
    )
    if not account:
        return None, None
    rank = await collector.client.fetch_rank(collector.session, account["puuid"])
    return account["puuid"], f"{rank.tier} {rank.rank} {rank.lp} LP" if rank else None


async def run(roster_path: Path, out: Path, target: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    roster: dict[str, list[str]] = json.loads(roster_path.read_text(encoding="utf-8"))
    players_path = out / "players.json"
    players: dict[str, JsonDict] = json.loads(players_path.read_text(encoding="utf-8")) if players_path.exists() else {}
    store = Store(out / "matches.jsonl.gz")
    print(f"{len(store.index)} matches already stored")

    client = RiotAPIClient(settings.riot_api_key, "euw", limiter=RiotRateLimiter(PER_SECOND, PER_TWO_MINUTES), max_connections=4)
    since = int(settings.season_start.timestamp())
    async with create_secure_session() as session:
        collector = Collector(client, session, store, {})
        try:
            # All the puuids first: we need to know who is in the roster to decide whether a match carries a timeline.
            for role, riot_ids in roster.items():
                for riot_id in riot_ids:
                    entry = players.setdefault(riot_id, {"riot_id": riot_id, "role": role})
                    if not entry.get("puuid"):
                        entry["puuid"], entry["rank"] = await resolve(collector, riot_id)
                        print(f"  {role:<8} {riot_id:<28} {entry['rank'] or ('NOT FOUND' if not entry['puuid'] else 'unranked')}")
                    if entry["puuid"]:
                        collector.roster_roles[entry["puuid"]] = role
            players_path.write_text(json.dumps(players, indent=1, ensure_ascii=False), encoding="utf-8")

            for entry in players.values():
                if not entry.get("puuid") or entry.get("status") == "full":
                    continue
                started = time.monotonic()
                print(f"\n{entry['role']} · {entry['riot_id']} ({entry['rank']})")
                ids, scanned, status = await collector.player(entry["puuid"], entry["role"], target, since)
                entry.update(games=ids, in_role=len(ids), scanned=scanned, status=status)
                players_path.write_text(json.dumps(players, indent=1, ensure_ascii=False), encoding="utf-8")
                print(f"\n    {status}: {len(ids)} in role out of {scanned} ({(time.monotonic() - started) / 60:.1f} min)")
        except KeyExpired as exc:
            players_path.write_text(json.dumps(players, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"\nThe Riot key has expired ({exc}). Put the new one in apps/api/.env and relaunch: it carries on where it left off.")
            return 2

    done = sum(1 for p in players.values() if p.get("status") == "full")
    print(f"\nDone: {done}/{len(players)} players complete, {len(store.index)} matches stored.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roster", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--games", type=int, default=100, help="matches in their role per player")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.roster, args.out, args.games)))


if __name__ == "__main__":
    main()
