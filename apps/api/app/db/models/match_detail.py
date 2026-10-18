from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchDetail(Base):
    """Summary of a match with its 10 participants (ygg_core MatchSummary).

    It is requested from Riot the first time someone expands the match and is stored:
    finished matches don't change. `version` allows regenerating it if the
    shape of the summary changes.
    """

    __tablename__ = "match_details"

    match_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int]
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
