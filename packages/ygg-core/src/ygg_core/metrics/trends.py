"""Trends of a snapshot: each match in order, its moving average and, if there is one, the Challenger reference.

Each role has its four charts: the jungler, objective setup and vision
and ganks; the top, only kills, vision and map contribution; the support, participation,
roams and vision; mid and ADC, gold efficiency, damage and deaths. Which metrics are included
and their reference is decided here; the frontend only draws them.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from ygg_core.domain.participant import ParticipantStats
from ygg_core.metrics import role_metrics as rm
from ygg_core.metrics.aggregates import trend_window_size
from ygg_core.metrics.benchmarks import CHALLENGER_BENCHMARKS, average
from ygg_core.metrics.radar import (
    laning_deaths,
    match_cs_min,
    match_vision_min,
    post14_deaths,
    rank_benchmarks,
)

Extractor = Callable[[ParticipantStats], float | None]


@dataclass(slots=True)
class TrendGame:
    game_num: int
    match_id: str
    creation_time: datetime
    champion: str
    win: bool


@dataclass(slots=True)
class TrendSeries:
    key: str
    label: str
    unit: str  # "" · "%"
    digits: int
    signed: bool  # differences: shown with a sign
    challenger: float | None  # what is expected of a Challenger in the role (dotted line), if known
    values: list[float | None]  # one per match; None if the data is missing
    moving_average: list[float | None]


@dataclass(slots=True)
class TrendGroup:
    key: str
    label: str
    metrics: list[TrendSeries]


@dataclass(slots=True)
class SnapshotTrends:
    games: list[TrendGame]  # in chronological order
    groups: list[TrendGroup]


@dataclass(slots=True, frozen=True)
class TrendMetric:
    key: str
    label: str
    extract: Extractor
    challenger: float | None = None
    unit: str = ""
    digits: int = 1
    signed: bool = False
    # How a window of matches is summarised when the mean doesn't apply (ratios are summed).
    window_value: rm.Summary | None = None


def _timeline(extract: Callable[[ParticipantStats], float]) -> Extractor:
    """There is data only if the match was downloaded with the timeline."""
    return lambda p: float(extract(p)) if p.timeline_enriched else None


def _role_timeline(extract: Callable[[ParticipantStats], float]) -> Extractor:
    """There is data only if the match has the per-role metrics (see role_metrics.has_role_timeline)."""
    return lambda p: float(extract(p)) if rm.has_role_timeline(p) else None


def _ratio(key: str, label: str, summary: rm.Summary, *, unit: str = "", digits: int = 1, signed: bool = False) -> TrendMetric:
    return TrendMetric(key, label, lambda p: summary([p]), unit=unit, digits=digits, signed=signed, window_value=summary)


def _per_minute(value: Callable[[ParticipantStats], int]) -> Extractor:
    return lambda p: value(p) / (p.duration / 60) if p.duration else 0.0


def _efficiency(p: ParticipantStats) -> float | None:
    return p.damage_share / p.gold_share if p.gold_share else None


Group = tuple[str, str, list[TrendMetric]]


def trend_metrics(role: str) -> list[Group]:
    """The role's four charts.

    The Challenger references are the measured Challenger means in the role (benchmarks.py and the radar): what they
    really do, not the target; against the opponent, one Challenger against another comes out at 0. The new per-role
    metrics have no reference.
    """
    table_role = role if role in CHALLENGER_BENCHMARKS else "MID"
    radar = rank_benchmarks(role)["CHALLENGER"]

    def centre(metric: str) -> float:
        return round(average("CHALLENGER", table_role, metric), 2)

    deaths: Group = (
        "deaths",
        "Deaths",
        [
            TrendMetric("deaths", "Total", lambda p: p.deaths, radar["Deaths/Game"]),
            TrendMetric("laning_deaths", "Laning phase", _timeline(laning_deaths), radar["Laning Deaths"]),
            TrendMetric("mid_late_deaths", "Mid-late game", _timeline(post14_deaths), radar["Post-14 Deaths"]),
        ],
    )
    wards = [
        TrendMetric("wards_placed", "Wards placed", _timeline(lambda p: len(p.ward_events)), digits=0),
        TrendMetric("control_wards", "Control wards", lambda p: p.control_wards, digits=0),
        TrendMetric("wards_killed", "Wards destroyed", _role_timeline(lambda p: p.wards_killed), digits=0),
    ]

    if role == "JUNGLE":
        return [
            (
                "objective_setup",
                "Objective setup",
                [
                    _ratio("setup_presence", "Setup presence", rm.setup_presence_rate, unit="%", digits=0),
                    _ratio("objectives_secured", "Secured", rm.objective_secure_rate, unit="%", digits=0),
                    _ratio("objectives_contested", "Contested", rm.objective_contest_rate, unit="%", digits=0),
                ],
            ),
            (
                "objective_vision",
                "Vision before objectives",
                [
                    _ratio("wards_per_objective", "Your wards", rm.player_wards_per_objective),
                    _ratio("team_wards_per_objective", "Team wards", rm.team_wards_per_objective),
                    TrendMetric("control_wards", "Control wards", lambda p: p.control_wards, digits=0),
                ],
            ),
            (
                "ganks",
                "Ganks",
                [
                    TrendMetric("lane_visits", "Lane visits", _role_timeline(rm.visits), digits=0),
                    TrendMetric("successful_ganks", "Successful", _role_timeline(rm.successful_visits), digits=0),
                    _ratio("gank_success", "Success rate", rm.visit_success_rate, unit="%", digits=0),
                    _ratio("gank_swing", "Lane lead per gank", rm.swing_per_visit, digits=0, signed=True),
                    TrendMetric("gank_deaths", "Deaths ganking", _timeline(rm.early_deaths_in_lanes), digits=0),
                ],
            ),
            deaths,
        ]

    if role == "TOP":
        return [
            (
                "solo_kills",
                "Solo kills",
                [
                    TrendMetric("solo_kills", "Solo kills", _timeline(lambda p: p.solo_kills), digits=0),
                    TrendMetric("solo_deaths", "Solo deaths", _timeline(rm.solo_deaths), digits=0),
                    TrendMetric("turret_plates", "Turret plates", _role_timeline(lambda p: p.turret_plates), digits=0),
                ],
            ),
            ("vision", "Vision", [TrendMetric("vision_per_min", "Vision/min", match_vision_min, digits=2), *wards]),
            (
                "map_contribution",
                "Map contribution",
                [
                    TrendMetric("roams", "Roams", _role_timeline(rm.visits), digits=0),
                    TrendMetric("successful_roams", "Successful roams", _role_timeline(rm.successful_visits), digits=0),
                    TrendMetric("damage_structures", "Structure damage", lambda p: p.damage_structures, digits=0),
                    TrendMetric("cs_diff_14", "CS @14", _timeline(lambda p: p.cs_diff_14), 0.0, digits=0, signed=True),
                ],
            ),
            deaths,
        ]

    if role == "SUPPORT":
        return [
            (
                "kill_participation",
                "Kill participation",
                [
                    TrendMetric("kill_participation", "KP", lambda p: p.kill_participation, centre("kill_participation"), unit="%", digits=0),
                    _ratio("early_kill_participation", "KP before 14", rm.early_kill_participation, unit="%", digits=0),
                ],
            ),
            (
                "roams",
                "Effective roams",
                [
                    TrendMetric("roams", "Roams", _role_timeline(rm.visits), digits=0),
                    TrendMetric("effective_roams", "Effective", _role_timeline(rm.successful_visits), digits=0),
                    _ratio("roam_success", "Success rate", rm.visit_success_rate, unit="%", digits=0),
                    TrendMetric(
                        "roam_deaths", "Deaths roaming", _timeline(lambda p: rm.early_deaths_away_from_lane(p, role)), digits=0
                    ),
                ],
            ),
            (
                "vision",
                "Vision",
                [TrendMetric("vision_per_min", "Vision/min", match_vision_min, radar["Vision/Min"], digits=2), *wards],
            ),
            deaths,
        ]

    # MID and ADC (and any unknown role).
    return [
        (
            "gold",
            "Gold efficiency",
            [
                TrendMetric("gold_per_min", "Gold/min", _per_minute(lambda p: p.gold), digits=0),
                TrendMetric("gold_share", "Gold share", lambda p: p.gold_share, unit="%"),
                TrendMetric("cs_per_min", "CS/min", match_cs_min, centre("cs_per_min")),
                TrendMetric("cs_14", "CS @14", _timeline(lambda p: p.cs_14), digits=0),
                TrendMetric("gold_diff_14", "Gold diff @14", _timeline(lambda p: p.gold_diff_14), 0.0, digits=0, signed=True),
            ],
        ),
        (
            "damage",
            "Damage dealt",
            [
                TrendMetric("damage_per_min", "DMG/min", _per_minute(lambda p: p.damage), centre("damage_per_min"), digits=0),
                TrendMetric("damage_share", "DMG share", lambda p: p.damage_share, centre("damage_share"), unit="%"),
                TrendMetric("efficiency", "DMG % / gold %", _efficiency, centre("efficiency"), digits=2),
            ],
        ),
        (
            "deaths",
            "Deaths",
            [
                *deaths[2],
                TrendMetric("solo_deaths", "Solo deaths", _timeline(rm.solo_deaths), digits=0),
                TrendMetric("early_gank_deaths", "Ganked before 10", _timeline(lambda p: p.early_gank_deaths), digits=0),
            ],
        ),
        (
            "vs",
            "Vs lane opponent",
            [
                TrendMetric("gold_diff_14", "Gold @14", _timeline(lambda p: p.gold_diff_14), 0.0, digits=0, signed=True),
                TrendMetric("cs_diff_14", "CS @14", _timeline(lambda p: p.cs_diff_14), 0.0, digits=0, signed=True),
                TrendMetric("xp_diff_14", "XP @14", _timeline(lambda p: p.xp_diff_14), 0.0, digits=0, signed=True),
            ],
        ),
    ]


def _moving_average(values: Sequence[float | None], window: int) -> list[float | None]:
    """Mean of the window with whatever data there is (None if there is none)."""
    result: list[float | None] = []
    for index in range(len(values)):
        present = [value for value in values[max(0, index - window + 1) : index + 1] if value is not None]
        result.append(round(sum(present) / len(present), 2) if present else None)
    return result


def compute_trends(participants: Sequence[ParticipantStats], role: str) -> SnapshotTrends:
    games = sorted(participants, key=lambda p: p.creation_time)
    window = trend_window_size(len(games))
    groups: list[TrendGroup] = []
    for key, label, metrics in trend_metrics(role):
        series: list[TrendSeries] = []
        for metric in metrics:
            values = [None if value is None else round(value, 2) for value in (metric.extract(p) for p in games)]
            moving: list[float | None]
            if metric.window_value is None:
                moving = _moving_average(values, window)
            else:
                summarize = metric.window_value
                moving = [summarize(games[max(0, index - window + 1) : index + 1]) for index in range(len(games))]
            series.append(
                TrendSeries(
                    key=metric.key,
                    label=metric.label,
                    unit=metric.unit,
                    digits=metric.digits,
                    signed=metric.signed,
                    challenger=metric.challenger,
                    values=values,
                    moving_average=moving,
                )
            )
        groups.append(TrendGroup(key, label, series))
    return SnapshotTrends(
        games=[TrendGame(index + 1, p.match_id, p.creation_time, p.champion, p.win) for index, p in enumerate(games)],
        groups=groups,
    )
