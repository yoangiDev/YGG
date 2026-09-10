"""Re-fetch timelines for S26 matches missing Role Quest data."""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select

from app.db.base import Base  # noqa: F401
from app.db.models.job import Job  # noqa: F401
from app.db.models.match import Match
from app.db.models.match_snapshot import MatchSnapshot
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.user import User  # noqa: F401
from app.db.session import SessionLocal
from app.service.http_client import create_secure_session
from app.service.role_quest_parser import is_s26_match
from app.service.riot_client import RiotAPIClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _backfill_rows(rows: list[tuple[Match, Player]]) -> int:
    updated = 0
    async with create_secure_session() as session:
        for match, player in rows:
            client = RiotAPIClient(region=player.region)
            timeline = await client._fetch_timeline(session, match.match_id)
            match_data = await client._fetch_single_match(session, match.match_id)
            if not timeline or not match_data:
                logger.warning("Skipping %s — fetch failed", match.match_id)
                continue
            try:
                client._apply_timeline_to_match(
                    match, match_data, timeline, player.puuid
                )
                updated += 1
            except Exception as exc:
                logger.warning("Failed %s: %s", match.match_id, exc)
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
