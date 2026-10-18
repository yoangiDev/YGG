"""Enrichment of ParticipantStats with the match timeline."""

from __future__ import annotations

from typing import Any

from ygg_core.domain.participant import TIMELINE_VERSION, DeathEvent, ParticipantStats, WardEvent
from ygg_core.domain.roles import lane_opponent_id, role_from_position
from ygg_core.metrics.timeline_grade import timeline_grades
from ygg_core.metrics.wpa import wpa_report
from ygg_core.metrics.wpa_model import MODEL
from ygg_core.timeline.map_zones import is_bot_lane, is_mid_lane, is_top_lane
from ygg_core.timeline.objectives import compute_objective_vision_score
from ygg_core.timeline.quests import apply_role_quest_stats
from ygg_core.timeline.role_impact import (
    count_turret_plates,
    count_wards_killed,
    early_kill_counts,
    extract_lane_visits,
    extract_objective_setups,
)

JsonDict = dict[str, Any]

LANE_PHASE_MS = 14 * 60 * 1000
EARLY_GANK_WINDOW_MS = 10 * 60 * 1000
FULLCLEAR_CS = 24
FULLCLEAR_LEVEL = 4


def _frames(timeline: JsonDict) -> list[JsonDict]:
    frames: list[JsonDict] = timeline.get("info", {}).get("frames", [])
    return frames


def _frame_at_minute(timeline: JsonDict, minute: int) -> JsonDict | None:
    frames = _frames(timeline)
    if not frames:
        return None
    return frames[minute] if len(frames) > minute else frames[-1]


# ── Differentials against the lane opponent ───────────────────────────────────


def timeline_diff(timeline: JsonDict, participant_id: int, minute: int, stat: str) -> int:
    frame = _frame_at_minute(timeline, minute)
    if frame is None:
        return 0
    p_frames = frame.get("participantFrames", {})
    player = p_frames.get(str(participant_id), {}).get(stat, 0)
    opponent = p_frames.get(str(lane_opponent_id(participant_id)), {}).get(stat, 0)
    return int(player - opponent)


def cs_at_minute(timeline: JsonDict, participant_id: int, minute: int) -> dict[str, int]:
    frame = _frame_at_minute(timeline, minute)
    if frame is None:
        return {"player": 0, "opponent": 0, "diff": 0}
    p_frames = frame.get("participantFrames", {})

    def _cs(data: JsonDict) -> int:
        return int(data.get("minionsKilled", 0) + data.get("jungleMinionsKilled", 0))

    player = _cs(p_frames.get(str(participant_id), {}))
    opponent = _cs(p_frames.get(str(lane_opponent_id(participant_id)), {}))
    return {"player": player, "opponent": opponent, "diff": player - opponent}


# ── Spatial events ────────────────────────────────────────────────────────────


def extract_death_events(timeline: JsonDict, participant_id: int) -> list[DeathEvent]:
    deaths: list[DeathEvent] = []
    for frame in _frames(timeline):
        for event in frame.get("events", []):
            if event.get("type") != "CHAMPION_KILL" or event.get("victimId") != participant_id:
                continue
            position = event.get("position", {})
            if position:
                deaths.append(
                    DeathEvent(
                        x=position.get("x", 0),
                        y=position.get("y", 0),
                        time=event.get("timestamp", 0) // 1000,
                        assistingParticipantIds=event.get("assistingParticipantIds", []),
                    )
                )
    return deaths


def extract_ward_events(timeline: JsonDict, participant_id: int) -> list[WardEvent]:
    wards: list[WardEvent] = []
    pid_key = str(participant_id)
    for frame in _frames(timeline):
        participant_frames = frame.get("participantFrames", {})
        for event in frame.get("events", []):
            if event.get("type") != "WARD_PLACED" or event.get("creatorId") != participant_id:
                continue
            # match-v5 WARD_PLACED usually comes without `position`: the participant's
            # position in that same frame is used.
            position = event.get("position") or (participant_frames.get(pid_key) or {}).get(
                "position"
            )
            if not position:
                continue
            wards.append(
                WardEvent(
                    x=position.get("x", 0),
                    y=position.get("y", 0),
                    time=event.get("timestamp", 0) // 1000,
                    type=event.get("wardType", "UNKNOWN"),
                )
            )
    return wards


