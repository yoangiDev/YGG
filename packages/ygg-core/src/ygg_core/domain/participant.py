"""Objetos de dominio que antes estaban implícitos en el modelo ORM `Match`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any, TypedDict


class DeathEvent(TypedDict, total=False):
    x: int
    y: int
    time: int  # segundos desde el inicio
    assistingParticipantIds: list[int]


class WardEvent(TypedDict, total=False):
    x: int
    y: int
    time: int
    type: str


class DragonSetup(TypedDict, total=False):
    dragon_time: int
    dragon_type: str
    team_dragon: bool
    in_prep_zone: bool
    at_kill_zone: bool
    secured_by_jg: bool
    contested: bool


@dataclass(slots=True, frozen=True)
class PlayerRef:
    """Lo mínimo para pedir partidas de un jugador a Riot."""

    puuid: str
    game_name: str = ""
    tag_line: str = ""

    @property
    def label(self) -> str:
        if self.game_name:
            return f"{self.game_name}#{self.tag_line}"
        return self.puuid[:12]


@dataclass(slots=True, frozen=True)
class RankInfo:
    tier: str
    rank: str
    lp: int
    wins: int
    losses: int


@dataclass(slots=True, frozen=True)
class SummonerInfo:
    profile_icon_id: int


@dataclass(slots=True)
class ParticipantStats:
    """Estadísticas de UN participante en UNA partida.

    Los nombres de campo coinciden con las columnas persistidas por la API, de
    modo que el mapeo dominio ↔ ORM es un simple volcado de atributos.
    """

    # ── Partida ────────────────────────────────────────────────────────────────
    match_id: str
    creation_time: datetime  # fin de la partida (gameCreation + gameDuration), UTC
    duration: int  # segundos
    queue_id: int = 420
    game_version: str = ""

    # ── Participante ───────────────────────────────────────────────────────────
    puuid: str = ""
    participant_id: int = 0
    team_id: int = 0
    player_role: str = "UNKNOWN"
    champion: str = ""
    win: bool = False

    # ── Combate ────────────────────────────────────────────────────────────────
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    kill_participation: float = 0.0  # 0-100
    vision: int = 0
    damage: int = 0
    gold: int = 0
    total_cs: int = 0
    damage_share: float = 0.0  # 0-100

    # ── Objetivos de equipo ────────────────────────────────────────────────────
    first_dragon: bool = False
    void_grubs: bool = False  # 2+ larvas
    herald: bool = False

    # ── Build ──────────────────────────────────────────────────────────────────
    summoner1_id: int = 0
    summoner2_id: int = 0
    item0: int = 0
    item1: int = 0
    item2: int = 0
    item3: int = 0
    item4: int = 0
    item5: int = 0
    item6: int = 0
    primary_rune: int = 0
    secondary_tree: int = 0

    # ── Métricas avanzadas ─────────────────────────────────────────────────────
    solo_kills: int = 0
    damage_structures: int = 0
    gold_share: float = 0.0
    enemy_jg_monsters: int = 0
    control_wards: int = 0
    roaming_proactivity: int = 0
    objective_vision_score: int = 0
    early_gank_deaths: int = 0

    # ── Timeline ───────────────────────────────────────────────────────────────
    cs_8: int = 0
    cs_14: int = 0
    cs_25: int = 0
    cs_diff_8: int = 0
    cs_diff_14: int = 0
    cs_diff_25: int = 0
    gold_diff_8: int = 0
    gold_diff_14: int = 0
    gold_diff_25: int = 0
    xp_diff_8: int = 0
    xp_diff_14: int = 0
    death_events: list[DeathEvent] = field(default_factory=list)
    ward_events: list[WardEvent] = field(default_factory=list)
    dragon_setups: list[DragonSetup] = field(default_factory=list)
    fullclear_time: int | None = None
    timeline_enriched: bool = False

    # ── Role Quests (temporada 26) ─────────────────────────────────────────────
    role_bound_item: int = 0
    quest_completed: bool = False
    quest_completion_time: int | None = None
    enemy_quest_completion_time: int | None = None
    quest_completion_time_diff: int | None = None

    @property
    def items(self) -> list[int]:
        return [self.item0, self.item1, self.item2, self.item3, self.item4, self.item5]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["creation_time"] = self.creation_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParticipantStats:
        known = {f.name for f in fields(cls)}
        values = {key: value for key, value in data.items() if key in known}
        created = values.get("creation_time")
        if isinstance(created, str):
            values["creation_time"] = datetime.fromisoformat(created)
        return cls(**values)


# Campos que calcula el enriquecimiento con timeline. Si se vuelve a descargar
# una partida, son los que hay que refrescar en la fila persistida.
TIMELINE_FIELDS: tuple[str, ...] = (
    "xp_diff_8",
    "xp_diff_14",
    "gold_diff_8",
    "gold_diff_14",
    "gold_diff_25",
    "cs_8",
    "cs_14",
    "cs_25",
    "cs_diff_8",
    "cs_diff_14",
    "cs_diff_25",
    "death_events",
    "ward_events",
    "dragon_setups",
    "timeline_enriched",
    "solo_kills",
    "roaming_proactivity",
    "objective_vision_score",
    "early_gank_deaths",
    "fullclear_time",
    "role_bound_item",
    "quest_completed",
    "quest_completion_time",
    "enemy_quest_completion_time",
    "quest_completion_time_diff",
)
