from pydantic import BaseModel, computed_field, field_validator
from typing import Any, Optional, List
from datetime import datetime

from app.service.role_quest_parser import resolve_role_bound_item


class MatchResponse(BaseModel):
    match_id: str
    player_id: Optional[int] = None
    snapshot_id: Optional[int] = None
    creation_time: datetime
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
    dragon_setups: Optional[List[Any]] = []

    # Nuevas estadísticas avanzadas para Dashboard
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

    @computed_field
    @property
    def quest_item_id(self) -> int:
        return resolve_role_bound_item(
            self.role_bound_item,
            self.player_role,
            self.creation_time,
            [self.item0, self.item1, self.item2, self.item3, self.item4, self.item5],
        )

    # Campos de timeline (pueden ser None si no se descargó timeline)
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

    # Validator para normalizar JSON legacy ({}) y None → []
    @field_validator('death_events', 'ward_events', 'dragon_setups', mode='before')
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
    def fullclear_timer(self) -> str | None:
        if self.fullclear_time is None:
            return None
        minutes, seconds = divmod(self.fullclear_time, 60)
        return f"{minutes}:{seconds:02d}"

    @computed_field
    @property
    def vision_per_min(self) -> float:
        return round(self.vision / self.duration_minutes, 2) if self.duration > 0 else 0

    @computed_field
    @property
    def deaths_by_phase(self) -> dict[str, int]:
        early = 0
        mid = 0
        late = 0
        for d in (self.death_events or []):
            t = d.get("time", 0)
            if t < 480:
                early += 1
            elif t < 840:
                mid += 1
            else:
                late += 1
        return {
            "early_deaths": early,
            "mid_deaths": mid,
            "late_deaths": late
        }

    @computed_field
    @property
    def death_events_normalized(self) -> list[dict[str, Any]]:
        normalized = []
        for d in (self.death_events or []):
            x = d.get("x", 0)
            y = d.get("y", 0)
            nx = max(0.0, min(1.0, x / 15000))
            ny = max(0.0, min(1.0, 1.0 - (y / 15000)))
            normalized.append({
                "x": x,
                "y": y,
                "norm_x": round(nx, 4),
                "norm_y": round(ny, 4),
                "time": d.get("time", 0),
                "assistingParticipantIds": d.get("assistingParticipantIds", []),
            })
        return normalized

    @computed_field
    @property
    def ward_events_normalized(self) -> list[dict[str, Any]]:
        normalized = []
        for w in (self.ward_events or []):
            x = w.get("x", 0)
            y = w.get("y", 0)
            nx = max(0.0, min(1.0, x / 15000))
            ny = max(0.0, min(1.0, 1.0 - (y / 15000)))
            normalized.append({
                "x": x,
                "y": y,
                "norm_x": round(nx, 4),
                "norm_y": round(ny, 4),
                "time": w.get("time", 0),
                "type": w.get("type", "unknown"),
            })
        return normalized

    @computed_field
    @property
    def dragon_setups_summary(self) -> dict[str, Any]:
        setups = self.dragon_setups or []
        team = [s for s in setups if s.get("team_dragon")]
        if not team:
            return {
                "team_dragons": 0,
                "setup_rate": None,
                "presence_at_kill_rate": None,
                "secure_rate": None,
            }
        n = len(team)
        return {
            "team_dragons": n,
            "setup_rate": round(
                sum(1 for s in team if s.get("in_prep_zone")) / n * 100, 1
            ),
            "presence_at_kill_rate": round(
                sum(1 for s in team if s.get("at_kill_zone")) / n * 100, 1
            ),
            "secure_rate": round(
                sum(1 for s in team if s.get("secured_by_jg")) / n * 100, 1
            ),
        }


class SnapshotStatsResponse(BaseModel):
    snapshot_id: int
    games_played: int
    winrate: float
    avg_kda: float
    avg_cs_per_min: float
    avg_damage_per_min: float
    avg_gold_per_min: float
    avg_vision: float
    avg_kill_participation: float
    first_dragon_rate: str
    herald_rate: str
    two_or_more_void_grubs_rate: str

    @classmethod
    def from_matches(cls, snapshot_id: int, matches: list["MatchResponse"]) -> "SnapshotStatsResponse":
        n = len(matches)
        if n == 0:
            return cls(
                snapshot_id=snapshot_id, games_played=0, winrate=0, avg_kda=0,
                avg_cs_per_min=0, avg_damage_per_min=0, avg_gold_per_min=0,
                avg_vision=0, avg_kill_participation=0,
                first_dragon_rate="0/0", herald_rate="0/0", two_or_more_void_grubs_rate="0/0"
            )
        return cls(
            snapshot_id=snapshot_id,
            games_played=n,
            winrate=round(sum(m.win for m in matches) / n * 100, 1),
            avg_kda=round(sum(m.kda for m in matches) / n, 2),
            avg_cs_per_min=round(sum(m.cs_per_min for m in matches) / n, 2),
            avg_damage_per_min=round(sum(m.dmg_per_min for m in matches) / n, 2),
            avg_gold_per_min=round(sum(m.gold_per_min for m in matches) / n, 2),
            avg_vision=round(sum(m.vision for m in matches) / n, 1),
            avg_kill_participation=round(sum(m.kill_participation for m in matches) / n, 1),
            first_dragon_rate=f"{sum(m.first_dragon for m in matches)}/{n}",
            herald_rate=f"{sum(m.herald for m in matches)}/{n}",
            two_or_more_void_grubs_rate=f"{sum(m.void_grubs for m in matches)}/{n}",
        )

class MostPlayedChampionResponse(BaseModel):
    champion_name: str
    games_played: int
    win_rate: float
    icon_url: str