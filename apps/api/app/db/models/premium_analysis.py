from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PremiumAnalysis(Base):
    """A snapshot's replay analysis: its matches decoded from the .rofl, what comes out of them
    (`result`) and the review that Claude writes (`review`).

    Since 16.20 the user uploads each match's replay on the web and the API puts together what comes out
    (`app.service.premium`)."""

    __tablename__ = "premium_analyses"

    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | processing | done | error
    progress: Mapped[int] = mapped_column(default=0, server_default=text("0"))  # 0-100
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    review: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
