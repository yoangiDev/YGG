from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class Match(Base):
    __tablename__ = "match_data"

    # ── Identificación ─────────────────────────────────────────────────────────
    id              = Column(Integer, primary_key=True, index=True)
    match_id        = Column(String(50), unique=True, nullable=False, index=True)
    creation_time   = Column(DateTime(timezone=True), nullable=False)

    # ── Datos básicos de partida ───────────────────────────────────────────────
    champion        = Column(String(50), nullable=False)
    win             = Column(Boolean, nullable=False)
    duration        = Column(Integer, nullable=False)               # En segundos

    # ── Estadísticas de combate ────────────────────────────────────────────────
    kills           = Column(Integer, default=0)
    deaths          = Column(Integer, default=0)
    assists         = Column(Integer, default=0)
    kill_participation = Column(Float, default=0.0)                 # Porcentaje 0-100
    vision          = Column(Integer, default=0)                    # Vision Score
    damage          = Column(Integer, default=0)                    # Daño total a campeones
    gold            = Column(Integer, default=0)                    # Oro total
    total_cs        = Column(Integer, default=0)                    # CS + monstruos de jungla
    damage_share    = Column(Float, default=0.0)                    # % del daño total del equipo

    # ── Objetivos de equipo ────────────────────────────────────────────────────
    first_dragon    = Column(Boolean, default=False)
    void_grubs      = Column(Boolean, default=False)                # 2+ larvas del vacío
    herald          = Column(Boolean, default=False)

    # ── Equipamiento y Runas ───────────────────────────────────────────────────
    summoner1_id    = Column(Integer, default=0)
    summoner2_id    = Column(Integer, default=0)
    item0           = Column(Integer, default=0)
    item1           = Column(Integer, default=0)
    item2           = Column(Integer, default=0)
    item3           = Column(Integer, default=0)
    item4           = Column(Integer, default=0)
    item5           = Column(Integer, default=0)
    item6           = Column(Integer, default=0)
    primary_rune    = Column(Integer, default=0)
    secondary_tree  = Column(Integer, default=0)

    # ── Eventos de muerte (JSON) ───────────────────────────────────────────────
    death_events    = Column(JSON, default=list)
    ward_events     = Column(JSON, default=list)
    dragon_setups = Column(JSON, default=list)
    timeline_enriched = Column(Boolean, default=False, nullable=False)
    player_role = Column(String(20), nullable=True)

    # ── Role Quests (Season 26) ───────────────────────────────────────────────
    role_bound_item = Column(Integer, default=0, nullable=False)
    quest_completed = Column(Boolean, default=False, nullable=False)
    quest_completion_time = Column(Integer, nullable=True)
    enemy_quest_completion_time = Column(Integer, nullable=True)
    quest_completion_time_diff = Column(Integer, nullable=True)
    fullclear_time = Column(Integer, nullable=True)

    # ── Nuevas estadísticas avanzadas para Dashboard ───────────────────────────
    solo_kills          = Column(Integer, default=0)
    damage_structures   = Column(Integer, default=0)
    gold_share          = Column(Float, default=0.0)
    enemy_jg_monsters   = Column(Integer, default=0)
    control_wards       = Column(Integer, default=0)
    roaming_proactivity = Column(Integer, default=0)
    objective_vision_score = Column(Integer, default=0)
    early_gank_deaths   = Column(Integer, default=0)

    # ── Diferencias por minuto ─────────────────────────────────────────────────
    cs_8            = Column(Integer, default=0)
    cs_14           = Column(Integer, default=0)
    cs_25           = Column(Integer, default=0)
    cs_diff_8       = Column(Integer, default=0)
    cs_diff_14      = Column(Integer, default=0)
    cs_diff_25      = Column(Integer, default=0)
    gold_diff_8     = Column(Integer, default=0)
    gold_diff_14    = Column(Integer, default=0)
    gold_diff_25    = Column(Integer, default=0)
    xp_diff_8       = Column(Integer, default=0)
    xp_diff_14      = Column(Integer, default=0)

    # ── Relaciones ─────────────────────────────────────────────────────────────
    snapshots = relationship(
        "Snapshot",
        secondary="match_snapshots",
        back_populates="matches"
    )