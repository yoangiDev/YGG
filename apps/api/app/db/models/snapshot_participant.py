from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SnapshotParticipant(Base):
    """N:M snapshot ↔ participant (not ↔ match).

    Linking the participant and not the match is what guarantees that a player's
    snapshot shows their own stats.
    """

    __tablename__ = "snapshot_participants"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    match_participant_id: Mapped[int] = mapped_column(
        ForeignKey("match_participants.id", ondelete="CASCADE"), primary_key=True, index=True
    )
