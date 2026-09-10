"""Recalcula con la Riot API los enlaces que la migración no pudo atribuir.

Cada fila de legacy_unresolved_links es una partida que un jugador tenía en un
snapshot o en su historial, pero cuyas estadísticas guardadas eran de otro
jugador (bug P1). Aquí se descargan las suyas y se vuelve a enlazar.

    python scripts/repair_legacy_links.py [límite]
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import select

import app.db.models  # noqa: F401
from app.crud.participants import add_history_entries, link_snapshot, upsert_participants
from app.db.models.legacy_link import LegacyUnresolvedLink
from app.db.models.player import Player
from app.db.session import SessionLocal
from app.service.riot import create_secure_session, riot_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def repair(limit: int) -> tuple[int, int]:
    db = SessionLocal()
    try:
        links = list(
            db.scalars(
                select(LegacyUnresolvedLink)
                .where(LegacyUnresolvedLink.resolved_at.is_(None))
                .order_by(LegacyUnresolvedLink.id)
                .limit(limit)
            )
        )
        repaired = 0
        async with create_secure_session() as session:
            for link in links:
                player = db.get(Player, link.player_id)
                if player is None:
                    continue
                stats = await riot_client(player.region).fetch_participant(
                    session, link.match_id, player.puuid
                )
                if stats is None:
                    logger.warning("No se pudo recalcular %s para %s", link.match_id, player.game_name)
                    continue

                participant_id = upsert_participants(db, [stats])[(stats.match_id, stats.puuid)]
                if link.kind == "snapshot" and link.snapshot_id is not None:
                    link_snapshot(db, link.snapshot_id, [participant_id])
                else:
                    add_history_entries(db, player.id, [participant_id])
                link.resolved_at = datetime.now(timezone.utc)
                db.commit()
                repaired += 1
        return repaired, len(links)
    finally:
        db.close()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    repaired, total = asyncio.run(repair(limit))
    logger.info("Reparados %d de %d enlaces pendientes.", repaired, total)
