from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.participant import MatchParticipant


class Match(Base):
    """Una partida de Riot. Lo que hizo cada jugador vive en MatchParticipant."""

    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    creation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration: Mapped[int]  # segundos
    queue_id: Mapped[int] = mapped_column(default=420, server_default=text("420"))
    game_version: Mapped[str] = mapped_column(String(32), default="", server_default="")

    participants: Mapped[list[MatchParticipant]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
