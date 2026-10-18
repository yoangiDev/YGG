from pydantic import BaseModel, computed_field, field_validator
from typing import Any, Literal, Optional, List
from datetime import datetime

from ygg_core.metrics import aggregates
from ygg_core.metrics.match_score import metric_status
from ygg_core.timeline.quests import quest_reward_item

Status = Literal["excellent", "good", "normal", "bad"]


class MatchResponse(BaseModel):
    match_id: str
    player_id: Optional[int] = None
    snapshot_id: Optional[int] = None
    creation_time: datetime
    game_version: str = ""  # the build (16.19.823.722): a snapshot's sessions can't cross it
    champion: str
    win: bool
    duration: int
    kills: int
    deaths: int
    assists: int
    kill_participation: float
    vision: int
    damage: int
    gold: int
    total_cs: int
    damage_share: float
    first_dragon: bool
    void_grubs: bool
    herald: bool

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

    death_events: Optional[List[Any]] = []
    ward_events: Optional[List[Any]] = []

    # Only in matches analysed with a timeline (snapshots): total WPA in points and a 0-100 grade (70 = average Challenger).
    wpa_total: Optional[float] = None
    wpa_grade: Optional[int] = None

    # Only in the history and if the match has a stored summary: 0-100 grade, 1-10 position and badge.
    score: Optional[int] = None
    placement: Optional[int] = None
    badge: Optional[Literal["MVP", "ACE"]] = None

    # New advanced stats for the Dashboard
    solo_kills: int = 0
    damage_structures: int = 0
    gold_share: float = 0.0
    enemy_jg_monsters: int = 0
    control_wards: int = 0
    roaming_proactivity: int = 0
    objective_vision_score: int = 0
    early_gank_deaths: Optional[int] = 0
    player_role: Optional[str] = None

    # Role Quests (Season 26)
    role_bound_item: Optional[int] = 0
    quest_completed: Optional[bool] = False
    quest_completion_time: Optional[int] = None
    enemy_quest_completion_time: Optional[int] = None
    quest_completion_time_diff: Optional[int] = None
    fullclear_time: Optional[int] = None

    # Timeline fields (may be None if no timeline was downloaded)
    cs_8: Optional[int] = None
    cs_14: Optional[int] = None
    cs_25: Optional[int] = None
    cs_diff_8: Optional[int] = None
    cs_diff_14: Optional[int] = None
    cs_diff_25: Optional[int] = None
    gold_diff_8: Optional[int] = None
    gold_diff_14: Optional[int] = None
    gold_diff_25: Optional[int] = None
    xp_diff_8: Optional[int] = None
    xp_diff_14: Optional[int] = None
    xp_diff_25: Optional[int] = None
    solo_kills: Optional[int] = None
    roaming_proactivity: Optional[int] = None
    objective_vision_score: Optional[int] = None

    model_config = {"from_attributes": True}

    # Validator to normalise legacy JSON ({}) and None → []
    @field_validator('death_events', 'ward_events', mode='before')
    @classmethod
    def validate_json_lists(cls, v):
        if v is None or v == {}:
            return []
        if isinstance(v, list):
            return v
        return []

    @field_validator('quest_completed', mode='before')
    @classmethod
    def validate_quest_completed(cls, v):
        return False if v is None else v

    @field_validator('role_bound_item', mode='before')
    @classmethod
    def validate_role_bound_item(cls, v):
        return 0 if v is None else v

    # ── Computed fields ────────────────────────────────────────────────

    @computed_field
    @property
    def duration_minutes(self) -> float:
        return round(self.duration / 60, 2) if self.duration > 0 else 0

    @computed_field
    @property
    def kda(self) -> float:
        if self.deaths == 0:
            return float(self.kills + self.assists)
        return round((self.kills + self.assists) / self.deaths, 2)

    @computed_field
    @property
    def cs_per_min(self) -> float:
        return round(self.total_cs / self.duration_minutes, 2) if self.duration > 0 else 0

    @computed_field
    @property
    def dmg_per_min(self) -> float:
        return round(self.damage / self.duration_minutes, 2) if self.duration > 0 else 0

    @computed_field
    @property
    def gold_per_min(self) -> float:
        return round(self.gold / self.duration_minutes, 2) if self.duration > 0 else 0

    @computed_field
    @property
    def vision_per_min(self) -> float:
        return round(self.vision / self.duration_minutes, 2) if self.duration > 0 else 0

    @computed_field
    @property
    def death_events_normalized(self) -> list[dict[str, Any]]:
        return aggregates.normalized_death_events(self.death_events)

    @computed_field
    @property
    def kda_status(self) -> Status:
        """KDA against the role's Challenger matches."""
        return metric_status("kda", self.kda, self.player_role)

    @computed_field
    @property
    def cs_status(self) -> Status:
        """CS/min against the role's Challenger range."""
        return metric_status("cs_per_min", self.cs_per_min, self.player_role)

    @computed_field
    @property
    def dmg_status(self) -> Status:
        """Damage/min against the role's Challenger range."""
        return metric_status("damage_per_min", self.dmg_per_min, self.player_role)

    @computed_field
    @property
    def quest_reward_item(self) -> int:
        """Role Quest reward if it was completed (the ADC's boots, the top's Teleport...), or 0."""
        return quest_reward_item(self.role_bound_item)


