from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ACTIVE_JOB_STATUSES = ("queued", "processing")


class Job(Base):
    """A queued analysis. It is run by the ARQ worker, outside the API process."""

    __tablename__ = "jobs"
    __table_args__ = (
        # Idempotency: at most one active analysis per (user, player, rank).
        # The database guarantees it even if two requests arrive at the same time.
        Index(
            "uq_jobs_active_request",
            "user_id",
            "player_id",
            "date_from",
            "date_to",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
        ),
        Index("ix_jobs_status_heartbeat_at", "status", "heartbeat_at"),
    )

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    # Owner of the job: only they can query its status. NULL on earlier jobs.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    date_from: Mapped[int | None] = mapped_column(BigInteger)  # Unix timestamp (s)
    date_to: Mapped[int | None] = mapped_column(BigInteger)
    description: Mapped[str | None] = mapped_column(String(255))
    # On finishing, it also queues the snapshot's replay analysis (replay analysis).
    premium: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    status: Mapped[str] = mapped_column(String, default="queued")  # queued | processing | done | error
    snapshot_id: Mapped[int | None]
    error: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[int | None] = mapped_column(default=0)  # 0-100
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))

    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
