from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, select
from sqlalchemy.orm import relationship, column_property
from sqlalchemy.sql import func

from app.db.base import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id          = Column(Integer, primary_key=True, index=True)
    player_id   = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    date_from   = Column(DateTime(timezone=True), nullable=False)
    date_to     = Column(DateTime(timezone=True), nullable=False)
    description = Column(String(255), default="")
    notes       = Column(Text, default="")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # ── Relaciones ─────────────────────────────────────────────────────────────
    player = relationship(
        "Player",
        back_populates="snapshots"
    )
    matches = relationship(
        "Match",
        secondary="match_snapshots",
        back_populates="snapshots"
    )


def _add_match_count():
    from app.db.models.match_snapshot import MatchSnapshot  # import diferido para evitar ciclo
    Snapshot.match_count = column_property(
        select(func.count(MatchSnapshot.match_id))
        .where(MatchSnapshot.snapshot_id == Snapshot.id)
        .correlate_except(MatchSnapshot)
        .scalar_subquery()
    )

_add_match_count()