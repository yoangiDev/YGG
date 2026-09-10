"""Re-fetch timelines for S26 matches missing Role Quest data."""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select
from ygg_core.timeline.quests import is_s26_match

import app.db.models  # noqa: F401
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.db.session import SessionLocal
from app.service.dashboard_cache import invalidate_dashboards_for_participants
from app.service.riot import copy_timeline_fields, create_secure_session, riot_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _backfill_rows(rows: list[tuple[MatchParticipant, Player]]) -> int:
    updated = 0
    async with create_secure_session() as session:
        for participant, player in rows:
            client = riot_client(player.region)
            try:
                stats = await client.fetch_participant(session, participant.match_id, player.puuid)
            except Exception as exc:
                logger.warning("Failed %s: %s", participant.match_id, exc)
                continue
            if stats is None:
                logger.warning("Skipping %s — fetch failed", participant.match_id)
                continue
            copy_timeline_fields(participant, stats)
            updated += 1
    return updated


async def backfill(limit: int = 50, *, force: bool = False) -> None:
    async with SessionLocal() as db:
        query = (
            select(MatchParticipant, Player)
            .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
            .join(Snapshot, Snapshot.id == SnapshotParticipant.snapshot_id)
            .join(Player, Player.id == Snapshot.player_id)
            .order_by(MatchParticipant.creation_time.desc())
        )
        if not force:
            query = query.where(MatchParticipant.quest_completion_time.is_(None))

        rows: list[tuple[MatchParticipant, Player]] = []
        seen: set[int] = set()
        for participant, player in (await db.execute(query)).all():
            if participant.id in seen or not is_s26_match(participant.creation_time):
                continue
            seen.add(participant.id)
            rows.append((participant, player))
            if len(rows) >= limit:
                break

        if not rows:
            logger.info("No S26 matches need quest backfill.")
            return

        logger.info("Backfilling quest data for %d matches...", len(rows))
        updated = await _backfill_rows(rows)
        await db.commit()
        await invalidate_dashboards_for_participants(db, (participant.id for participant, _ in rows))
        logger.info("Updated quest data for %d/%d matches.", updated, len(rows))


if __name__ == "__main__":
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    n = int(args[0]) if args else 50
    asyncio.run(backfill(n, force=force))
