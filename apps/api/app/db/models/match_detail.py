from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchDetail(Base):
    """Resumen de una partida con sus 10 participantes (ygg_core MatchSummary).

    Se pide a Riot la primera vez que alguien despliega la partida y se guarda:
    las partidas terminadas no cambian. `version` permite regenerarlo si cambia
    la forma del resumen.
    """

    __tablename__ = "match_details"

    match_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int]
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
