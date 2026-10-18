"""Downloads again the matches stored with an earlier version of the timeline computation.

New analyses already do this by themselves with the matches they reuse; this brings
all the ones already stored up to date in one go.
"""

import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import TIMELINE_VERSION
from ygg_core.riot.client import RiotAPIClient
from ygg_core.riot.routing import region_from_match_id

from app.db.models.participant import MatchParticipant
from app.service.dashboard_cache import invalidate_dashboards_for_participants
from app.service.demo_seed import DEMO_MATCH_PREFIX
from app.service.riot import copy_timeline_fields, create_secure_session, riot_client

logger = logging.getLogger(__name__)

COMMIT_EVERY = 20
# If Riot stops responding (expired key, outage) there is no point in carrying on requesting.
MAX_CONSECUTIVE_FAILURES = 3

ProgressCallback = Callable[[int, int, int], None]  # (processed, total, updated)


async def outdated_participants(
    db: AsyncSession, *, puuid: str | None = None, limit: int | None = None
) -> list[MatchParticipant]:
    stmt = (
        select(MatchParticipant)
        .where(
            MatchParticipant.timeline_enriched.is_(True),
            MatchParticipant.timeline_version < TIMELINE_VERSION,
            # The demo ones aren't in Riot: they are regenerated with the seed.
            ~MatchParticipant.match_id.startswith(DEMO_MATCH_PREFIX, autoescape=True),
        )
        .order_by(MatchParticipant.creation_time.desc())
    )
    if puuid is not None:
        stmt = stmt.where(MatchParticipant.puuid == puuid)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(await db.scalars(stmt))


async def refresh_outdated_timelines(
    db: AsyncSession,
    *,
    puuid: str | None = None,
    limit: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> int:
    """Recomputes with the current timeline the rows of earlier versions. Returns how many were updated."""
    rows = await outdated_participants(db, puuid=puuid, limit=limit)
    clients: dict[str, RiotAPIClient] = {}
    updated: list[int] = []
    failures = 0

    async with create_secure_session() as session:
        for index, row in enumerate(rows, start=1):
            region = region_from_match_id(row.match_id)
            client = clients.setdefault(region, riot_client(region))
            try:
                stats = await client.fetch_participant(session, row.match_id, row.puuid)
            except Exception as exc:
                logger.warning("Timeline refresh of %s failed: %s", row.match_id, exc)
                stats = None

            if stats is None:
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.warning("Timeline refresh stopped: Riot did not return %d matches in a row.", failures)
                    break
            else:
                failures = 0
                copy_timeline_fields(row, stats)
                updated.append(row.id)

            if index % COMMIT_EVERY == 0:
                await db.commit()
            if on_progress:
                on_progress(index, len(rows), len(updated))

    await db.commit()
    await invalidate_dashboards_for_participants(db, updated)
    logger.info("Timeline refresh: %d of %d outdated matches updated.", len(updated), len(rows))
    return len(updated)
