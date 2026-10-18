from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RankCutoff(Base):
    __tablename__ = "rank_cutoffs"

    platform: Mapped[str] = mapped_column(String(10), primary_key=True)
    grandmaster_cutoff_lp: Mapped[int]
    challenger_cutoff_lp: Mapped[int]
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
