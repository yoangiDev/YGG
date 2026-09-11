from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.player import Player


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    date_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(String(255), default="")
    notes: Mapped[str | None] = mapped_column(Text, default="")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # joined: con AsyncSession no hay carga perezosa y el dashboard necesita el jugador.
    player: Mapped[Player] = relationship(back_populates="snapshots", lazy="joined")


def _add_match_count() -> None:
    from app.db.models.snapshot_participant import SnapshotParticipant  # evita el ciclo de imports

    Snapshot.match_count = column_property(
        select(func.count(SnapshotParticipant.match_participant_id))
        .where(SnapshotParticipant.snapshot_id == Snapshot.id)
        .correlate_except(SnapshotParticipant)
        .scalar_subquery()
    )


_add_match_count()
