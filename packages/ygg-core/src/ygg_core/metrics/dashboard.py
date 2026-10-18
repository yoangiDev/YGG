"""Snapshot dashboard computation: averages by role, champions, radar and trends."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

from ygg_core.domain.participant import ParticipantStats
from ygg_core.metrics import role_metrics as rm
from ygg_core.metrics.benchmarks import DEFAULT_TARGET_RANK, target
from ygg_core.metrics.match_score import metric_status, scoring_role
from ygg_core.metrics.radar import (
    average,
    build_radar_values,
    efficiency,
    laning_deaths,
    match_cs_min,
    match_vision_min,
    normalize_radar_metric,
    pooled_kda,
    post14_deaths,
    radar_axes,
    rank_benchmarks,
)
from ygg_core.metrics.status import KDA_EXCELLENT_FROM, check_status
from ygg_core.metrics.trends import SnapshotTrends, compute_trends

# Each jungle camp gives 4 CS: in the timeline the jungle CS goes up in steps of 4.
CS_PER_CAMP = 4


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
    """Performance with one champion.

    Kills, deaths, assists, @14 differences and deaths by phase are per-match
    means (the timeline ones, over the matches that have it); the KDA and the per-minute
    rates come from the total of their matches.
    """

    champion_name: str
    games_played: int
    win_rate: float
    wins: int
    losses: int
    kills: float
    deaths: float
    assists: float
    kda: float
    kda_status: str
    cs_per_min: float
    dmg_per_min: float
    gold_per_min: float
    vision_per_min: float
    kill_participation: float
    damage_share: float
    gold_diff_14: float | None
    cs_diff_14: float | None
    laning_deaths: float | None
    mid_late_deaths: float | None


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
    trends: SnapshotTrends


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


def _laning_block(participants: Sequence[ParticipantStats]) -> list[RoleAverage]:
    gold_14 = average(participants, lambda p: p.gold_diff_14)
    cs_14 = average(participants, lambda p: p.cs_diff_14)
    return [
        _metric("gold_diff_14", "Gold Diff @14", gold_14, "Gold Diff", 200.0, "g"),
        _metric("cs_diff_14", "CS Diff @14", cs_14, "CS Diff", 8.0, "cs"),
    ]


# Cards measured per league in the harvest (card key → metric of benchmarks.py). Their target is the
# 65th percentile of the chosen league (35th for deaths: better than two out of three matches) and their status comes from the
# grade bands. The KDA is deliberately absent: it has a fixed threshold (status.py). ponytail: the others that are not
# here (only kills, roaming, early ganks, objective control and vision) still use the fixed threshold of status.py;
# they move here as soon as references.py measures them.
RANKED_CARDS: dict[str, str] = {
    "cs_min": "cs_per_min",
    "deaths": "deaths",
    "efficiency": "efficiency",
    "dmg_share": "damage_share",
    "kp_percent": "kill_participation",
    "vision_min": "vision_per_min",
    "vision_score": "vision_score",
    "pink_wards": "control_wards",
    "struct_dmg": "damage_structures",
    "enemy_jg": "enemy_jg_camps",
    "gold_diff_14": "gold_diff_14",
    "cs_diff_14": "cs_diff_14",
    "laning_deaths": "laning_deaths",
    "post14_deaths": "post14_deaths",
}


def _against_rank(card: RoleAverage, role: str, rank: str) -> RoleAverage:
    metric = RANKED_CARDS.get(card.key)
    if metric is None:
        return card
    goal = target(rank, scoring_role(role), metric)
    return replace(card, threshold=round(goal, 2), status=metric_status(metric, card.value, role, rank))


def role_averages(
    participants: Sequence[ParticipantStats], role: str, target_rank: str = DEFAULT_TARGET_RANK
) -> list[RoleAverage]:
    """Role cards compared with the average of the player's target rank."""
    return [_against_rank(card, role, target_rank) for card in _role_cards(participants, role)]


