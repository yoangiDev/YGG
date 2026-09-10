from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class RoleEnum(enum.Enum):
    TOP     = "TOP"
    JUNGLE  = "JUNGLE"
    MID     = "MID"
    BOTTOM  = "BOTTOM"
    SUPPORT = "SUPPORT"
    ALL     = "ALL"


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("user_id", "puuid", name="uq_players_user_puuid"),
    )

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    puuid           = Column(String(100), nullable=False)
    game_name       = Column(String(50), nullable=False)
    tag_line        = Column(String(10), nullable=False)
    region          = Column(String(10), nullable=False)
    nickname        = Column(String(20), default="")
    role            = Column(Enum(RoleEnum), default=RoleEnum.ALL, nullable=False)
    notes           = Column(Text, default="")

    # Datos de rango — se actualizan periódicamente desde la Riot API
    tier            = Column(String(20), default="")
    rank            = Column(String(5), default="")
    lp              = Column(Integer, default=0)
    profile_icon_id = Column(Integer, default=0)  # ID del icono de invocador (Data Dragon)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    match_history_cached_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def win_rate(self) -> float:
        # Usamos "or 0" para convertir None en 0 antes de calcular
        w = self.wins or 0
        l = self.losses or 0
        total = w + l
        if total == 0:
            return 0.0
        return round((w / total) * 100, 2)

    # ── Relaciones ─────────────────────────────────────────────────────────────
    owner = relationship(
        "User",
        back_populates="players"
    )
    snapshots = relationship(
        "Snapshot",
        back_populates="player",
        cascade="all, delete-orphan"  # Si se borra el jugador, se borran sus snapshots
    )