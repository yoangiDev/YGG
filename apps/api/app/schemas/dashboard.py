from datetime import datetime

from pydantic import BaseModel


class ChampionStatsResponse(BaseModel):
    champion_name: str
    games_played: int
    win_rate: float
    icon_url: str


class RadarDataset(BaseModel):
    label: str
    values: dict[str, float]              # p. ej. {"KDA": 4.2, "CS/Min": 8.5}
    normalized_values: dict[str, float]   # 0-100 respecto al techo del rol


class RadarChartData(BaseModel):
    axes: list[str]
    player_dataset: RadarDataset
    rank_datasets: dict[str, RadarDataset]  # "CHALLENGER"
    pro_datasets: dict[str, RadarDataset]   # cuentas comparadas en vivo


class RoleAverageMetric(BaseModel):
    key: str
    label: str
    value: float
    status: str                             # "excellent" | "good" | "normal" | "bad"
    threshold: float
    unit: str = ""


class TrendPoint(BaseModel):
    game_num: int
    match_id: str
    creation_time: datetime
    champion: str
    win: bool
    kda: float
    cs_per_min: float
    gold_per_min: float
    vision_per_min: float
    kda_moving_avg: float
    cs_moving_avg: float
    gold_moving_avg: float
    vision_moving_avg: float


class DeathsByPhase(BaseModel):
    early_deaths: int   # antes del minuto 8
    mid_deaths: int     # minutos 8-14
    late_deaths: int    # a partir del 14


class SnapshotDashboardResponse(BaseModel):
    """Dashboard de un snapshot.

    No incluye la lista de partidas (P9): se piden paginadas en
    GET /matches/snapshot/{snapshot_id}. Así la respuesta cabe en caché y no
    crece con el número de partidas.
    """
    snapshot_id: int
    player_id: int
    player_name: str
    date_from: datetime
    date_to: datetime
    description: str | None = ""
    notes: str | None = ""
    active_role: str                        # "TOP" | "JUNGLE" | "MID" | "ADC" | "SUPPORT"
    games_played: int
    role_averages: list[RoleAverageMetric]
    played_champions: list[ChampionStatsResponse]
    deaths_by_phase: DeathsByPhase
    performance_trends: list[TrendPoint]
    radar_data: RadarChartData