def extract_fullclear_time(timeline: JsonDict, participant_id: int) -> int | None:
    """First second at which the jungler reaches 24 farm or level 4."""
    for frame in _frames(timeline):
        data = frame.get("participantFrames", {}).get(str(participant_id), {})
        if not data:
            continue
        farm = data.get("minionsKilled", 0) + data.get("jungleMinionsKilled", 0)
        if farm >= FULLCLEAR_CS or data.get("level", 0) >= FULLCLEAR_LEVEL:
            return int(frame.get("timestamp", 0) // 1000)
    return None


# ── Map zones (ygg_core.timeline.map_zones) ────────────────────────────────────


_LANE_CHECKS = {"TOP": is_top_lane, "MID": is_mid_lane, "ADC": is_bot_lane}


# ── Event-based metrics ────────────────────────────────────────────────────────


def count_solo_kills(timeline: JsonDict, participant_id: int) -> int:
    return sum(
        1
        for frame in _frames(timeline)
        for event in frame.get("events", [])
        if event.get("type") == "CHAMPION_KILL"
        and event.get("killerId") == participant_id
        and not event.get("assistingParticipantIds")
    )


def count_roaming_proactivity(timeline: JsonDict, participant_id: int) -> int:
    """Kills/assists before minute 14 outside the central lane."""
    count = 0
    for frame in _frames(timeline):
        for event in frame.get("events", []):
            if event.get("type") != "CHAMPION_KILL" or event.get("timestamp", 0) >= LANE_PHASE_MS:
                continue
            involved = event.get("killerId") == participant_id or participant_id in event.get(
                "assistingParticipantIds", []
            )
            position = event.get("position", {})
            if involved and position and not is_mid_lane(position.get("x", 0), position.get("y", 0)):
                count += 1
    return count


def count_early_gank_deaths(
    timeline: JsonDict,
    participant_id: int,
    player_role: str | None,
    enemy_ids: dict[str, int],
) -> int:
    """Deaths before minute 10, in their own lane, to an enemy gank.

    It counts as a gank when a helper (enemy jungler or support;
    only the jungler in bot) and a lane opponent take part at the same time.
    """
    in_lane = _LANE_CHECKS.get(player_role or "")
    if in_lane is None:
        return 0

    jungle, support = enemy_ids.get("JUNGLE"), enemy_ids.get("SUPPORT")
    if player_role == "ADC":
        helpers, rivals = {jungle}, {enemy_ids.get("ADC"), support}
    else:
        helpers, rivals = {jungle, support}, {enemy_ids.get(player_role or "")}
    helpers.discard(None)
    rivals.discard(None)

    count = 0
    for frame in _frames(timeline):
        for event in frame.get("events", []):
            if event.get("type") != "CHAMPION_KILL" or event.get("victimId") != participant_id:
                continue
            if event.get("timestamp", 0) >= EARLY_GANK_WINDOW_MS:
                continue
            position = event.get("position", {})
            if not position or not in_lane(position.get("x", 0), position.get("y", 0)):
                continue
            killers = {event.get("killerId"), *event.get("assistingParticipantIds", [])}
            if helpers & killers and rivals & killers:
                count += 1
    return count


def enemy_lane_ids(participants: list[JsonDict], player_team_id: int) -> dict[str, int]:
    """Role → participantId of the enemy team."""
    ids: dict[str, int] = {}
    for participant in participants:
        if participant["teamId"] == player_team_id:
            continue
        role = role_from_position(participant.get("teamPosition"))
        if role != "UNKNOWN":
            ids[role] = participant["participantId"]
    return ids


# ── Orchestration ──────────────────────────────────────────────────────────────


def enrich_with_timeline(
    stats: ParticipantStats,
    timeline: JsonDict,
    participant_id: int,
    *,
    player_role: str | None = None,
    enemy_ids: dict[str, int] | None = None,
    participants: list[JsonDict] | None = None,
) -> None:
    """Fills in `stats` with all the fields derived from the timeline."""
    stats.xp_diff_8 = timeline_diff(timeline, participant_id, 8, "xp")
    stats.xp_diff_14 = timeline_diff(timeline, participant_id, 14, "xp")
    stats.gold_diff_8 = timeline_diff(timeline, participant_id, 8, "totalGold")
    stats.gold_diff_14 = timeline_diff(timeline, participant_id, 14, "totalGold")
    stats.gold_diff_25 = timeline_diff(timeline, participant_id, 25, "totalGold")

    cs_8 = cs_at_minute(timeline, participant_id, 8)
    cs_14 = cs_at_minute(timeline, participant_id, 14)
    cs_25 = cs_at_minute(timeline, participant_id, 25)
    stats.cs_8, stats.cs_diff_8 = cs_8["player"], cs_8["diff"]
    stats.cs_14, stats.cs_diff_14 = cs_14["player"], cs_14["diff"]
    stats.cs_25, stats.cs_diff_25 = cs_25["player"], cs_25["diff"]

    stats.death_events = extract_death_events(timeline, participant_id)
    stats.ward_events = extract_ward_events(timeline, participant_id)
    stats.solo_kills = count_solo_kills(timeline, participant_id)
    stats.roaming_proactivity = count_roaming_proactivity(timeline, participant_id)
    stats.objective_vision_score = compute_objective_vision_score(
        stats.ward_events, timeline=timeline
    )

    stats.early_gank_deaths = count_early_gank_deaths(
        timeline, participant_id, player_role, enemy_ids or {}
    )
    stats.fullclear_time = (
        extract_fullclear_time(timeline, participant_id) if player_role == "JUNGLE" else None
    )

    stats.turret_plates = count_turret_plates(timeline, participant_id)
    stats.wards_killed = count_wards_killed(timeline, participant_id)

    if participants:
        apply_role_quest_stats(
            stats,
            timeline,
            participant_id,
            player_role=player_role,
            participants=participants,
        )
        # Impact by role: needs to know the team and role of all 10 players.
        stats.objective_setups = extract_objective_setups(timeline, participants, participant_id)
        stats.lane_visits = extract_lane_visits(timeline, participants, participant_id)
        stats.early_takedowns, stats.early_team_kills = early_kill_counts(timeline, participants, participant_id)
        stats.timeline_version = TIMELINE_VERSION

    stats.timeline_enriched = True


def apply_timeline(
    stats: ParticipantStats,
    match_data: JsonDict,
    timeline: JsonDict,
    puuid: str,
) -> None:
    """Enriches `stats`, locating the player and their opponents in the match payload."""
    participants: list[JsonDict] = match_data["info"]["participants"]
    player = next(p for p in participants if p["puuid"] == puuid)
    role = role_from_position(player.get("teamPosition"))
    stats.role_bound_item = player.get("roleBoundItem") or 0

    enrich_with_timeline(
        stats,
        timeline,
        player["participantId"],
        player_role=role,
        enemy_ids=enemy_lane_ids(participants, player["teamId"]),
        participants=participants,
    )
    report = wpa_report(match_data, timeline, puuid, MODEL)
    if report is not None:
        stats.wpa_events = [dict(event) for event in report.events]
        stats.wp_curve = report.wp_curve
        stats.wpa_total = report.total
        # the WPA curve and events stay; the grade is the one that predicts the analysis one (metrics/timeline_grade.py)
        stats.wpa_grade = timeline_grades(match_data, timeline).get(puuid, report.grade)
