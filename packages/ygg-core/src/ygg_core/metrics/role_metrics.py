"""Per-role metrics computed from the stored facts of each match.

What counts as a successful gank or roam is decided here, not when the match is downloaded:
it can be tuned without asking Riot for anything again.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ygg_core.domain.participant import LaneVisit, ParticipantStats
from ygg_core.timeline.map_zones import ROLE_LANE, in_base, lane_at

LANE_PHASE_SEC = 840  # minute 14
# Version of the timeline that added ganks, roams and objectives: later ones have them too.
ROLE_IMPACT_VERSION = 2

# Gold + experience that a visit with no deaths has to leave in the lane to count as a success.
SWING_SUCCESS = 250

Summary = Callable[[Sequence[ParticipantStats]], float | None]


def has_role_timeline(p: ParticipantStats) -> bool:
    """Does the match have the per-role metrics (timeline of the version that added them or later)?"""
    return p.timeline_enriched and p.timeline_version >= ROLE_IMPACT_VERSION


def visit_successful(visit: LaneVisit) -> bool:
    """A gank or roam that went well: won the exchange, took down a structure or left the lane ahead.

    With no kills it also counts if the lane ends up winning at least SWING_SUCCESS of gold +
    experience: covering a recall without losing waves, taking the enemy's health down so that your
    laner plays safe or pushing the wave to go to the river all look like this in the timeline.
    """
    takedowns, deaths = visit.get("takedowns", 0), visit.get("deaths", 0)
    if takedowns != deaths:
        return takedowns > deaths
    return visit.get("structures", 0) > 0 or visit.get("swing", 0) >= SWING_SUCCESS


# ── Per-match counts ───────────────────────────────────────────────────────────


def visits(p: ParticipantStats) -> int:
    return len(p.lane_visits)


def successful_visits(p: ParticipantStats) -> int:
    return sum(1 for visit in p.lane_visits if visit_successful(visit))


def visit_swing(p: ParticipantStats) -> int:
    return sum(visit.get("swing", 0) for visit in p.lane_visits)


def objectives(p: ParticipantStats) -> int:
    return len(p.objective_setups)


def objectives_prepared(p: ParticipantStats) -> int:
    return sum(1 for setup in p.objective_setups if setup.get("in_prep_zone"))


def objectives_secured(p: ParticipantStats) -> int:
    return sum(1 for setup in p.objective_setups if setup.get("team_objective"))


def objectives_contested(p: ParticipantStats) -> int:
    return sum(1 for setup in p.objective_setups if setup.get("contested"))


def player_objective_wards(p: ParticipantStats) -> int:
    return sum(setup.get("player_wards", 0) for setup in p.objective_setups)


def team_objective_wards(p: ParticipantStats) -> int:
    return sum(setup.get("team_wards", 0) for setup in p.objective_setups)


def solo_deaths(p: ParticipantStats) -> int:
    return sum(1 for death in p.death_events or [] if not death.get("assistingParticipantIds"))


def early_deaths_in_lanes(p: ParticipantStats) -> int:
    """Deaths before minute 14 inside a lane (the jungler dying in a gank)."""
    return sum(
        1
        for death in p.death_events or []
        if death.get("time", 0) < LANE_PHASE_SEC and lane_at(death.get("x", 0), death.get("y", 0)) is not None
    )


def early_deaths_away_from_lane(p: ParticipantStats, role: str) -> int:
    """Deaths before minute 14 outside their lane and the bases (a laner dying in a roam)."""
    own_lane = ROLE_LANE.get(role)
    return sum(
        1
        for death in p.death_events or []
        if death.get("time", 0) < LANE_PHASE_SEC
        and not in_base(death.get("x", 0), death.get("y", 0))
        and lane_at(death.get("x", 0), death.get("y", 0)) != own_lane
    )


# ── Ratios that are summed match by match ──────────────────────────────────────


def pooled_ratio(
    numerator: Callable[[ParticipantStats], float],
    denominator: Callable[[ParticipantStats], float],
    *,
    percent: bool = False,
) -> Summary:
    """Ratio over several matches, summing before dividing: a match with 5 ganks weighs more than one with 1."""

    def summarize(games: Sequence[ParticipantStats]) -> float | None:
        usable = [p for p in games if has_role_timeline(p)]
        total = sum(denominator(p) for p in usable)
        if total <= 0:
            return None
        value = sum(numerator(p) for p in usable) / total
        return round(value * 100 if percent else value, 2)

    return summarize


visit_success_rate = pooled_ratio(successful_visits, visits, percent=True)
swing_per_visit = pooled_ratio(visit_swing, visits)
setup_presence_rate = pooled_ratio(objectives_prepared, objectives, percent=True)
objective_secure_rate = pooled_ratio(objectives_secured, objectives, percent=True)
objective_contest_rate = pooled_ratio(objectives_contested, objectives, percent=True)
player_wards_per_objective = pooled_ratio(player_objective_wards, objectives)
team_wards_per_objective = pooled_ratio(team_objective_wards, objectives)
early_kill_participation = pooled_ratio(lambda p: p.early_takedowns, lambda p: p.early_team_kills, percent=True)
