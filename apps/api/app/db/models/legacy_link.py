from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LegacyUnresolvedLink(Base):
    """Enlaces del esquema antiguo que la migración no pudo atribuir.

    En `match_data` una partida compartida guardaba las estadísticas del primer
    jugador analizado; los snapshots de los demás apuntaban a datos ajenos. La
    migración no los copia (serían incorrectos) sino que los deja aquí para que
    `scripts/repair_legacy_links.py` los recalcule con la Riot API.
    """

    __tablename__ = "legacy_unresolved_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # "snapshot" | "history"
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[str] = mapped_column(String(50))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
