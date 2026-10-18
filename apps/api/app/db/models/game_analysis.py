from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GameAnalysis(Base):
    """The analysis of one of your matches: you upload its replay on the web (`processing`) and the API decodes it and
    analyses it (`done`, or `error` with the reason). `requested` is a match from a snapshot waiting for its
    replay.

    `result` has the shape of a snapshot's analysis (`summary`, `games`, `missing`) with a single match, so
    the web draws it the same way. `created_at` is when it was requested, and the quota comes from it."""

    __tablename__ = "game_analyses"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_game_analyses_user_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="requested", server_default="requested")
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    review: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
