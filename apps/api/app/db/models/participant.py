from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.match import Match


def _int() -> Mapped[int]:
    return mapped_column(default=0, server_default=text("0"))


def _float() -> Mapped[float]:
    return mapped_column(default=0.0, server_default=text("0"))


def _bool() -> Mapped[bool]:
    return mapped_column(default=False, server_default=text("false"))


def _events() -> Mapped[list[dict[str, Any]]]:
    return mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))


class MatchParticipant(Base):
    """Stats of ONE player in ONE match.

    (match_id, puuid) is unique: two registered players who share a
    match each have their own row. `creation_time` is duplicated from `matches`
    (it is immutable) so that a player's history is served with an index
    (puuid, creation_time) without a join; a btree can be walked backwards for the DESC.
    """

    __tablename__ = "match_participants"
    __table_args__ = (
        UniqueConstraint("match_id", "puuid", name="uq_match_participants_match_puuid"),
        Index("ix_match_participants_puuid_creation_time", "puuid", "creation_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id", ondelete="CASCADE"))
    puuid: Mapped[str] = mapped_column(String(100))
    creation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # ── Participant ─────────────────────────────────────────────────────────────
    participant_id: Mapped[int] = _int()  # 1-10 in match-v5; 0 in migrated rows
    team_id: Mapped[int] = _int()
    player_role: Mapped[str] = mapped_column(String(20), default="UNKNOWN", server_default="UNKNOWN")
    champion: Mapped[str] = mapped_column(String(50))
    win: Mapped[bool]

    # ── Combat ───────────────────────────────────────────────────────────────────
    kills: Mapped[int] = _int()
    deaths: Mapped[int] = _int()
    assists: Mapped[int] = _int()
    kill_participation: Mapped[float] = _float()
    vision: Mapped[int] = _int()
    damage: Mapped[int] = _int()
    gold: Mapped[int] = _int()
    total_cs: Mapped[int] = _int()
    damage_share: Mapped[float] = _float()

    # ── Team objectives ────────────────────────────────────────────────────────
    first_dragon: Mapped[bool] = _bool()
    void_grubs: Mapped[bool] = _bool()
    herald: Mapped[bool] = _bool()

    # ── Build ──────────────────────────────────────────────────────────────────
    summoner1_id: Mapped[int] = _int()
    summoner2_id: Mapped[int] = _int()
    item0: Mapped[int] = _int()
    item1: Mapped[int] = _int()
    item2: Mapped[int] = _int()
    item3: Mapped[int] = _int()
    item4: Mapped[int] = _int()
    item5: Mapped[int] = _int()
    item6: Mapped[int] = _int()
    primary_rune: Mapped[int] = _int()
    secondary_tree: Mapped[int] = _int()

    # ── Advanced metrics ───────────────────────────────────────────────────────
    solo_kills: Mapped[int] = _int()
    damage_structures: Mapped[int] = _int()
    gold_share: Mapped[float] = _float()
    enemy_jg_monsters: Mapped[int] = _int()
    control_wards: Mapped[int] = _int()
    roaming_proactivity: Mapped[int] = _int()
    objective_vision_score: Mapped[int] = _int()
    early_gank_deaths: Mapped[int] = _int()

    # ── Timeline ───────────────────────────────────────────────────────────────
    cs_8: Mapped[int] = _int()
    cs_14: Mapped[int] = _int()
    cs_25: Mapped[int] = _int()
    cs_diff_8: Mapped[int] = _int()
    cs_diff_14: Mapped[int] = _int()
    cs_diff_25: Mapped[int] = _int()
    gold_diff_8: Mapped[int] = _int()
    gold_diff_14: Mapped[int] = _int()
    gold_diff_25: Mapped[int] = _int()
    xp_diff_8: Mapped[int] = _int()
    xp_diff_14: Mapped[int] = _int()
    # JSONB: they are read whole to draw the heatmaps. If they had to be
    # queried by coordinate or minute, they would move to an events table.
    death_events: Mapped[list[dict[str, Any]]] = _events()
    ward_events: Mapped[list[dict[str, Any]]] = _events()
    fullclear_time: Mapped[int | None]
    timeline_enriched: Mapped[bool] = _bool()
    timeline_version: Mapped[int] = _int()  # rows of an earlier version are downloaded again

    # ── Impact by role (timeline version 2) ────────────────────────────────────
    turret_plates: Mapped[int] = _int()
    wards_killed: Mapped[int] = _int()
    early_takedowns: Mapped[int] = _int()
    early_team_kills: Mapped[int] = _int()
    objective_setups: Mapped[list[dict[str, Any]]] = _events()
    lane_visits: Mapped[list[dict[str, Any]]] = _events()

    # ── Role Quests (season 26) ─────────────────────────────────────────────
    role_bound_item: Mapped[int] = _int()
    quest_completed: Mapped[bool] = _bool()
    quest_completion_time: Mapped[int | None]
    enemy_quest_completion_time: Mapped[int | None]
    quest_completion_time_diff: Mapped[int | None]

    # ── WPA (timeline version 4), only in matches analysed with a timeline ─────
    wpa_events: Mapped[list[dict[str, Any]]] = _events()
    wp_curve: Mapped[list[float]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    wpa_total: Mapped[float | None]
    wpa_grade: Mapped[int | None]

    match: Mapped[Match] = relationship(back_populates="participants", lazy="joined", innerjoin=True)

    # Match data exposed on the participant (MatchResponse reads them from here).
    @property
    def duration(self) -> int:
        return self.match.duration if self.match is not None else 0

    @property
    def queue_id(self) -> int:
        return self.match.queue_id if self.match is not None else 420

    @property
    def game_version(self) -> str:
        return self.match.game_version if self.match is not None else ""
