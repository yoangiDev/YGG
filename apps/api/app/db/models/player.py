from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.snapshot import Snapshot
    from app.db.models.user import User


class RoleEnum(enum.Enum):
    TOP     = "TOP"
    JUNGLE  = "JUNGLE"
    MID     = "MID"
    BOTTOM  = "BOTTOM"
    SUPPORT = "SUPPORT"
    ALL     = "ALL"


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("user_id", "puuid", name="uq_players_user_puuid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    puuid: Mapped[str] = mapped_column(String(100))
    game_name: Mapped[str] = mapped_column(String(50))
    tag_line: Mapped[str] = mapped_column(String(10))
    region: Mapped[str] = mapped_column(String(10))
    nickname: Mapped[str | None] = mapped_column(String(20), default="")
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), default=RoleEnum.ALL)
    notes: Mapped[str | None] = mapped_column(Text, default="")

    # Datos de rango — se actualizan periódicamente desde la Riot API
    tier: Mapped[str | None] = mapped_column(String(20), default="")
    rank: Mapped[str | None] = mapped_column(String(5), default="")
    lp: Mapped[int | None] = mapped_column(default=0)
    profile_icon_id: Mapped[int | None] = mapped_column(default=0)  # icono de invocador (Data Dragon)
    wins: Mapped[int | None] = mapped_column(default=0)
    losses: Mapped[int | None] = mapped_column(default=0)
    match_history_cached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="players")
    snapshots: Mapped[list[Snapshot]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",  # Si se borra el jugador, se borran sus snapshots
    )

    @property
    def win_rate(self) -> float:
        wins = self.wins or 0
        losses = self.losses or 0
        total = wins + losses
        if total == 0:
            return 0.0
        return round((wins / total) * 100, 2)
