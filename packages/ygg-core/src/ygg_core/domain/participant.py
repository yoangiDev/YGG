"""Domain objects that used to be implicit in the `Match` ORM model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any, TypedDict

# Version of what is computed when a match is downloaded. Bump it when adding or fixing
# metrics: matches stored with an earlier version are downloaded again.
# 2: impact by role · 3: CS in the enemy jungle read from where Riot sends it.
# 6: neutral WPA (each play as if the game were even) and shutdown with its own gold.
# 7: note of gold lost on each death.
TIMELINE_VERSION = 7


class DeathEvent(TypedDict, total=False):
    x: int
    y: int
    time: int  # seconds since the start
    assistingParticipantIds: list[int]


class WardEvent(TypedDict, total=False):
    x: int
    y: int
    time: int
    type: str


class ObjectiveSetup(TypedDict, total=False):
    """An epic objective of the match as seen from the player."""

    objective: str  # DRAGON · HORDE (void grubs) · RIFTHERALD · BARON_NASHOR · ATAKHAN
    time: int  # seconds
    team_objective: bool  # their team got it
    in_prep_zone: bool  # was near the pit in the previous 90 s
    contested: bool  # there were kills near the pit around the objective
    player_wards: int  # their own wards near the pit in the previous 90 s
    team_wards: int  # their team's wards (their own included) in that window


class LaneVisit(TypedDict, total=False):
    """Presence in a lane that is not their own before minute 14: a jungler's gank or a laner's roam."""

    lane: str  # TOP · MID · BOT
    time: int  # seconds, start of the visit
    takedowns: int  # their team's kills in that lane during the visit
    deaths: int  # their team's deaths in that lane during the visit
    structures: int  # enemy plates or turrets of that lane that fell right afterwards
    swing: int  # allied laners' gold + experience against the enemies': after - before


@dataclass(slots=True, frozen=True)
class PlayerRef:
    """The minimum needed to request a player's matches from Riot."""

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
    """Stats of ONE participant in ONE match.

    The field names match the columns persisted by the API, so
    the domain ↔ ORM mapping is a simple dump of attributes.
    """

    # ── Match ──────────────────────────────────────────────────────────────────
    match_id: str
    creation_time: datetime  # end of the match (gameCreation + gameDuration), UTC
    duration: int  # seconds
    queue_id: int = 420
    game_version: str = ""

    # ── Participant ─────────────────────────────────────────────────────────────
    puuid: str = ""
    participant_id: int = 0
    team_id: int = 0
    player_role: str = "UNKNOWN"
    champion: str = ""
    win: bool = False

    # ── Combat ───────────────────────────────────────────────────────────────────
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    kill_participation: float = 0.0  # 0-100
    vision: int = 0
    damage: int = 0
    gold: int = 0
    total_cs: int = 0
    damage_share: float = 0.0  # 0-100

    # ── Team objectives ────────────────────────────────────────────────────────
    first_dragon: bool = False
    void_grubs: bool = False  # 2+ void grubs
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

    # ── Advanced metrics ───────────────────────────────────────────────────────
    solo_kills: int = 0
    damage_structures: int = 0
    gold_share: float = 0.0
    enemy_jg_monsters: int = 0  # CS in the enemy jungle (each camp gives 4)
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
    fullclear_time: int | None = None
    timeline_enriched: bool = False
    timeline_version: int = 0  # see TIMELINE_VERSION

    # ── Impact by role (timeline version 2) ────────────────────────────────────
    turret_plates: int = 0
    wards_killed: int = 0
    early_takedowns: int = 0  # kills + assists before minute 14
    early_team_kills: int = 0  # their team's kills before minute 14
    objective_setups: list[ObjectiveSetup] = field(default_factory=list)
    lane_visits: list[LaneVisit] = field(default_factory=list)

    # ── Role Quests (season 26) ─────────────────────────────────────────────
    role_bound_item: int = 0
    quest_completed: bool = False
    quest_completion_time: int | None = None
    enemy_quest_completion_time: int | None = None
    quest_completion_time_diff: int | None = None

    # ── WPA (timeline version 4; 5 adds the why of each event; 6 makes it neutral), see metrics/wpa.py ──
    wpa_events: list[dict[str, Any]] = field(default_factory=list)
    wp_curve: list[float] = field(default_factory=list)  # their team's WP per minute, 0-100
    wpa_total: float | None = None
    wpa_grade: int | None = None

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


# Fields computed by the timeline enrichment. If a match is downloaded
# again, these are the ones to refresh in the persisted row.
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
    "timeline_enriched",
    "timeline_version",
    "enemy_jg_monsters",  # comes from the match, not from the timeline: fixed in version 3
    "turret_plates",
    "wards_killed",
    "early_takedowns",
    "early_team_kills",
    "objective_setups",
    "lane_visits",
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
    "wpa_events",
    "wp_curve",
    "wpa_total",
    "wpa_grade",
)
