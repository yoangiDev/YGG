"""Historial de partidas de un jugador, por páginas y en el orden de Riot.

Riot solo pagina ids. Las partidas que ya están guardadas para ESTE jugador no se
vuelven a descargar, y cada página se añade al historial sin borrar las
anteriores: así «cargar más» acumula y la base de datos hace de caché.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.participants import add_history_entries, known_participants, upsert_participants
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.player_history import PlayerHistoryEntry
from app.service.dashboard_cache import invalidate_dashboards_for_participants
from app.service.riot import create_secure_session, player_ref, riot_client

logger = logging.getLogger(__name__)

_HISTORY_TTL = timedelta(hours=1)
DEFAULT_HISTORY_LIMIT = 100


def is_history_fresh(player: Player) -> bool:
    """La primera página se sincronizó con Riot hace menos de una hora."""
    if not player.match_history_cached_at:
        return False
    return datetime.now(timezone.utc) - player.match_history_cached_at < _HISTORY_TTL


def _newest_first():
    return MatchParticipant.creation_time.desc(), MatchParticipant.id.desc()


async def get_history_from_cache(
    db: AsyncSession, player_id: int, limit: int = DEFAULT_HISTORY_LIMIT, offset: int = 0
) -> list[MatchParticipant]:
    stmt = (
        select(MatchParticipant)
        .join(PlayerHistoryEntry, PlayerHistoryEntry.match_participant_id == MatchParticipant.id)
        .where(PlayerHistoryEntry.player_id == player_id)
        .order_by(*_newest_first())
        .offset(offset)
        .limit(limit)
    )
    return list(await db.scalars(stmt))


async def fetch_history_page(
    db: AsyncSession, player: Player, *, offset: int, limit: int
) -> list[MatchParticipant]:
    """Pide a Riot la página `offset`/`limit` del historial y la guarda.

    Solo se descargan (sin timeline) las partidas que faltan. La primera página
    renueva la marca de frescura del historial.
    """
    client = riot_client(player.region)
    async with create_secure_session() as session:
        match_ids = await client.fetch_match_ids_page(session, player.puuid, None, None, offset, count=limit)
        known = await known_participants(db, player.puuid, match_ids) if match_ids else {}
        missing = [match_id for match_id in match_ids if match_id not in known]
        fresh = (
            await client.fetch_participants(
                session, player_ref(player), role_filter=None, include_timeline=False, match_ids=missing
            )
            if missing
            else []
        )

    fresh_ids = await upsert_participants(db, fresh)
    participant_ids = [row.id for row in known.values()] + list(fresh_ids.values())
    await add_history_entries(db, player.id, participant_ids)
    if offset == 0:
        player.match_history_cached_at = datetime.now(timezone.utc)
    await db.commit()
    if fresh_ids:
        await invalidate_dashboards_for_participants(db, fresh_ids.values())

    logger.info(
        "[%s] History page offset=%d: %d matches (%d reused, %d downloaded).",
        player.game_name, offset, len(participant_ids), len(known), len(fresh_ids),
    )
    if not participant_ids:
        return []
    rows = await db.scalars(
        select(MatchParticipant).where(MatchParticipant.id.in_(participant_ids)).order_by(*_newest_first())
    )
    return list(rows)