def _role_cards(participants: Sequence[ParticipantStats], role: str) -> list[RoleAverage]:
    if not participants:
        return []
    p = participants
    kda = pooled_kda(p)
    cs_min = average(p, match_cs_min)
    deaths = average(p, lambda x: x.deaths)
    early_ganks = average(p, lambda x: x.early_gank_deaths)

    if role == "TOP":
        return [
            *_laning_block(p),
            _metric("solo_kills", "Solo Kills / Game", average(p, lambda x: x.solo_kills), "Solo Kills", 0.6),
            _metric("solo_deaths", "Solo Deaths / Game", average(p, rm.solo_deaths), "Solo Deaths", 0.8),
            _metric("efficiency", "Dmg Share / Gold Share", efficiency(p), "Efficiency", 1.0),
            _metric("struct_dmg", "Structure Damage", average(p, lambda x: x.damage_structures), "Struct Dmg", 6000.0),
            _metric("kda", "KDA", kda, "KDA", KDA_EXCELLENT_FROM),
            _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
            _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
            _metric("early_gank_deaths", "Death by Early Ganks", early_ganks, "Early Gank Deaths", 0.4),
        ]

    if role == "JUNGLE":
        objectives = sum(x.first_dragon for x in p) + sum(x.herald for x in p) + sum(x.void_grubs for x in p)
        obj_rate = round(objectives / (3 * len(p)) * 100, 1)
        return [
            *_laning_block(p),
            _metric("kda", "KDA", kda, "KDA", KDA_EXCELLENT_FROM),
            _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
            _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
            _metric("obj_control", "Objective Control", obj_rate, "Obj Control", 55.0, "%"),
            _metric("enemy_jg", "Opponent Camps Cleared", average(p, lambda x: x.enemy_jg_monsters / CS_PER_CAMP), "Enemy JG", 12.0),
            _metric("pink_wards", "Pink Wards / Game", average(p, lambda x: x.control_wards), "Pink Wards", 5.0, role="JUNGLE"),
        ]

    if role in ("MID", "ADC"):
        # Per match and not as a % of the total: the two % add up to 100, and it was impossible to do well in both at once.
        lane_metrics = [
            _metric("laning_deaths", "Deaths in Laning (pre-14)", average(p, laning_deaths), "Laning Deaths", 2.0),
            _metric("post14_deaths", "Deaths after 14:00", average(p, post14_deaths), "Post-14 Deaths", 3.0),
        ]
        early = _metric("early_gank_deaths", "Death by Early Ganks", early_ganks, "Early Gank Deaths", 0.4)
        if role == "MID":
            return [
                *_laning_block(p),
                _metric("kda", "KDA", kda, "KDA", KDA_EXCELLENT_FROM),
                _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
                _metric("deaths", "Deaths/Game", deaths, "Deaths", 5.0),
                _metric("solo_deaths", "Solo Deaths / Game", average(p, rm.solo_deaths), "Solo Deaths", 0.8),
                *lane_metrics,
                _metric("roaming", "Roaming Proactivity", average(p, lambda x: x.roaming_proactivity), "Roaming", 3.0),
                early,
            ]
        return [
            *_laning_block(p),
            _metric("dmg_share", "Damage Share", average(p, lambda x: x.damage_share), "Dmg Share", 28.0, "%"),
            _metric("efficiency", "Dmg Share / Gold Share", efficiency(p), "Efficiency", 1.0),
            _metric("cs_min", "CS/Min", cs_min, "CS/Min", 7.0),
            *lane_metrics,
            _metric("kda", "KDA", kda, "KDA", KDA_EXCELLENT_FROM),
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


def _per_minute(games: Sequence[ParticipantStats], value: Callable[[ParticipantStats], int]) -> float:
    minutes = sum(p.duration for p in games) / 60
    return round(sum(value(p) for p in games) / minutes, 2) if minutes > 0 else 0.0


def _champion_summary(name: str, games: Sequence[ParticipantStats], role: str, target_rank: str) -> ChampionSummary:
    wins = sum(p.win for p in games)
    kda = pooled_kda(games)
    timeline = [p for p in games if p.timeline_enriched]

    def timeline_average(extractor: Callable[[ParticipantStats], float]) -> float | None:
        return average(timeline, extractor) if timeline else None

    return ChampionSummary(
        champion_name=name,
        games_played=len(games),
        win_rate=round(wins / len(games) * 100, 1),
        wins=wins,
        losses=len(games) - wins,
        kills=average(games, lambda p: p.kills),
        deaths=average(games, lambda p: p.deaths),
        assists=average(games, lambda p: p.assists),
        kda=kda,
        kda_status=metric_status("kda", kda, role, target_rank),
        cs_per_min=_per_minute(games, lambda p: p.total_cs),
        dmg_per_min=_per_minute(games, lambda p: p.damage),
        gold_per_min=_per_minute(games, lambda p: p.gold),
        vision_per_min=_per_minute(games, lambda p: p.vision),
        kill_participation=average(games, lambda p: p.kill_participation),
        damage_share=average(games, lambda p: p.damage_share),
        gold_diff_14=timeline_average(lambda p: p.gold_diff_14),
        cs_diff_14=timeline_average(lambda p: p.cs_diff_14),
        laning_deaths=timeline_average(laning_deaths),
        mid_late_deaths=timeline_average(post14_deaths),
    )


def played_champions(
    participants: Sequence[ParticipantStats], role: str = "MID", target_rank: str = DEFAULT_TARGET_RANK
) -> list[ChampionSummary]:
    """Champions in the snapshot, from most to least played, with their performance on each."""
    by_champion: dict[str, list[ParticipantStats]] = {}
    for p in participants:
        by_champion.setdefault(p.champion, []).append(p)
    ordered = sorted(by_champion.items(), key=lambda item: len(item[1]), reverse=True)
    return [_champion_summary(name, games, role, target_rank) for name, games in ordered]


def radar_dataset(label: str, values: dict[str, float], role: str) -> RadarDataset:
    return RadarDataset(
        label=label,
        values={k: round(v, 2) for k, v in values.items()},
        normalized_values={k: normalize_radar_metric(k, v, role) for k, v in values.items()},
    )


def comparison_dataset(
    label: str, participants: Sequence[ParticipantStats], role: str
) -> RadarDataset:
    """Radar of another account (e.g. a pro) to overlay on the player's."""
    return radar_dataset(label, build_radar_values(participants, role), role)


def compute_dashboard(
    participants: Sequence[ParticipantStats],
    role: str,
    player_label: str,
    target_rank: str = DEFAULT_TARGET_RANK,
) -> DashboardMetrics:
    if not participants:
        return DashboardMetrics(
            active_role=role,
            role_averages=[],
            played_champions=[],
            radar=RadarData(axes=[], player_dataset=RadarDataset("", {}, {})),
            trends=SnapshotTrends(games=[], groups=[]),
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
        role_averages=role_averages(participants, role, target_rank),
        played_champions=played_champions(participants, role, target_rank),
        radar=radar,
        trends=compute_trends(participants, role),
    )
