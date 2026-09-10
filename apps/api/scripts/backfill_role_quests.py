"""Re-fetch timelines for S26 matches missing Role Quest data."""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select
from ygg_core.timeline.quests import is_s26_match

import app.db.models  # noqa: F401
from app.db.models.match import Match
from app.db.models.match_snapshot import MatchSnapshot
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.session import SessionLocal
from app.service.riot import copy_timeline_fields, create_secure_session, riot_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _backfill_rows(rows: list[tuple[Match, Player]]) -> int:
    updated = 0
    async with create_secure_session() as session:
        for match, player in rows:
            client = riot_client(player.region)
            try:
                stats = await client.fetch_participant(session, match.match_id, player.puuid)
            except Exception as exc:
                logger.warning("Failed %s: %s", match.match_id, exc)
                continue
            if stats is None:
                logger.warning("Skipping %s — fetch failed", match.match_id)
                continue
            copy_timeline_fields(match, stats)
            updated += 1
    return updated


def backfill(limit: int = 50, *, force: bool = False) -> None:
    db = SessionLocal()
    try:
        query = (
            select(Match, Player)
            .join(MatchSnapshot, MatchSnapshot.match_id == Match.id)
            .join(Snapshot, Snapshot.id == MatchSnapshot.snapshot_id)
            .join(Player, Player.id == Snapshot.player_id)
            .order_by(Match.creation_time.desc())
        )
        if not force:
            query = query.where(Match.quest_completion_time.is_(None))

        rows = [
            (m, p)
            for m, p in db.execute(query).unique().all()
            if is_s26_match(m.creation_time)
        ][:limit]

        if not rows:
            logger.info("No S26 matches need quest backfill.")
            return

        logger.info("Backfilling quest data for %d matches...", len(rows))
        updated = asyncio.run(_backfill_rows(rows))
        db.commit()
        logger.info("Updated quest data for %d/%d matches.", updated, len(rows))
    finally:
        db.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    n = int(args[0]) if args else 50
    backfill(n, force=force)
