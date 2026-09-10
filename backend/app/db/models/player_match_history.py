from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint

from app.db.base import Base


class PlayerMatchHistory(Base):
    __tablename__ = "player_match_history"
    __table_args__ = (
        UniqueConstraint("player_id", "match_id", name="uq_player_match_history"),
    )

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    match_id  = Column(Integer, ForeignKey("match_data.id", ondelete="CASCADE"), nullable=False)
