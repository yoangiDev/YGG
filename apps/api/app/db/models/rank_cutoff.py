from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.base import Base


class RankCutoff(Base):
    __tablename__ = "rank_cutoffs"

    platform              = Column(String(10), primary_key=True)
    grandmaster_cutoff_lp = Column(Integer, nullable=False)
    challenger_cutoff_lp  = Column(Integer, nullable=False)
    fetched_at            = Column(DateTime, nullable=False, default=datetime.utcnow)
