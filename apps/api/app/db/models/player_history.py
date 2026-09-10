from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlayerHistoryEntry(Base):
    """Caché del historial reciente de un jugador (TTL en players.match_history_cached_at)."""

    __tablename__ = "player_history_entries"

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    match_participant_id: Mapped[int] = mapped_column(
        ForeignKey("match_participants.id", ondelete="CASCADE"), primary_key=True, index=True
    )
