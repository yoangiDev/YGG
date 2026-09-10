from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class MatchSnapshot(Base):
    """
    Tabla intermedia que relaciona Snapshots con Matches (N:M).
    Permite que una misma partida esté en múltiples snapshots sin duplicación de datos.
    """
    __tablename__ = "match_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("match_data.id", ondelete="CASCADE"), nullable=False, index=True)

    # Constraint: una partida no puede estar dos veces en el mismo snapshot
    __table_args__ = (
        UniqueConstraint("snapshot_id", "match_id", name="uq_snapshot_match"),
    )