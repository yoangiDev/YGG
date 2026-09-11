"""Cálculo del dashboard de un snapshot: medias por rol, campeones y radar."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ygg_core.domain.participant import ParticipantStats
from ygg_core.metrics.radar import (
    LANE_PHASE_SEC,
    average,
    build_radar_values,
    match_cs_min,
    match_kda,
    match_vision_min,
    normalize_radar_metric,
    radar_axes,
    rank_benchmarks,
)
from ygg_core.metrics.status import check_status


@dataclass(slots=True)
class RoleAverage:
    key: str
    label: str
    value: float
    status: str
    threshold: float
    unit: str = ""


@dataclass(slots=True)
class ChampionSummary:
    champion_name: str
    games_played: int
    win_rate: float


@dataclass(slots=True)
class RadarDataset:
    label: str
    values: dict[str, float]
    normalized_values: dict[str, float]


@dataclass(slots=True)
class RadarData:
    axes: list[str]
    player_dataset: RadarDataset
    rank_datasets: dict[str, RadarDataset] = field(default_factory=dict)
    pro_datasets: dict[str, RadarDataset] = field(default_factory=dict)


@dataclass(slots=True)
class DashboardMetrics:
    active_role: str
    role_averages: list[RoleAverage]
    played_champions: list[ChampionSummary]
    radar: RadarData


def _metric(
    key: str,
    label: str,
    value: float,
    status_key: str,
    threshold: float,
    unit: str = "",
    role: str = "",
) -> RoleAverage:
    return RoleAverage(key, label, value, check_status(status_key, value, role), threshold, unit)


def _solo_deaths(p: ParticipantStats) -> int:
    return sum(1 for d in (p.death_events or []) if not d.get("assistingParticipantIds"))


def _death_phase_split(participants: Sequence[ParticipantStats]) -> tuple[float, float]:
    """% de muertes en fase de líneas (<14 min) y después."""
    lane = side = 0
    for p in participants:
        for death in p.death_events or []:
            if death.get("time", 0) < LANE_PHASE_SEC:
                lane += 1
            else:
                side += 1
    total = lane + side
    if total == 0:
        return 0.0, 0.0
    return round(lane / total * 100, 1), round(side / total * 100, 1)


def _efficiency(participants: Sequence[ParticipantStats]) -> float:
    dmg_share = average(participants, lambda p: p.damage_share)
    gold_share = average(participants, lambda p: p.gold_share)
    return round(dmg_share / gold_share, 2) if gold_share > 0 else 0.0


def _laning_block(participants: Sequence[ParticipantStats]) -> list[RoleAverage]:
    gold_14 = average(participants, lambda p: p.gold_diff_14)
    cs_14 = average(participants, lambda p: p.cs_diff_14)
    return [
        _metric("gold_diff_14", "Gold Diff @14", gold_14, "Gold Diff", 200.0, "g"),
        _metric("cs_diff_14", "CS Diff @14", cs_14, "CS Diff", 8.0, "cs"),
    ]


def role_averages(participants: Sequence[ParticipantStats], role: str) -> list[RoleAverage]:
    if not participants:
        return []
    p = participants
    kda = average(p, match_kda)
    cs_min = average(p, match_cs_min)
    deaths = average(p, lambda x: x.deaths)
    early_ganks = average(p, lambda x: x.early_gank_deaths)

    if role == "TOP":
        return [
            *_laning_block(p),
            _metric("solo_kills", "Solo Kills / Game", average(p, lambda x: x.solo_kills), "Solo Kills", 0.6),
            _metric("solo_deaths", "Solo Deaths / Game", average(p, _solo_deaths), "Solo Deaths", 0.8),
            _metric("efficiency", "Dmg Share / Gold Share", _efficiency(p), "Efficiency", 1.0),
            _metric("struct_dmg", "Daño a Estructuras", average(p, lambda x: x.damage_structures), "Struct Dmg", 6000.0),
            _metric("kda", "KDA", kda, "KDA", 3.0),
            _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
            _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
            _metric("early_gank_deaths", "Death by Early Ganks", early_ganks, "Early Gank Deaths", 0.4),
        ]

    if role == "JUNGLE":
        objectives = sum(x.first_dragon for x in p) + sum(x.herald for x in p) + sum(x.void_grubs for x in p)
        obj_rate = round(objectives / (3 * len(p)) * 100, 1)
        return [
            *_laning_block(p),
            _metric("kda", "KDA", kda, "KDA", 3.0),
            _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
            _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
            _metric("obj_control", "Control Objetivos", obj_rate, "Obj Control", 55.0, "%"),
            _metric("enemy_jg", "Opponent Camps Cleared", average(p, lambda x: x.enemy_jg_monsters), "Enemy JG", 12.0),
            _metric("pink_wards", "Pink Wards / Game", average(p, lambda x: x.control_wards), "Pink Wards", 5.0, role="JUNGLE"),
        ]

    if role in ("MID", "ADC"):
        lane_pct, side_pct = _death_phase_split(p)
        lane_metrics = [
            _metric("lane_deaths", "Deaths in Laning (pre-14)", lane_pct, "Lane Deaths", 35.0, "%"),
            _metric("side_deaths", "Deaths in Side (post-14)", side_pct, "Side Deaths", 30.0, "%"),
        ]
        early = _metric("early_gank_deaths", "Death by Early Ganks", early_ganks, "Early Gank Deaths", 0.4)
        if role == "MID":
            return [
                *_laning_block(p),
                _metric("kda", "KDA", kda, "KDA", 3.0),
                _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
                _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
                _metric("solo_deaths", "Solo Deaths / Game", average(p, _solo_deaths), "Solo Deaths", 0.8),
                *lane_metrics,
                _metric("roaming", "Roaming Proactivity", average(p, lambda x: x.roaming_proactivity), "Roaming", 3.0),
                early,
            ]
        return [
            *_laning_block(p),
            _metric("dmg_share", "Damage Share", average(p, lambda x: x.damage_share), "Dmg Share", 28.0, "%"),
            _metric("efficiency", "Dmg Share / Gold Share", _efficiency(p), "Efficiency", 1.0),
            _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
            *lane_metrics,
            _metric("kda", "KDA", kda, "KDA", 3.0),
            _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
            early,
        ]

    # SUPPORT
    return [
        _metric("vision_min", "Vision Score/Min", average(p, match_vision_min), "Vision Score/Min", 1.5, "/min"),
        _metric("pink_wards", "Pink Wards / Game", average(p, lambda x: x.control_wards), "Pink Wards", 7.0, role="SUPPORT"),
        _metric("kp_percent", "Kill Participation %", average(p, lambda x: x.kill_participation), "KP%", 60.0, "%"),
        _metric("vision_score", "Vision Score", average(p, lambda x: x.vision), "Vision Score", 55.0),
        _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
        _metric("obj_vision", "Objective Prep Vision Score", average(p, lambda x: x.objective_vision_score), "Obj Vision", 5.0),
    ]


def played_champions(participants: Sequence[ParticipantStats]) -> list[ChampionSummary]:
    games: dict[str, int] = {}
    wins: dict[str, int] = {}
    for p in participants:
        games[p.champion] = games.get(p.champion, 0) + 1
        if p.win:
            wins[p.champion] = wins.get(p.champion, 0) + 1
    return [
        ChampionSummary(name, count, round(wins.get(name, 0) / count * 100, 1))
        for name, count in sorted(games.items(), key=lambda item: item[1], reverse=True)
    ]


def radar_dataset(label: str, values: dict[str, float], role: str) -> RadarDataset:
    return RadarDataset(
        label=label,
        values={k: round(v, 2) for k, v in values.items()},
        normalized_values={k: normalize_radar_metric(k, v, role) for k, v in values.items()},
    )


def comparison_dataset(
    label: str, participants: Sequence[ParticipantStats], role: str
) -> RadarDataset:
    """Radar de otra cuenta (p. ej. un pro) para superponerlo al del jugador."""
    return radar_dataset(label, build_radar_values(participants, role), role)


def compute_dashboard(
    participants: Sequence[ParticipantStats],
    role: str,
    player_label: str,
) -> DashboardMetrics:
    if not participants:
        return DashboardMetrics(
            active_role=role,
            role_averages=[],
            played_champions=[],
            radar=RadarData(axes=[], player_dataset=RadarDataset("", {}, {})),
        )

    radar = RadarData(
        axes=radar_axes(role),
        player_dataset=radar_dataset(player_label, build_radar_values(participants, role), role),
        rank_datasets={
            rank: radar_dataset(rank.capitalize(), values, role)
            for rank, values in rank_benchmarks(role).items()
        },
    )
    return DashboardMetrics(
        active_role=role,
        role_averages=role_averages(participants, role),
        played_champions=played_champions(participants),
        radar=radar,
    )
