import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import ParticipantStats

from app.crud.participants import replace_history, upsert_participants
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.player_history import PlayerHistoryEntry
from app.service.dashboard_cache import invalidate_dashboards_for_participants

logger = logging.getLogger(__name__)

_HISTORY_TTL = timedelta(hours=1)
DEFAULT_HISTORY_LIMIT = 100


def is_history_fresh(player: Player) -> bool:
    if not player.match_history_cached_at:
        return False
    return datetime.now(timezone.utc) - player.match_history_cached_at < _HISTORY_TTL


async def get_history_from_cache(
    db: AsyncSession, player_id: int, limit: int = DEFAULT_HISTORY_LIMIT
) -> list[MatchParticipant]:
    stmt = (
        select(MatchParticipant)
        .join(PlayerHistoryEntry, PlayerHistoryEntry.match_participant_id == MatchParticipant.id)
        .where(PlayerHistoryEntry.player_id == player_id)
        .order_by(MatchParticipant.creation_time.desc())
        .limit(limit)
    )
    return list(await db.scalars(stmt))


async def update_history_cache(
    db: AsyncSession, player: Player, participants: Sequence[ParticipantStats]
) -> None:
    """Guarda las partidas, deja el historial con exactamente estas y renueva el TTL."""
    ids = await upsert_participants(db, participants)
    await replace_history(db, player.id, list(ids.values()))
    player.match_history_cached_at = datetime.now(timezone.utc)
    await db.commit()
    await invalidate_dashboards_for_participants(db, ids.values())
    logger.info("[%s] History cache updated with %d matches.", player.game_name, len(ids))
