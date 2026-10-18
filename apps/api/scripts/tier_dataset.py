"""Sample of SoloQ matches from each league, from Iron to Grandmaster, for the WP model.

Players are drawn at random from Riot's ladders (league-v4), spread
among each league's divisions: the best of a league do not represent it. For
each one their most recent matches of the season are downloaded, with timeline, until
`--target` per league is gathered. They are not chosen by role: each match brings two players
of each role. It fills in rounds (a third of each league, then two thirds...),
so a cut leaves all leagues with data.

Resumable like ladder_dataset.py: what is stored isn't requested again and, if the Riot key
expires, it stops and it is enough to relaunch it with the new one.

    python scripts/tier_dataset.py ../../research/ladder/data/tiers

With `--patch` and `--since` it also serves to choose the replays of a decoder
harvest (lol-replay-decoder/descargar.py reads the sample.json it leaves):

    python scripts/tier_dataset.py ../../research/ladder/data/harvest-16.19 --target 143 \
        --tiers GOLD PLATINUM EMERALD DIAMOND MASTER GRANDMASTER CHALLENGER \
        --since 2026-09-23 --patch 16.19 --per-player 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ladder_dataset import (  # noqa: E402
    PER_SECOND,
    PER_TWO_MINUTES,
    SOLOQ,
    KeyExpired,
    Store,
    get,
    match_record,
)
from ygg_core.riot.client import RiotAPIClient  # noqa: E402
from ygg_core.riot.http import create_secure_session  # noqa: E402
from ygg_core.riot.parsers import REMAKE_MAX_SECONDS  # noqa: E402
from ygg_core.riot.rate_limiter import RiotRateLimiter  # noqa: E402

from app.core.config import settings  # noqa: E402

TIERS = ("IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER")
APEX = ("MASTER", "GRANDMASTER", "CHALLENGER")
DIVISIONS = ("I", "II", "III", "IV")
GAMES_PER_PLAYER = 25  # their most recent: with more players and fewer matches each, the sample is more varied
ROUNDS = 3


async def sample_players(client: RiotAPIClient, session: Any, tier: str, page: int = 1) -> list[str]:
    """Puuids from a page of the league at random, alternating divisions (Master, GM and Challenger have none, nor more pages)."""
    queue = "RANKED_SOLO_5x5"
    if tier in APEX and page > 1:
        return []
    if tier in APEX:
        league = await get(client, session, f"{client.base_platform}/lol/league/v4/{tier.lower()}leagues/by-queue/{queue}")
        pools = [[e["puuid"] for e in (league or {}).get("entries", []) if e.get("puuid")]]
    else:
        pools = [
            [e["puuid"] for e in await get(client, session, f"{client.base_platform}/lol/league/v4/entries/{queue}/{tier}/{d}?page={page}") or []
             if e.get("puuid")]
            for d in DIVISIONS
        ]
    rng = random.Random(f"{tier}{page}" if page > 1 else tier)  # the same sample on relaunch
    for pool in pools:
        rng.shuffle(pool)
    # One from each division per turn: I, II, III, IV, I, II...
    return [pool[i] for i in range(max(map(len, pools), default=0)) for pool in pools if i < len(pool)]


class TierCollector:
    def __init__(self, client: RiotAPIClient, session: Any, store: Store, state: dict[str, Any], since: int,
                 patch: str = "", per_player: int = GAMES_PER_PLAYER) -> None:
        self.client, self.session, self.store, self.state, self.since = client, session, store, state, since
        self.patch, self.per_player = patch, per_player
        self.calls = 0

    async def _get(self, url: str) -> Any:
        self.calls += 1
        return await get(self.client, self.session, url)

    def games(self, tier: str) -> int:
        return len(self.state[tier]["games"])

    async def match(self, match_id: str, tier: str) -> bool:
        """Downloads the match with a timeline if missing. True if usable: complete, no remake, from the patch and from nobody of another league."""
        if match_id not in self.store.index:
            base = f"{self.client.base_routing}/lol/match/v5/matches/{match_id}"
            match = await self._get(base)
            if match is None:
                self.store.add({"match_id": match_id, "missing": True})
            else:
                remake = match["info"].get("gameDuration", 0) < REMAKE_MAX_SECONDS
                timeline = None if remake else await self._get(f"{base}/timeline")
                self.store.add({**match_record(match, timeline), "tier": tier})
        known = self.store.index[match_id]
        taken = any(match_id in s["games"] for s in self.state.values())
        in_patch = known["version"].startswith(self.patch)
        return known["timeline"] and not known["remake"] and not known["missing"] and in_patch and not taken

    async def fill(self, tier: str, goal: int) -> None:
        entry = self.state[tier]
        if not entry.get("players"):
            entry["players"] = await sample_players(self.client, self.session, tier)
            entry.setdefault("next", 0)
            print(f"  {len(entry['players'])} players in the {tier} sample")
        while self.games(tier) < goal:
            if entry["next"] >= len(entry["players"]):
                # Sample exhausted: the next page of each division (many haven't played since --since).
                entry["page"] = entry.get("page", 1) + 1
                seen = set(entry["players"])
                more = [p for p in await sample_players(self.client, self.session, tier, entry["page"]) if p not in seen]
                if not more:
                    break
                entry["players"] += more
                print(f"\n  +{len(more)} players from page {entry['page']} of {tier}")
            puuid = entry["players"][entry["next"]]
            ids = await self._get(
                f"{self.client.base_routing}/lol/match/v5/matches/by-puuid/{puuid}/ids"
                f"?queue={SOLOQ}&start=0&count={self.per_player}&startTime={self.since}"
            ) or []
            platform = self.client.base_platform.split("//")[1].split(".")[0].upper()
            for match_id in ids:
                if self.games(tier) >= goal:
                    break
                if not match_id.startswith(f"{platform}_"):  # match-v5 europe mixes EUW, EUNE, TR and RU
                    continue
                try:
                    if await self.match(match_id, tier):
                        entry["games"].append(match_id)
                except RuntimeError as exc:
                    print(f"\n    skipped {match_id}: {exc}")
                print(f"  {tier:<11} {self.games(tier)}/{goal} · player {entry['next'] + 1} · {self.calls} calls", end="\r")
            entry["next"] += 1  # also if it was cut halfway: its stored matches aren't requested again
        print()


async def run(out: Path, target: int, tiers: list[str], since: datetime, patch: str, per_player: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "sample.json"
    state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    for tier in tiers:
        state.setdefault(tier, {"games": []})
    store = Store(out / "matches.jsonl.gz")
    print(f"{len(store.index)} matches already stored")

    client = RiotAPIClient(settings.riot_api_key, "euw", limiter=RiotRateLimiter(PER_SECOND, PER_TWO_MINUTES), max_connections=4)
    async with create_secure_session() as session:
        collector = TierCollector(client, session, store, state, int(since.timestamp()), patch, per_player)
        try:
            for round_ in range(1, ROUNDS + 1):
                goal = target * round_ // ROUNDS
                print(f"\nRound {round_}: {goal} matches per league")
                for tier in tiers:
                    await collector.fill(tier, goal)
                    state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
        except KeyExpired as exc:
            state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
            print(f"\nThe Riot key has expired ({exc}). Put the new one in apps/api/.env and relaunch: it carries on where it left off.")
            return 2

    print("\nDone:", ", ".join(f"{tier} {len(state[tier]['games'])}" for tier in tiers))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--target", type=int, default=1500, help="matches with timeline per league")
    parser.add_argument("--tiers", nargs="+", choices=TIERS, default=list(TIERS[:-1]))
    parser.add_argument("--since", type=lambda d: datetime.fromisoformat(d).replace(tzinfo=UTC),
                        default=settings.season_start, help="only matches since this day (YYYY-MM-DD)")
    parser.add_argument("--patch", default="", help="gameVersion prefix, e.g. 16.19")
    parser.add_argument("--per-player", type=int, default=GAMES_PER_PLAYER)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.out, args.target, args.tiers, args.since, args.patch, args.per_player)))


if __name__ == "__main__":
    main()
