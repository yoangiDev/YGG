"""Performance radar normalised by role.

Each axis is brought to 0-100 so that the Challenger average sits at 80 on all of them and
the radar comes out balanced:

- Positives (CS/min, vision, KDA, damage %, Dmg/Gold): 0 → 0 and the Challenger
  average / 0.8 → 100. Dmg/Gold is the team's damage % ÷ the team's gold
  %.
- Deaths: compared with the role's Challenger average. Dying as much as a
  Challenger is worth 80, half as much 100 and triple 0.

Each league's references (the polygons that can be overlaid) are the
means measured in the 16.19 harvest (benchmarks.py): what a player of that
league really does, not the target.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ygg_core.domain.participant import ParticipantStats
from ygg_core.metrics.benchmarks import CHALLENGER_BENCHMARKS, RANKS
from ygg_core.metrics.benchmarks import average as rank_average

LANE_PHASE_SEC = 840  # 14 minutes

RADAR_AXES: tuple[str, ...] = (
    "CS/Min",
    "KDA",
    "Dmg Share",
    "Dmg/Gold",
    "Deaths/Game",
    "Laning Deaths",
    "Post-14 Deaths",
)
RADAR_AXES_SUPPORT: tuple[str, ...] = ("Vision/Min", *RADAR_AXES[1:])

DEATH_AXES: frozenset[str] = frozenset({"Deaths/Game", "Laning Deaths", "Post-14 Deaths"})
CHALLENGER_SCORE = 80.0
# With triple the deaths of a Challenger the axis reaches 0 (and with half, 100).
DEATHS_ZERO_AT = 3.0

# benchmarks.py metric behind each axis (the KDA, apart: it is aggregated like the player's).
_AXIS_METRIC: dict[str, str] = {
    "CS/Min": "cs_per_min",
    "Vision/Min": "vision_per_min",
    "Dmg Share": "damage_share",
    "Dmg/Gold": "efficiency",
    "Deaths/Game": "deaths",
    "Laning Deaths": "laning_deaths",
    "Post-14 Deaths": "post14_deaths",
}


def _rank_radar(role: str, rank: str) -> dict[str, float]:
    """A league's averages on each axis of the role.

    The KDA is aggregated like the player's (`pooled_kda`): mean kills + assists over mean deaths. The
    mean of each match's KDA would shoot up with matches that have no deaths.
    """
    mean = {metric: rank_average(rank, role, metric) for metric in (*_AXIS_METRIC.values(), "kills", "assists")}
    values = {axis: round(mean[metric], 2) for axis, metric in _AXIS_METRIC.items()}
    values["KDA"] = round((mean["kills"] + mean["assists"]) / max(mean["deaths"], 1), 2)
    axes = RADAR_AXES_SUPPORT if role == "SUPPORT" else RADAR_AXES
    return {axis: values[axis] for axis in axes}


RADAR_RANK_BENCHMARKS: dict[str, dict[str, dict[str, float]]] = {
    role: {rank: _rank_radar(role, rank) for rank in RANKS} for role in CHALLENGER_BENCHMARKS
}

# Ceilings of the positive metrics: the Challenger average / 0.8, so that a Challenger sits at 80 as in deaths.
RADAR_MAX_POSITIVE: dict[str, dict[str, float]] = {
    axis: {
        role: round(RADAR_RANK_BENCHMARKS[role]["CHALLENGER"][axis] / 0.8, 2)
        for role in CHALLENGER_BENCHMARKS
        if axis in RADAR_RANK_BENCHMARKS[role]["CHALLENGER"]
    }
    for axis in ("CS/Min", "Vision/Min", "KDA", "Dmg Share", "Dmg/Gold")
}


def radar_axes(role: str) -> list[str]:
    return list(RADAR_AXES_SUPPORT if role == "SUPPORT" else RADAR_AXES)


def rank_benchmarks(role: str) -> dict[str, dict[str, float]]:
    return RADAR_RANK_BENCHMARKS.get(role, RADAR_RANK_BENCHMARKS["MID"])


def normalize_radar_metric(key: str, value: float, role: str) -> float:
    """Normalise to 0-100 (clamped); see the module docstring."""
    if key in DEATH_AXES:
        challenger = rank_benchmarks(role)["CHALLENGER"].get(key, 0.0)
        if challenger <= 0:
            return 0.0
        ratio = float(value) / challenger
        score = CHALLENGER_SCORE * (DEATHS_ZERO_AT - ratio) / (DEATHS_ZERO_AT - 1)
        return round(max(0.0, min(100.0, score)), 1)
    caps = RADAR_MAX_POSITIVE.get(key, {})
    cap = caps.get(role, caps.get("MID", 0.0))
    if cap <= 0:
        return 0.0
    return round(max(0.0, min(float(value), cap)) / cap * 100.0, 1)


# ── Per-match metrics ──────────────────────────────────────────────────────────


def match_cs_min(p: ParticipantStats) -> float:
    return p.total_cs / (p.duration / 60) if p.duration else 0.0


def match_vision_min(p: ParticipantStats) -> float:
    return p.vision / (p.duration / 60) if p.duration else 0.0


def laning_deaths(p: ParticipantStats) -> int:
    return sum(1 for d in (p.death_events or []) if d.get("time", 0) < LANE_PHASE_SEC)


def post14_deaths(p: ParticipantStats) -> int:
    return sum(1 for d in (p.death_events or []) if d.get("time", 0) >= LANE_PHASE_SEC)


def average(
    participants: Sequence[ParticipantStats],
    extractor: Callable[[ParticipantStats], float | int | None],
) -> float:
    values = [v for v in (extractor(p) for p in participants) if v is not None]
    return round(sum(values) / len(values), 2) if values else 0.0


def pooled_kda(participants: Sequence[ParticipantStats]) -> float:
    """KDA of the period: (kills + assists) / deaths, all summed.

    The mean of each match's KDA shoots up with matches that have no deaths,
    which count whole kills + assists.
    """
    kills_assists = sum(p.kills + p.assists for p in participants)
    deaths = sum(p.deaths for p in participants)
    return round(kills_assists / max(deaths, 1), 2)


def efficiency(participants: Sequence[ParticipantStats]) -> float:
    """Team damage % ÷ team gold %: how much damage it gets out of its share of the gold.

    Raw damage ÷ raw gold gives 1.5-2 to almost anyone and tells no one apart.
    """
    dmg_share = average(participants, lambda p: p.damage_share)
    gold_share = average(participants, lambda p: p.gold_share)
    return round(dmg_share / gold_share, 2) if gold_share > 0 else 0.0


def build_radar_values(participants: Sequence[ParticipantStats], role: str) -> dict[str, float]:
    if role == "SUPPORT":
        farm_key, farm_value = "Vision/Min", average(participants, match_vision_min)
    else:
        farm_key, farm_value = "CS/Min", average(participants, match_cs_min)
    return {
        farm_key: farm_value,
        "KDA": pooled_kda(participants),
        "Dmg Share": average(participants, lambda p: p.damage_share),
        "Dmg/Gold": efficiency(participants),
        "Deaths/Game": average(participants, lambda p: p.deaths),
        "Laning Deaths": average(participants, laning_deaths),
        "Post-14 Deaths": average(participants, post14_deaths),
    }
