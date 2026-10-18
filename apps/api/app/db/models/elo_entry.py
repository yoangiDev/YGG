from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EloEntry(Base):
    """A player's rank with elo tracking: one per day, the last one queried."""

    __tablename__ = "elo_history"

    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    tier: Mapped[str] = mapped_column(String(20))
    division: Mapped[str] = mapped_column(String(5))
    lp: Mapped[int]
    wins: Mapped[int]
    losses: Mapped[int]
