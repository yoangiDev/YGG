"""Impact by role from the timeline: visits to other lanes, epic objectives and structures.

The timeline gives each player's position once per minute and the events with
their timestamp. A visit is detected when the player is in a lane that is
not their own near an enemy of that lane, or when they take part in a kill (or
die) in it. Only the facts of each visit are stored here; what counts as a
success is decided in ygg_core.metrics.role_metrics, without downloading anything again.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ygg_core.domain.participant import LaneVisit, ObjectiveSetup
from ygg_core.domain.roles import role_from_position
from ygg_core.timeline.map_zones import LANE_ROLES, ROLE_LANE, lane_at
from ygg_core.timeline.objectives import (
    OBJECTIVE_PIT_POSITIONS,
    OBJECTIVE_PREP_WINDOW_MS,
    within_objective_radius,
)

JsonDict = dict[str, Any]
Point = tuple[float, float]

LANE_PHASE_MS = 14 * 60 * 1000
FIRST_VISIT_MS = 2 * 60 * 1000  # before that they only leave the base
PRESENCE_RADIUS = 2000  # distance to an enemy of the lane to count as present
VISIT_MERGE_MS = 60_000  # consecutive detections in the same lane are a single visit
VISIT_BEFORE_MS = 30_000
VISIT_AFTER_MS = 90_000
STRUCTURE_AFTER_MS = 120_000  # the plates fall a little after the gank
OBJECTIVE_CONTEST_AFTER_MS = 30_000
HORDE_MERGE_MS = 60_000  # the grubs die one at a time: a group is one objective

EPIC_OBJECTIVES = ("DRAGON", "HORDE", "RIFTHERALD", "BARON_NASHOR", "ATAKHAN")
_OBJECTIVE_PIT = {"DRAGON": "DRAGON", "HORDE": "BARON_NASHOR", "RIFTHERALD": "BARON_NASHOR", "BARON_NASHOR": "BARON_NASHOR"}
_LANE_TYPES = {"TOP_LANE": "TOP", "MID_LANE": "MID", "BOT_LANE": "BOT"}


def _frames(timeline: JsonDict) -> list[JsonDict]:
    frames: list[JsonDict] = timeline.get("info", {}).get("frames", [])
    return frames


def _events(timeline: JsonDict) -> Iterator[tuple[JsonDict, JsonDict]]:
    for frame in _frames(timeline):
        for event in frame.get("events", []):
            yield frame, event


def _position(data: JsonDict | None) -> Point | None:
    position = (data or {}).get("position") or {}
    x, y = position.get("x"), position.get("y")
    if not x and not y:
        return None
    return float(x or 0), float(y or 0)


def _near(a: Point, b: Point, radius: float) -> bool:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 <= radius * radius


def _frame_position(frame: JsonDict, participant_id: int) -> Point | None:
    return _position(frame.get("participantFrames", {}).get(str(participant_id)))


def _frame_at(frames: list[JsonDict], ms: int) -> JsonDict | None:
    """The frame of the minute in progress at `ms` (the last one if the match ended earlier)."""
    if not frames:
        return None
    return frames[min(len(frames) - 1, max(0, ms // 60_000))]


class _Teams:
    """Team and role of each participantId in the match."""

    def __init__(self, participants: list[JsonDict]) -> None:
        self.team: dict[int, int] = {int(p["participantId"]): int(p["teamId"]) for p in participants}
        self.role: dict[int, str] = {
            int(p["participantId"]): role_from_position(p.get("teamPosition")) for p in participants
        }

    def lane_players(self, lane: str, team_id: int) -> list[int]:
        roles = LANE_ROLES[lane]
        return [pid for pid, role in self.role.items() if role in roles and self.team[pid] == team_id]


def _lane_score(frame: JsonDict, participant_ids: list[int]) -> int:
    frames = frame.get("participantFrames", {})
    return sum(
        int((frames.get(str(pid)) or {}).get("totalGold", 0)) + int((frames.get(str(pid)) or {}).get("xp", 0))
        for pid in participant_ids
    )


# ── Visits to other lanes ──────────────────────────────────────────────────────


def _visit_detections(timeline: JsonDict, teams: _Teams, participant_id: int) -> list[tuple[int, str]]:
    team_id = teams.team[participant_id]
    own_lane = ROLE_LANE.get(teams.role.get(participant_id, ""))
    detections: list[tuple[int, str]] = []

    for frame in _frames(timeline):
        ts = int(frame.get("timestamp", 0))
        me = _frame_position(frame, participant_id)
        if not FIRST_VISIT_MS <= ts < LANE_PHASE_MS or me is None:
            continue
        lane = lane_at(*me)
        if lane is None or lane == own_lane:
            continue
        rivals = (_frame_position(frame, pid) for pid in teams.lane_players(lane, 300 - team_id))
        if any(rival is not None and _near(me, rival, PRESENCE_RADIUS) for rival in rivals):
            detections.append((ts, lane))

    for _, event in _events(timeline):
        ts = int(event.get("timestamp", 0))
        if event.get("type") != "CHAMPION_KILL" or ts >= LANE_PHASE_MS:
            continue
        involved = participant_id in (event.get("killerId"), event.get("victimId"), *event.get("assistingParticipantIds", []))
        where = _position(event)
        if involved and where is not None and (lane := lane_at(*where)) is not None and lane != own_lane:
            detections.append((ts, lane))
    return sorted(detections)


def _visit(timeline: JsonDict, teams: _Teams, team_id: int, start: int, last: int, lane: str) -> LaneVisit:
    takedowns = deaths = structures = 0
    for _, event in _events(timeline):
        kind = event.get("type")
        ts = int(event.get("timestamp", 0))
        if kind == "CHAMPION_KILL" and start - VISIT_BEFORE_MS <= ts <= last + VISIT_AFTER_MS:
            where = _position(event)
            if where is None or lane_at(*where) != lane:
                continue
            takedowns += teams.team.get(int(event.get("killerId") or 0)) == team_id
            deaths += teams.team.get(int(event.get("victimId") or 0)) == team_id
        elif kind in ("TURRET_PLATE_DESTROYED", "BUILDING_KILL") and start <= ts <= last + STRUCTURE_AFTER_MS:
            owner = event.get("teamId")
            structures += _LANE_TYPES.get(str(event.get("laneType", ""))) == lane and owner is not None and owner != team_id

    frames = _frames(timeline)
    allies, rivals = teams.lane_players(lane, team_id), teams.lane_players(lane, 300 - team_id)
    before, after = _frame_at(frames, start), _frame_at(frames, last + STRUCTURE_AFTER_MS)
    swing = 0
    if before is not None and after is not None and allies and rivals:
        lead_after = _lane_score(after, allies) - _lane_score(after, rivals)
        lead_before = _lane_score(before, allies) - _lane_score(before, rivals)
        swing = lead_after - lead_before
    return LaneVisit(lane=lane, time=start // 1000, takedowns=takedowns, deaths=deaths, structures=structures, swing=swing)


def extract_lane_visits(timeline: JsonDict, participants: list[JsonDict], participant_id: int) -> list[LaneVisit]:
    """Ganks (jungler) or roams (laners) before minute 14, with what happened in each."""
    teams = _Teams(participants)
    team_id = teams.team.get(participant_id)
    if team_id is None:
        return []

    spans: list[tuple[int, int, str]] = []  # (start, last detection, lane)
    for ts, lane in _visit_detections(timeline, teams, participant_id):
        if spans and spans[-1][2] == lane and ts - spans[-1][1] <= VISIT_MERGE_MS:
            spans[-1] = (spans[-1][0], ts, lane)
        else:
            spans.append((ts, ts, lane))
    return [_visit(timeline, teams, team_id, start, last, lane) for start, last, lane in spans]


# ── Epic objectives ────────────────────────────────────────────────────────────


def _ward_position(frame: JsonDict, event: JsonDict) -> Point | None:
    """WARD_PLACED usually comes without a position: that of whoever places it in that frame is used."""
    return _position(event) or _frame_position(frame, int(event.get("creatorId") or 0))


def extract_objective_setups(timeline: JsonDict, participants: list[JsonDict], participant_id: int) -> list[ObjectiveSetup]:
    """Setup of each dragon, group of grubs, herald, baron and Atakhan."""
    teams = _Teams(participants)
    team_id = teams.team.get(participant_id)
    if team_id is None:
        return []

    frames = _frames(timeline)
    wards = [
        (int(event.get("timestamp", 0)), int(event.get("creatorId") or 0), where)
        for frame, event in _events(timeline)
        if event.get("type") == "WARD_PLACED" and (where := _ward_position(frame, event)) is not None
    ]
    kills = [
        (int(event.get("timestamp", 0)), where)
        for _, event in _events(timeline)
        if event.get("type") == "CHAMPION_KILL" and (where := _position(event)) is not None
    ]

    setups: list[ObjectiveSetup] = []
    last_horde = -2 * HORDE_MERGE_MS
    for _, event in _events(timeline):
        objective = str(event.get("monsterType", ""))
        if event.get("type") != "ELITE_MONSTER_KILL" or objective not in EPIC_OBJECTIVES:
            continue
        ts = int(event.get("timestamp", 0))
        if objective == "HORDE":
            merged = ts - last_horde <= HORDE_MERGE_MS
            last_horde = ts
            if merged:
                continue
        pit: Point | None = _position(event)
        if pit is None and objective in _OBJECTIVE_PIT:
            px, py = OBJECTIVE_PIT_POSITIONS[_OBJECTIVE_PIT[objective]]
            pit = (float(px), float(py))
        if pit is None:
            continue

        prep_start = ts - OBJECTIVE_PREP_WINDOW_MS
        nearby = [creator for time, creator, where in wards if prep_start <= time <= ts and within_objective_radius(*where, *pit)]
        present = any(
            prep_start <= int(frame.get("timestamp", 0)) <= ts
            and (me := _frame_position(frame, participant_id)) is not None
            and within_objective_radius(*me, *pit)
            for frame in frames
        )
        setups.append(
            ObjectiveSetup(
                objective=objective,
                time=ts // 1000,
                team_objective=event.get("killerTeamId") == team_id,
                in_prep_zone=present,
                contested=any(
                    prep_start <= time <= ts + OBJECTIVE_CONTEST_AFTER_MS and within_objective_radius(*where, *pit)
                    for time, where in kills
                ),
                player_wards=sum(1 for creator in nearby if creator == participant_id),
                team_wards=sum(1 for creator in nearby if teams.team.get(creator) == team_id),
            )
        )
    return setups


# ── Recuentos ──────────────────────────────────────────────────────────────────


def count_turret_plates(timeline: JsonDict, participant_id: int) -> int:
    return sum(
        1
        for _, event in _events(timeline)
        if event.get("type") == "TURRET_PLATE_DESTROYED" and event.get("killerId") == participant_id
    )


def count_wards_killed(timeline: JsonDict, participant_id: int) -> int:
    return sum(
        1 for _, event in _events(timeline) if event.get("type") == "WARD_KILL" and event.get("killerId") == participant_id
    )


def early_kill_counts(timeline: JsonDict, participants: list[JsonDict], participant_id: int) -> tuple[int, int]:
    """(player's kills + assists, their team's kills) before minute 14."""
    teams = _Teams(participants)
    team_id = teams.team.get(participant_id)
    takedowns = team_kills = 0
    for _, event in _events(timeline):
        if event.get("type") != "CHAMPION_KILL" or int(event.get("timestamp", 0)) >= LANE_PHASE_MS:
            continue
        if team_id is None or teams.team.get(int(event.get("killerId") or 0)) != team_id:
            continue
        team_kills += 1
        takedowns += participant_id == event.get("killerId") or participant_id in event.get("assistingParticipantIds", [])
    return takedowns, team_kills