class PlayerChampionStats(BaseModel):
    """A player's performance with one champion (SQL query player_champion_stats).

    kills, deaths, assists and vision_score are per-match means; kda and the per-minute
    ratios are computed over the total of their matches with that champion.
    """

    champion_name: str
    games: int
    wins: int
    losses: int
    win_rate: float
    kills: float
    deaths: float
    assists: float
    kda: float
    cs_per_min: float
    dmg_per_min: float
    vision_score: float
    role: Optional[str] = None  # the most played with that champion

    @computed_field
    @property
    def kda_status(self) -> Status:
        """KDA against the Challenger matches of their most played role."""
        return metric_status("kda", self.kda, self.role)

    @computed_field
    @property
    def cs_status(self) -> Status:
        """CS/min against the Challenger range of their most played role."""
        return metric_status("cs_per_min", self.cs_per_min, self.role)

    @computed_field
    @property
    def dmg_status(self) -> Status:
        """Damage/min against the Challenger range of their most played role."""
        return metric_status("damage_per_min", self.dmg_per_min, self.role)


class WpaDriverResponse(BaseModel):
    """A part of the state that changed with the event and the points of its value that it explains."""

    factor: str  # model feature: gold_k, dead, kills, outer_turrets, dragons, baron_active...
    change: float  # how much it changed in favour of their team (gold and XP in units)
    wpa: float


class WpaEventResponse(BaseModel):
    """An event the player took part in, with the win-probability points attributed to them.

    The why (team_wpa, share, shared_with, drivers) is missing from matches analysed before version 5.
    """

    time: int  # seconds
    kind: Literal["KILL", "ASSIST", "DEATH", "OBJECTIVE", "OBJECTIVE_AFTER_KILL", "CONCEDED_WHILE_DEAD"]
    target: str  # champion or objective (BARON_NASHOR, DRAGON_1, TOWER_OUTER_MID...)
    wp_before: float  # their team's WP, 0-100
    wp_after: float
    wpa: float  # = team_wpa · share
    # Value of the event for their team: WP points as if the game were even (since version 6).
    team_wpa: Optional[float] = None
    share: Optional[float] = None  # the part attributed to them, 0-1
    shared_with: Optional[int] = None  # among how many it is split, them included
    drivers: List[WpaDriverResponse] = []  # why the WP changed, from highest to lowest weight
    bounty: int = 0  # gold of the kill that was collected or given, without shutdown
    shutdown: int = 0  # shutdown gold
    gold_lost: Optional[List[int]] = None  # only on DEATH: [gold lost with the respawn, with respawn + walk back]; missing from earlier analyses


class WpaTimelineResponse(BaseModel):
    """WPA timeline of a match in a snapshot. Empty if it was analysed before WPA existed."""

    match_id: str
    wpa_total: Optional[float] = None
    wpa_grade: Optional[int] = None
    wp_curve: List[float] = []  # their team's WP at each minute, 0-100
    events: List[WpaEventResponse] = []

    @classmethod
    def from_participant(cls, row: Any) -> "WpaTimelineResponse":
        return cls(
            match_id=row.match_id, wpa_total=row.wpa_total, wpa_grade=row.wpa_grade,
            wp_curve=row.wp_curve or [], events=row.wpa_events or [],
        )
