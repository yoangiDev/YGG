import logging
from datetime import datetime, timedelta

import aiohttp
from sqlalchemy.orm import Session

from app.db.models.rank_cutoff import RankCutoff
from app.service.http_client import create_secure_session
from app.service.riot_client import REGION_ROUTING, RiotAPIClient

logger = logging.getLogger(__name__)

_QUEUE = "RANKED_SOLO_5x5"
_CACHE_TTL = timedelta(hours=4)

# Overall ladder: Challenger ranks 1-300, Grandmaster ranks 301-1000.
CHALLENGER_CUTOFF_RANK = 300
GRANDMASTER_CUTOFF_RANK = 1000


def platform_from_region(region: str) -> str:
    _, platform = REGION_ROUTING.get(region.lower(), ("europe", "euw1"))
    return platform


async def _fetch_league_entries(
    session: aiohttp.ClientSession,
    client: RiotAPIClient,
    league_path: str,
) -> list[dict]:
    url = f"{client.base_platform}/lol/league/v4/{league_path}/by-queue/{_QUEUE}"
    async with session.get(url, headers=client.headers) as response:
        if response.status == 429:
            retry_after = float(response.headers.get("Retry-After", 2))
            logger.warning("Rate limit fetching %s. Retry in %ss", league_path, retry_after)
            raise ConnectionError("Riot API rate limit exceeded.")
        if response.status != 200:
            logger.error("Riot API error (%s) for %s", response.status, league_path)
            return []

        payload = await response.json()
        return payload.get("entries") or []


def _cutoff_lp(entries: list[dict], rank_position: int) -> int | None:
    if not entries:
        return None

    by_puuid: dict[str, dict] = {}
    for entry in entries:
        puuid = entry.get("puuid") or entry.get("summonerId")
        if puuid is None:
            continue
        existing = by_puuid.get(puuid)
        if existing is None or entry["leaguePoints"] > existing["leaguePoints"]:
            by_puuid[puuid] = entry

    combined = sorted(
        by_puuid.values(),
        key=lambda entry: entry["leaguePoints"],
        reverse=True,
    )
    index = min(rank_position - 1, len(combined) - 1)
    return int(combined[index]["leaguePoints"])


async def fetch_cutoffs_from_riot(region: str) -> tuple[int, int]:
    platform = platform_from_region(region)
    client = RiotAPIClient(platform)

    async with create_secure_session() as session:
        challenger_entries = await _fetch_league_entries(
            session, client, "challengerleagues"
        )
        grandmaster_entries = await _fetch_league_entries(
            session, client, "grandmasterleagues"
        )

    combined = challenger_entries + grandmaster_entries
    if not combined:
        raise ConnectionError(
            f"Could not fetch rank cutoffs for region '{region}'."
        )

    ch_lp = _cutoff_lp(combined, CHALLENGER_CUTOFF_RANK)
    gm_lp = _cutoff_lp(combined, GRANDMASTER_CUTOFF_RANK)

    if gm_lp is None or ch_lp is None:
        raise ConnectionError(
            f"Could not fetch rank cutoffs for region '{region}'."
        )

    return gm_lp, ch_lp


def get_cached_cutoffs(db: Session, platform: str) -> RankCutoff | None:
    return db.query(RankCutoff).filter(RankCutoff.platform == platform).first()


def is_stale(record: RankCutoff) -> bool:
    return datetime.utcnow() - record.fetched_at > _CACHE_TTL


def upsert_cutoffs(
    db: Session,
    platform: str,
    grandmaster_cutoff_lp: int,
    challenger_cutoff_lp: int,
) -> RankCutoff:
    record = get_cached_cutoffs(db, platform)
    now = datetime.utcnow()
    if record is None:
        record = RankCutoff(
            platform=platform,
            grandmaster_cutoff_lp=grandmaster_cutoff_lp,
            challenger_cutoff_lp=challenger_cutoff_lp,
            fetched_at=now,
        )
        db.add(record)
    else:
        record.grandmaster_cutoff_lp = grandmaster_cutoff_lp
        record.challenger_cutoff_lp = challenger_cutoff_lp
        record.fetched_at = now
    db.commit()
    db.refresh(record)
    return record


async def get_rank_cutoffs(
    db: Session,
    region: str,
    *,
    refresh: bool = False,
) -> RankCutoff:
    platform = platform_from_region(region)
    cached = get_cached_cutoffs(db, platform)

    if cached is not None and not refresh and not is_stale(cached):
        return cached

    gm_lp, ch_lp = await fetch_cutoffs_from_riot(region)
    return upsert_cutoffs(db, platform, gm_lp, ch_lp)
