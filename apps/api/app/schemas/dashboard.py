from pydantic import BaseModel, computed_field
from typing import Any, Optional
from datetime import datetime

from ygg_core.metrics import aggregates

from app.schemas.match import MatchResponse


class ChampionStatsResponse(BaseModel):
    champion_name: str
    games_played: int
    win_rate: float
    icon_url: str


class RadarDataset(BaseModel):
    label: str
    values: dict[str, float]              # e.g., {"KDA": 4.2, "CS/Min": 8.5, ...}
    normalized_values: dict[str, float]     # e.g., {"KDA": 70.0, "CS/Min": 85.0, ...}


class RadarChartData(BaseModel):
    axes: list[str]                         # Nombres de los ejes
    player_dataset: RadarDataset
    rank_datasets: dict[str, RadarDataset]  # "CHALLENGER", ...
    pro_datasets: dict[str, RadarDataset]   # Cuentas comparadas en vivo


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


class SnapshotDashboardResponse(BaseModel):
    snapshot_id: int
    player_id: int
    player_name: str
    date_from: datetime
    date_to: datetime
    description: str
    notes: str
    active_role: str                        # "TOP" | "JUNGLE" | "MID" | "ADC" | "SUPPORT"
    role_averages: list[RoleAverageMetric]
    played_champions: list[ChampionStatsResponse]
    matches: list[MatchResponse]
    radar_data: RadarChartData

    @computed_field
    @property
    def deaths_by_phase(self) -> dict[str, int]:
        """Agrega los eventos de muerte de todas las partidas por fase del juego."""
        early = 0
        mid = 0
        late = 0
        for m in (self.matches or []):
            phase_deaths = m.deaths_by_phase
            early += phase_deaths.get("early_deaths", 0)
            mid += phase_deaths.get("mid_deaths", 0)
            late += phase_deaths.get("late_deaths", 0)
        return {
            "early_deaths": early,
            "mid_deaths": mid,
            "late_deaths": late
        }

    @computed_field
    @property
    def performance_trends(self) -> list[TrendPoint]:
        """Rendimiento cronológico con medias móviles para alimentar las gráficas."""
        ordered = sorted(self.matches or [], key=lambda m: m.creation_time)
        window = aggregates.trend_window_size(len(ordered))
        kda = aggregates.moving_average([m.kda for m in ordered], window)
        cs = aggregates.moving_average([m.cs_per_min for m in ordered], window)
        gold = aggregates.moving_average([m.gold_per_min for m in ordered], window)
        vision = aggregates.moving_average([m.vision_per_min for m in ordered], window)
        return [
            TrendPoint(
                game_num=index + 1,
                match_id=m.match_id,
                creation_time=m.creation_time,
                champion=m.champion,
                win=m.win,
                kda=m.kda,
                cs_per_min=m.cs_per_min,
                gold_per_min=m.gold_per_min,
                vision_per_min=m.vision_per_min,
                kda_moving_avg=kda[index],
                cs_moving_avg=cs[index],
                gold_moving_avg=gold[index],
                vision_moving_avg=vision[index],
            )
            for index, m in enumerate(ordered)
        ]
