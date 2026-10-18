from datetime import datetime

from pydantic import BaseModel


class ChampionStatsResponse(BaseModel):
    """Performance with one champion in the snapshot.

    kills, deaths, assists, the @14 differences and the deaths by phase are per-match
    means; kda and the per-minute rates come from the total of their matches.
    """

    champion_name: str
    games_played: int
    win_rate: float
    wins: int
    losses: int
    kills: float
    deaths: float
    assists: float
    kda: float
    kda_status: str  # against the player's target league, like the cards
    cs_per_min: float
    dmg_per_min: float
    gold_per_min: float
    vision_per_min: float
    kill_participation: float
    damage_share: float
    gold_diff_14: float | None
    cs_diff_14: float | None
    laning_deaths: float | None
    mid_late_deaths: float | None


class RadarDataset(BaseModel):
    label: str
    values: dict[str, float]              # p. ej. {"KDA": 4.2, "CS/Min": 8.5}
    normalized_values: dict[str, float]   # 0-100 relative to the role's ceiling


class RadarChartData(BaseModel):
    axes: list[str]
    player_dataset: RadarDataset
    rank_datasets: dict[str, RadarDataset]  # "CHALLENGER"
    pro_datasets: dict[str, RadarDataset]   # accounts compared live


class RoleAverageMetric(BaseModel):
    key: str
    label: str
    value: float
    status: str                             # "excellent" | "good" | "normal" | "bad"
    threshold: float
    unit: str = ""


class TrendGame(BaseModel):
    game_num: int
    match_id: str
    creation_time: datetime
    champion: str
    win: bool


class TrendSeries(BaseModel):
    key: str
    label: str
    unit: str                               # "" | "%"
    digits: int
    signed: bool                            # differences: shown with a sign
    challenger: float | None                # what is expected of a Challenger in the role (dotted line)
    values: list[float | None]              # one per match, in the order of `games`
    moving_average: list[float | None]


class TrendGroup(BaseModel):
    key: str                                # "individual" | "vs" | "objectives" | "deaths"
    label: str
    metrics: list[TrendSeries]


class SnapshotTrends(BaseModel):
    games: list[TrendGame]                  # in chronological order
    groups: list[TrendGroup]


class SnapshotDashboardResponse(BaseModel):
    """Dashboard of a snapshot.

    It does not include the list of matches (P9): they are requested paginated at
    GET /matches/snapshot/{snapshot_id}. That way the response fits in the cache and doesn't
    grow with the number of matches.
    """
    snapshot_id: int
    player_id: int
    player_name: str
    date_from: datetime
    date_to: datetime
    description: str | None = ""
    notes: str | None = ""
    active_role: str                        # "TOP" | "JUNGLE" | "MID" | "ADC" | "SUPPORT"
    target_rank: str  # rank whose averages the radar and the cards are compared with
    games_played: int
    role_averages: list[RoleAverageMetric]
    played_champions: list[ChampionStatsResponse]
    trends: SnapshotTrends
    radar_data: RadarChartData
