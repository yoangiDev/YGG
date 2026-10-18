import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.riot.routing import platform_from_region

from app.core.config import settings
from app.db.models.rank_cutoff import RankCutoff
from app.service.riot import create_secure_session, riot_client

logger = logging.getLogger(__name__)

__all__ = ["get_rank_cutoffs", "is_stale", "platform_from_region", "upsert_cutoffs"]

_CACHE_TTL = timedelta(hours=4)

# Position in the combined Challenger + Grandmaster + Master ladder whose LP marks each cutoff.
# Without the Master list it comes out wrong: there are masters with more LP than the grandmasters who are about to drop.
CHALLENGER_CUTOFF_RANK = 300
GRANDMASTER_CUTOFF_RANK = 1000


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

    combined = sorted(by_puuid.values(), key=lambda entry: entry["leaguePoints"], reverse=True)
    index = min(rank_position - 1, len(combined) - 1)
    return int(combined[index]["leaguePoints"])


async def fetch_cutoffs_from_riot(region: str) -> tuple[int, int]:
    # It goes through the core's global rate limiter, like the rest of the Riot calls.
    client = riot_client(platform_from_region(region))

    async with create_secure_session() as session:
        combined = [
            entry
            for league in ("challengerleagues", "grandmasterleagues", "masterleagues")
            for entry in await client.fetch_league_entries(session, league)
        ]

    ch_lp = _cutoff_lp(combined, CHALLENGER_CUTOFF_RANK)
    gm_lp = _cutoff_lp(combined, GRANDMASTER_CUTOFF_RANK)
    if gm_lp is None or ch_lp is None:
        raise ConnectionError(f"Could not fetch rank cutoffs for region '{region}'.")
    return gm_lp, ch_lp


def is_stale(record: RankCutoff) -> bool:
    fetched_at = record.fetched_at
    if fetched_at.tzinfo is None:  # rows from before the migration to timestamptz
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - fetched_at > _CACHE_TTL


async def upsert_cutoffs(
    db: AsyncSession, platform: str, grandmaster_cutoff_lp: int, challenger_cutoff_lp: int
) -> RankCutoff:
    record = await db.get(RankCutoff, platform)
    now = datetime.now(timezone.utc)
    if record is None:
        record = RankCutoff(platform=platform, fetched_at=now)
        db.add(record)
    record.grandmaster_cutoff_lp = grandmaster_cutoff_lp
    record.challenger_cutoff_lp = challenger_cutoff_lp
    record.fetched_at = now
    await db.commit()
    await db.refresh(record)
    return record


async def get_rank_cutoffs(db: AsyncSession, region: str, *, refresh: bool = False) -> RankCutoff:
    platform = platform_from_region(region)
    cached = await db.get(RankCutoff, platform)
    # In the demo there is no Riot key: the stored cutoffs are valid even if they have expired.
    if cached is not None and not refresh and (settings.demo_mode or not is_stale(cached)):
        return cached

    gm_lp, ch_lp = await fetch_cutoffs_from_riot(region)
    return await upsert_cutoffs(db, platform, gm_lp, ch_lp)
