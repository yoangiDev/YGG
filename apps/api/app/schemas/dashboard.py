from pydantic import BaseModel, computed_field
from typing import Any, Optional
from datetime import datetime
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
    axes: list[str]                         # Nombres de los 6 ejes
    player_dataset: RadarDataset
    rank_datasets: dict[str, RadarDataset]  # "CHALLENGER", "GRANDMASTER", "MASTER", "DIAMOND", "EMERALD"
    pro_datasets: dict[str, RadarDataset]   # Nombres de proplayers de cada rol


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
        """Calcula el rendimiento cronológico con medias móviles para alimentar las gráficas."""
        trends = []
        sorted_matches = sorted(self.matches or [], key=lambda m: m.creation_time)
        n_games = len(sorted_matches)
        
        # Calcular tamaño dinámico de la ventana: 15% del total, entre 3 y 10 partidas
        w_size = max(3, min(10, round(n_games * 0.15)))
        
        for idx, m in enumerate(sorted_matches):
            game_num = idx + 1
            
            # Obtener ventana dinámica de partidas para el cálculo de la media móvil
            window = sorted_matches[max(0, idx - w_size + 1) : idx + 1]
            
            kda_vals = [w.kda for w in window]
            cs_vals = [w.cs_per_min for w in window]
            gold_vals = [w.gold_per_min for w in window]
            vision_vals = [w.vision_per_min for w in window]
            
            kda_moving_avg = round(sum(kda_vals) / len(kda_vals), 2) if kda_vals else 0.0
            cs_moving_avg = round(sum(cs_vals) / len(cs_vals), 2) if cs_vals else 0.0
            gold_moving_avg = round(sum(gold_vals) / len(gold_vals), 2) if gold_vals else 0.0
            vision_moving_avg = round(sum(vision_vals) / len(vision_vals), 2) if vision_vals else 0.0
            
            trends.append(
                TrendPoint(
                    game_num=game_num,
                    match_id=m.match_id,
                    creation_time=m.creation_time,
                    champion=m.champion,
                    win=m.win,
                    kda=m.kda,
                    cs_per_min=m.cs_per_min,
                    gold_per_min=m.gold_per_min,
                    vision_per_min=m.vision_per_min,
                    kda_moving_avg=kda_moving_avg,
                    cs_moving_avg=cs_moving_avg,
                    gold_moving_avg=gold_moving_avg,
                    vision_moving_avg=vision_moving_avg,
                )
            )
        return trends
