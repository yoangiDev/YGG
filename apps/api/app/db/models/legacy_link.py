from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LegacyUnresolvedLink(Base):
    """Links from the old schema that the migration could not attribute.

    In `match_data` a shared match stored the stats of the first player
    analysed; the other players' snapshots pointed to someone else's data. The
    migration doesn't copy them (they would be wrong) but leaves them here so that
    `scripts/repair_legacy_links.py` recomputes them with the Riot API.
    """

    __tablename__ = "legacy_unresolved_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # "snapshot" | "history"
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[str] = mapped_column(String(50))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
