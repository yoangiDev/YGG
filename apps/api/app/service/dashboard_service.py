from sqlalchemy.orm import Session

from app.db.models.match import Match
from app.db.models.match_snapshot import MatchSnapshot
from app.service.ddragon_client import get_ddragon_client
from app.schemas.dashboard import (
    SnapshotDashboardResponse, ChampionStatsResponse,
    RoleAverageMetric, RadarChartData, RadarDataset
)
from app.schemas.match import MatchResponse

LANE_PHASE_SEC = 840  # 14 minutes
RADAR_AXES = [
    "CS/Min",
    "KDA",
    "Dmg Share",
    "Dmg/Gold",
    "Deaths/Game",
    "Laning Deaths",
    "Post-14 Deaths",
]
RADAR_AXES_SUPPORT = [
    "Vision/Min",
    "KDA",
    "Dmg Share",
    "Dmg/Gold",
    "Deaths/Game",
    "Laning Deaths",
    "Post-14 Deaths",
]

# Radar ceilings (you can tweak these freely).
# Positive metrics:  ceiling ≈ top Challenger / pro performance.
# Death metrics:     ceiling = "very bad" (more is always worse).
_RADAR_MAX_POSITIVE: dict[str, dict[str, float]] = {
    "CS/Min":      {"TOP": 10.5, "JUNGLE": 7.5, "MID": 11.0, "ADC": 11.5, "SUPPORT": 1.8},
    "Vision/Min":  {"TOP": 2.0,  "JUNGLE": 1.8, "MID": 2.0,  "ADC": 1.8,  "SUPPORT": 3.5},
    "KDA":         {"TOP": 6.5,  "JUNGLE": 8.0, "MID": 8.5,  "ADC": 9.0,  "SUPPORT": 8.0},
    "Dmg Share":   {"TOP": 31.0, "JUNGLE": 18.0, "MID": 27.0, "ADC": 45.0, "SUPPORT": 14.0},
    "Dmg/Gold":    {"TOP": 1.35, "JUNGLE": 1.15, "MID": 1.35, "ADC": 1.60, "SUPPORT": 1.10},
}

_RADAR_MAX_NEGATIVE: dict[str, dict[str, float]] = {
    "Deaths/Game":    {"TOP": 6.0, "JUNGLE": 6.5, "MID": 6.5, "ADC": 6.0, "SUPPORT": 7.5},
    "Laning Deaths":  {"TOP": 2.2, "JUNGLE": 1.8, "MID": 2.2, "ADC": 2.2, "SUPPORT": 2.8},
    "Post-14 Deaths": {"TOP": 3.8, "JUNGLE": 4.2, "MID": 3.8, "ADC": 3.5, "SUPPORT": 4.8},
}

# Challenger role averages — only used for displaying raw values,
# normalization is purely ceiling-based.
_RADAR_RANK_BENCHMARKS: dict[str, dict[str, dict[str, float]]] = {
    "TOP": {
        "CHALLENGER":    {"CS/Min": 7.40, "KDA": 2.78, "Dmg Share": 24.5, "Dmg/Gold": 1.12, "Deaths/Game": 3.5, "Laning Deaths": 1.1, "Post-14 Deaths": 1.6},
    },
    "JUNGLE": {
        "CHALLENGER":    {"CS/Min": 7.09, "KDA": 4.47, "Dmg Share": 17.0, "Dmg/Gold": 1.05, "Deaths/Game": 4.0, "Laning Deaths": 0.7, "Post-14 Deaths": 2.2},
    },
    "MID": {
        "CHALLENGER":    {"CS/Min": 7.51, "KDA": 3.54, "Dmg Share": 28.0, "Dmg/Gold": 1.18, "Deaths/Game": 3.8, "Laning Deaths": 1.0, "Post-14 Deaths": 1.9},
    },
    "ADC": {
        "CHALLENGER":    {"CS/Min": 8.00, "KDA": 3.41, "Dmg Share": 32.0, "Dmg/Gold": 1.45, "Deaths/Game": 3.2, "Laning Deaths": 0.9, "Post-14 Deaths": 1.6},
    },
    "SUPPORT": {
        "CHALLENGER":    {"Vision/Min": 2.87, "KDA": 4.15, "Dmg Share": 11.0, "Dmg/Gold": 0.95, "Deaths/Game": 4.5, "Laning Deaths": 1.2, "Post-14 Deaths": 2.5},
    },
}


def _normalize_radar_metric(key: str, value: float, role: str) -> float:
    """
    Normalize snapshot averages to 0–100 using simple ceilings.

    - Positive metrics (CS, KDA, Dmg Share, Dmg/Gold):
      0 → 0, ceiling → 100 (clamped).
    - Death metrics (Deaths/Game, Laning Deaths, Post-14 Deaths):
      0 → 100, ceiling → 0 (clamped, lower is always better).
    """
    role_caps = _RADAR_MAX_NEGATIVE if key in _RADAR_MAX_NEGATIVE else _RADAR_MAX_POSITIVE
    role_map = role_caps.get(key, {})
    cap = role_map.get(role, role_map.get("MID", 0.0))

    # Fallback: if we have no cap for this key, just return 0.
    if cap <= 0:
        return 0.0

    v = max(0.0, min(float(value), cap))

    if key in _RADAR_MAX_NEGATIVE:
        # Less deaths = better score.
        return round((1.0 - v / cap) * 100.0, 1)

    # Positive metric — more is better.
    return round(v / cap * 100.0, 1)


def _match_kda(match: Match) -> float:
    return (match.kills + match.assists) / match.deaths if match.deaths > 0 else float(match.kills + match.assists)


def _match_cs_min(match: Match) -> float:
    return match.total_cs / (match.duration / 60) if match.duration else 0.0


def _laning_deaths(match: Match) -> int:
    return sum(1 for d in (match.death_events or []) if d.get("time", 0) < LANE_PHASE_SEC)


def _post14_deaths(match: Match) -> int:
    return sum(1 for d in (match.death_events or []) if d.get("time", 0) >= LANE_PHASE_SEC)


def _build_radar_values(matches: list[Match], get_avg, role: str) -> dict[str, float]:
    avg_damage = get_avg(lambda m: m.damage)
    avg_gold = get_avg(lambda m: m.gold)
    dmg_gold = round(avg_damage / avg_gold, 2) if avg_gold > 0 else 0.0
    primary_farm_key = "Vision/Min" if role == "SUPPORT" else "CS/Min"
    primary_farm_value = get_avg(lambda m: m.vision / (m.duration / 60)) if role == "SUPPORT" else get_avg(_match_cs_min)
    return {
        primary_farm_key: primary_farm_value,
        "KDA":            get_avg(_match_kda),
        "Dmg Share":      get_avg(lambda m: m.damage_share),
        "Dmg/Gold":       dmg_gold,
        "Deaths/Game":    get_avg(lambda m: m.deaths),
        "Laning Deaths":  get_avg(_laning_deaths),
        "Post-14 Deaths": get_avg(_post14_deaths),
    }


def check_status(key: str, val: float, role: str = "") -> str:
    """Clasifica una métrica promedio en excellent/good/normal/bad."""
    k = key.lower().replace("_", " ").strip()
    r = role.upper()

    if k == "kda":
        if val >= 5.0: return "excellent"
        if val >= 4.0: return "good"
        if val >= 3.0: return "normal"
        return "bad"
    elif k in ("cs/min", "cs min"):
        if val >= 10.0: return "excellent"
        if val >= 9.0: return "good"
        if val >= 8.0: return "normal"
        return "bad"
    elif k in ("deaths", "deaths/game"):
        if val <= 3.0: return "excellent"
        if val <= 4.0: return "good"
        if val <= 5.0: return "normal"
        return "bad"
    elif k == "solo kills":
        if val >= 2.0: return "excellent"
        if val >= 1.0: return "good"
        if val >= 0.5: return "normal"
        return "bad"
    elif k == "solo deaths":
        if val <= 0.4: return "excellent"
        if val <= 0.8: return "good"
        if val <= 1.2: return "normal"
        return "bad"
    elif "gold diff" in k:
        if val >= 500: return "excellent"
        if val >= 200: return "good"
        if val >= -100: return "normal"
        return "bad"
    elif "cs diff" in k:
        if val >= 15: return "excellent"
        if val >= 8: return "good"
        if val >= 0: return "normal"
        return "bad"
    elif "vision" in k or k == "vision score/min" or k == "vision min":
        if val < 10.0:
            if val >= 2.2: return "excellent"
            if val >= 1.8: return "good"
            if val >= 1.4: return "normal"
            return "bad"
        else:
            if val >= 70.0: return "excellent"
            if val >= 55.0: return "good"
            if val >= 40.0: return "normal"
            return "bad"
    elif "kp" in k or "participation" in k:
        if val >= 70.0: return "excellent"
        if val >= 60.0: return "good"
        if val >= 50.0: return "normal"
        return "bad"
    elif k == "struct dmg" or k == "daño a estructuras":
        if val >= 8000: return "excellent"
        if val >= 6000: return "good"
        if val >= 4000: return "normal"
        return "bad"
    elif k == "obj control" or k == "control objetivos":
        if val >= 60.0: return "excellent"
        if val >= 50.0: return "good"
        if val >= 40.0: return "normal"
        return "bad"
    elif k == "enemy jg" or "camps cleared" in k:
        if val >= 15: return "excellent"
        if val >= 10: return "good"
        if val >= 6: return "normal"
        return "bad"
    elif k == "pink wards" or k == "control wards" or "pink" in k:
        if r == "SUPPORT":
            if val >= 8: return "excellent"
            if val >= 6: return "good"
            if val >= 4: return "normal"
            return "bad"
        elif r == "JUNGLE":
            if val >= 6: return "excellent"
            if val >= 4: return "good"
            if val >= 2: return "normal"
            return "bad"
        else:
            if val >= 4: return "excellent"
            if val >= 2.5: return "good"
            if val >= 1.5: return "normal"
            return "bad"
    elif k == "laning deaths":
        if val <= 0.5: return "excellent"
        if val <= 2.0: return "good"
        if val <= 2.8: return "normal"
        return "bad"
    elif k == "post-14 deaths":
        if val <= 1.2: return "excellent"
        if val <= 2.0: return "good"
        if val <= 4.0: return "normal"
        return "bad"
    elif k == "lane deaths" or "laning (pre-14)" in k:
        if val <= 30.0: return "excellent"
        if val <= 45.0: return "good"
        if val <= 60.0: return "normal"
        return "bad"
    elif k == "side deaths" or "side (post-14)" in k:
        if val <= 20.0: return "excellent"
        if val <= 35.0: return "good"
        if val <= 50.0: return "normal"
        return "bad"
    elif k == "dmg/gold" or k == "dmg gold":
        if val >= 1.25: return "excellent"
        if val >= 1.05: return "good"
        if val >= 0.85: return "normal"
        return "bad"
    elif k == "roaming" or k == "roaming proactivity":
        if val >= 4.0: return "excellent"
        if val >= 2.5: return "good"
        if val >= 1.5: return "normal"
        return "bad"
    elif k == "obj vision" or "objective prep" in k or k == "obj prep vision":
        if val >= 6.0: return "excellent"
        if val >= 4.0: return "good"
        if val >= 2.5: return "normal"
        return "bad"
    elif k == "efficiency" or k == "efficiency ratio" or k == "dmg share / gold share":
        if val >= 1.2: return "excellent"
        if val >= 1.0: return "good"
        if val >= 0.8: return "normal"
        return "bad"
    elif k == "dmg share" or k == "damage share":
        if val >= 32.0: return "excellent"
        if val >= 28.0: return "good"
        if val >= 24.0: return "normal"
        return "bad"
    elif k in ("early gank deaths", "death by early ganks", "early ganks"):
        if val <= 0.15: return "excellent"
        if val <= 0.35: return "good"
        if val <= 0.60: return "normal"
        return "bad"
    return "normal"


async def build_snapshot_dashboard(
    db: Session,
    snapshot,
    compare_game_name: str | None = None,
    compare_tag_line: str | None = None,
    compare_region: str | None = None,
) -> SnapshotDashboardResponse:
    """
    Construye el dashboard completo de un snapshot: métricas por rol,
    campeones jugados y datos del gráfico radar con benchmarks.
    """
    matches = (
        db.query(Match)
        .join(MatchSnapshot, MatchSnapshot.match_id == Match.id)
        .filter(MatchSnapshot.snapshot_id == snapshot.id)
        .all()
    )

    player = snapshot.player
    player_name = f"{player.game_name}#{player.tag_line}"

    role_str = player.role.value
    if role_str == "BOTTOM":
        active_role = "ADC"
    elif role_str == "ALL":
        active_role = "MID"
    else:
        active_role = role_str

    # ── Campeones jugados ──────────────────────────────────────────────────────
    champion_games: dict[str, int] = {}
    champion_wins: dict[str, int] = {}
    for m in matches:
        champion_games[m.champion] = champion_games.get(m.champion, 0) + 1
        if m.win:
            champion_wins[m.champion] = champion_wins.get(m.champion, 0) + 1

    dd_client = await get_ddragon_client()
    current_version = dd_client.version or "16.9.1"

    played_champions = []
    for champ_name, games in sorted(champion_games.items(), key=lambda x: x[1], reverse=True):
        wins = champion_wins.get(champ_name, 0)
        win_rate = round((wins / games) * 100, 1) if games > 0 else 0.0
        icon_url = dd_client.champion_icon_url(current_version, champ_name)
        played_champions.append(
            ChampionStatsResponse(
                champion_name=champ_name,
                games_played=games,
                win_rate=win_rate,
                icon_url=icon_url,
            )
        )

    n_games = len(matches)

    if n_games == 0:
        empty_radar = RadarChartData(
            axes=[],
            player_dataset=RadarDataset(label="", values={}, normalized_values={}),
            rank_datasets={},
            pro_datasets={},
        )
        return SnapshotDashboardResponse(
            snapshot_id=snapshot.id,
            player_id=player.id,
            player_name=player_name,
            date_from=snapshot.date_from,
            date_to=snapshot.date_to,
            description=snapshot.description,
            notes=snapshot.notes,
            active_role=active_role,
            role_averages=[],
            played_champions=[],
            matches=[],
            radar_data=empty_radar,
        )

    def get_avg(extractor) -> float:
        vals = [extractor(m) for m in matches if extractor(m) is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    def get_solo_deaths(match: Match) -> int:
        return sum(1 for d in (match.death_events or []) if not d.get("assistingParticipantIds"))

    # ── Métricas por rol ───────────────────────────────────────────────────────

    if active_role == "TOP":
        avg_kda         = get_avg(lambda m: (m.kills + m.assists) / m.deaths if m.deaths > 0 else float(m.kills + m.assists))
        avg_cs_min      = get_avg(lambda m: m.total_cs / (m.duration / 60))
        avg_solo_kills  = get_avg(lambda m: m.solo_kills)
        avg_solo_deaths = get_avg(get_solo_deaths)
        avg_dmg_share   = get_avg(lambda m: m.damage_share)
        avg_gold_share  = get_avg(lambda m: m.gold_share)
        avg_struct_dmg  = get_avg(lambda m: m.damage_structures)
        avg_deaths      = get_avg(lambda m: m.deaths)
        avg_gold_14     = get_avg(lambda m: m.gold_diff_14)
        avg_cs_14       = get_avg(lambda m: m.cs_diff_14)
        avg_early_ganks = get_avg(lambda m: m.early_gank_deaths)

        eff = round(avg_dmg_share / avg_gold_share, 2) if avg_gold_share > 0 else 0.0

        role_averages = [
            RoleAverageMetric(key="gold_diff_14",  label="Gold Diff @14",          value=avg_gold_14,     status=check_status("Gold Diff", avg_gold_14),  threshold=200.0, unit="g"),
            RoleAverageMetric(key="cs_diff_14",    label="CS Diff @14",            value=avg_cs_14,       status=check_status("CS Diff", avg_cs_14),      threshold=8.0,   unit="cs"),
            RoleAverageMetric(key="solo_kills",    label="Solo Kills / Game",       value=avg_solo_kills,  status=check_status("Solo Kills", avg_solo_kills), threshold=0.6),
            RoleAverageMetric(key="solo_deaths",   label="Solo Deaths / Game",      value=avg_solo_deaths, status=check_status("Solo Deaths", avg_solo_deaths), threshold=0.8),
            RoleAverageMetric(key="efficiency",    label="Dmg Share / Gold Share",  value=eff,             status=check_status("Efficiency", eff),          threshold=1.0),
            RoleAverageMetric(key="struct_dmg",    label="Daño a Estructuras",      value=avg_struct_dmg,  status=check_status("Struct Dmg", avg_struct_dmg), threshold=6000.0),
            RoleAverageMetric(key="kda",           label="KDA",                     value=avg_kda,         status=check_status("KDA", avg_kda),            threshold=3.0),
            RoleAverageMetric(key="cs_min",        label="CS/Min",                  value=avg_cs_min,      status=check_status("CS/Min", avg_cs_min),      threshold=7.0),
            RoleAverageMetric(key="deaths",        label="Deaths/Game",             value=avg_deaths,      status=check_status("Deaths", avg_deaths),      threshold=5.0),
            RoleAverageMetric(key="early_gank_deaths", label="Death by Early Ganks", value=avg_early_ganks,  status=check_status("Early Gank Deaths", avg_early_ganks), threshold=0.4),
        ]

    elif active_role == "JUNGLE":
        avg_kda        = get_avg(lambda m: (m.kills + m.assists) / m.deaths if m.deaths > 0 else float(m.kills + m.assists))
        avg_cs_min     = get_avg(lambda m: m.total_cs / (m.duration / 60))
        avg_deaths     = get_avg(lambda m: m.deaths)
        avg_enemy_jg   = get_avg(lambda m: m.enemy_jg_monsters)
        avg_pinks      = get_avg(lambda m: m.control_wards)
        avg_gold_14    = get_avg(lambda m: m.gold_diff_14)
        avg_cs_14      = get_avg(lambda m: m.cs_diff_14)

        drake_count  = sum(m.first_dragon for m in matches)
        herald_count = sum(m.herald for m in matches)
        grubs_count  = sum(m.void_grubs for m in matches)
        obj_rate     = round(((drake_count + herald_count + grubs_count) / (3 * n_games)) * 100, 1)

        role_averages = [
            RoleAverageMetric(key="gold_diff_14", label="Gold Diff @14",           value=avg_gold_14,  status=check_status("Gold Diff", avg_gold_14), threshold=200.0, unit="g"),
            RoleAverageMetric(key="cs_diff_14",   label="CS Diff @14",             value=avg_cs_14,    status=check_status("CS Diff", avg_cs_14),     threshold=8.0,   unit="cs"),
            RoleAverageMetric(key="kda",          label="KDA",                      value=avg_kda,      status=check_status("KDA", avg_kda),           threshold=3.0),
            RoleAverageMetric(key="cs_min",       label="CS/Min",                   value=avg_cs_min,   status=check_status("CS/Min", avg_cs_min),     threshold=7.0),
            RoleAverageMetric(key="deaths",       label="Deaths/Game",              value=avg_deaths,   status=check_status("Deaths", avg_deaths),     threshold=5.0),
            RoleAverageMetric(key="obj_control",  label="Control Objetivos",        value=obj_rate,     status=check_status("Obj Control", obj_rate),  threshold=55.0, unit="%"),
            RoleAverageMetric(key="enemy_jg",     label="Opponent Camps Cleared",   value=avg_enemy_jg, status=check_status("Enemy JG", avg_enemy_jg), threshold=12.0),
            RoleAverageMetric(key="pink_wards",   label="Pink Wards / Game",        value=avg_pinks,    status=check_status("Pink Wards", avg_pinks, role="JUNGLE"), threshold=5.0),
        ]

    elif active_role == "MID":
        avg_kda         = get_avg(lambda m: (m.kills + m.assists) / m.deaths if m.deaths > 0 else float(m.kills + m.assists))
        avg_cs_min      = get_avg(lambda m: m.total_cs / (m.duration / 60))
        avg_deaths      = get_avg(lambda m: m.deaths)
        avg_solo_deaths = get_avg(get_solo_deaths)
        avg_roams       = get_avg(lambda m: m.roaming_proactivity)
        avg_gold_14     = get_avg(lambda m: m.gold_diff_14)
        avg_cs_14       = get_avg(lambda m: m.cs_diff_14)
        avg_early_ganks = get_avg(lambda m: m.early_gank_deaths)

        lane_deaths = side_deaths = total_deaths_all = 0
        for m in matches:
            for d in (m.death_events or []):
                total_deaths_all += 1
                if d.get("time", 0) < 840:
                    lane_deaths += 1
                else:
                    side_deaths += 1

        lane_pct = round(lane_deaths / total_deaths_all * 100, 1) if total_deaths_all > 0 else 0.0
        side_pct = round(side_deaths / total_deaths_all * 100, 1) if total_deaths_all > 0 else 0.0

        role_averages = [
            RoleAverageMetric(key="gold_diff_14",  label="Gold Diff @14",              value=avg_gold_14, status=check_status("Gold Diff", avg_gold_14), threshold=200.0, unit="g"),
            RoleAverageMetric(key="cs_diff_14",    label="CS Diff @14",                value=avg_cs_14,   status=check_status("CS Diff", avg_cs_14),     threshold=8.0,   unit="cs"),
            RoleAverageMetric(key="kda",           label="KDA",                         value=avg_kda,     status=check_status("KDA", avg_kda),           threshold=3.0),
            RoleAverageMetric(key="cs_min",        label="CS/Min",                      value=avg_cs_min,  status=check_status("CS/Min", avg_cs_min),     threshold=7.0),
            RoleAverageMetric(key="deaths",        label="Deaths/Game",                 value=avg_deaths,  status=check_status("Deaths", avg_deaths),     threshold=5.0),
            RoleAverageMetric(key="solo_deaths",   label="Solo Deaths / Game",          value=avg_solo_deaths, status=check_status("Solo Deaths", avg_solo_deaths), threshold=0.8),
            RoleAverageMetric(key="lane_deaths",   label="Deaths in Laning (pre-14)",   value=lane_pct,    status=check_status("Lane Deaths", lane_pct),  threshold=35.0, unit="%"),
            RoleAverageMetric(key="side_deaths",   label="Deaths in Side (post-14)",    value=side_pct,    status=check_status("Side Deaths", side_pct),  threshold=30.0, unit="%"),
            RoleAverageMetric(key="roaming",       label="Roaming Proactivity",         value=avg_roams,   status=check_status("Roaming", avg_roams),     threshold=3.0),
            RoleAverageMetric(key="early_gank_deaths", label="Death by Early Ganks", value=avg_early_ganks,  status=check_status("Early Gank Deaths", avg_early_ganks), threshold=0.4),
        ]

    elif active_role == "ADC":
        avg_kda        = get_avg(lambda m: (m.kills + m.assists) / m.deaths if m.deaths > 0 else float(m.kills + m.assists))
        avg_cs_min     = get_avg(lambda m: m.total_cs / (m.duration / 60))
        avg_dmg_share  = get_avg(lambda m: m.damage_share)
        avg_gold_share = get_avg(lambda m: m.gold_share)
        avg_deaths     = get_avg(lambda m: m.deaths)
        avg_gold_14    = get_avg(lambda m: m.gold_diff_14)
        avg_cs_14      = get_avg(lambda m: m.cs_diff_14)
        avg_early_ganks = get_avg(lambda m: m.early_gank_deaths)

        eff = round(avg_dmg_share / avg_gold_share, 2) if avg_gold_share > 0 else 0.0

        lane_deaths = side_deaths = total_deaths_all = 0
        for m in matches:
            for d in (m.death_events or []):
                total_deaths_all += 1
                if d.get("time", 0) < 840:
                    lane_deaths += 1
                else:
                    side_deaths += 1

        lane_pct = round(lane_deaths / total_deaths_all * 100, 1) if total_deaths_all > 0 else 0.0
        side_pct = round(side_deaths / total_deaths_all * 100, 1) if total_deaths_all > 0 else 0.0

        role_averages = [
            RoleAverageMetric(key="gold_diff_14", label="Gold Diff @14",              value=avg_gold_14,   status=check_status("Gold Diff", avg_gold_14), threshold=200.0, unit="g"),
            RoleAverageMetric(key="cs_diff_14",   label="CS Diff @14",                value=avg_cs_14,     status=check_status("CS Diff", avg_cs_14),     threshold=8.0,   unit="cs"),
            RoleAverageMetric(key="dmg_share",    label="Damage Share",               value=avg_dmg_share, status=check_status("Dmg Share", avg_dmg_share), threshold=28.0, unit="%"),
            RoleAverageMetric(key="efficiency",   label="Dmg Share / Gold Share",     value=eff,           status=check_status("Efficiency", eff),        threshold=1.0),
            RoleAverageMetric(key="cs_min",       label="CS/Min",                      value=avg_cs_min,    status=check_status("CS/Min", avg_cs_min),     threshold=7.0),
            RoleAverageMetric(key="lane_deaths",  label="Deaths in Laning (pre-14)",  value=lane_pct,      status=check_status("Lane Deaths", lane_pct),  threshold=35.0, unit="%"),
            RoleAverageMetric(key="side_deaths",  label="Deaths in Side (post-14)",   value=side_pct,      status=check_status("Side Deaths", side_pct),  threshold=30.0, unit="%"),
            RoleAverageMetric(key="kda",          label="KDA",                         value=avg_kda,       status=check_status("KDA", avg_kda),           threshold=3.0),
            RoleAverageMetric(key="deaths",       label="Deaths/Game",                 value=avg_deaths,    status=check_status("Deaths", avg_deaths),     threshold=5.0),
            RoleAverageMetric(key="early_gank_deaths", label="Death by Early Ganks", value=avg_early_ganks,  status=check_status("Early Gank Deaths", avg_early_ganks), threshold=0.4),
        ]

    else:  # SUPPORT
        avg_vision_min = get_avg(lambda m: m.vision / (m.duration / 60))
        avg_pinks      = get_avg(lambda m: m.control_wards)
        avg_kp         = get_avg(lambda m: m.kill_participation)
        avg_vision     = get_avg(lambda m: m.vision)
        avg_deaths     = get_avg(lambda m: m.deaths)
        avg_obj_vision = get_avg(lambda m: m.objective_vision_score)

        role_averages = [
            RoleAverageMetric(key="vision_min",   label="Vision Score/Min",                value=avg_vision_min, status=check_status("Vision Score/Min", avg_vision_min), threshold=1.5, unit="/min"),
            RoleAverageMetric(key="pink_wards",   label="Pink Wards / Game",               value=avg_pinks,      status=check_status("Pink Wards", avg_pinks, role="SUPPORT"), threshold=7.0),
            RoleAverageMetric(key="kp_percent",   label="Kill Participation %",            value=avg_kp,         status=check_status("KP%", avg_kp),         threshold=60.0, unit="%"),
            RoleAverageMetric(key="vision_score", label="Vision Score",                    value=avg_vision,     status=check_status("Vision Score", avg_vision), threshold=55.0),
            RoleAverageMetric(key="deaths",       label="Deaths/Game",                     value=avg_deaths,     status=check_status("Deaths", avg_deaths),  threshold=5.0),
            RoleAverageMetric(key="obj_vision",   label="Objective Prep Vision Score",     value=avg_obj_vision, status=check_status("Obj Vision", avg_obj_vision), threshold=5.0),
        ]

    # ── Radar chart ────────────────────────────────────────────────────────────

    axes = RADAR_AXES_SUPPORT if active_role == "SUPPORT" else RADAR_AXES
    player_values = _build_radar_values(matches, get_avg, active_role)
    rank_benchmarks = _RADAR_RANK_BENCHMARKS.get(active_role, _RADAR_RANK_BENCHMARKS["MID"])

    def normalize_metric(k: str, v: float) -> float:
        return _normalize_radar_metric(k, v, active_role)

    player_dataset = RadarDataset(
        label=player.game_name,
        values={k: round(v, 2) for k, v in player_values.items()},
        normalized_values={k: normalize_metric(k, v) for k, v in player_values.items()},
    )

    rank_datasets = {
        rank_name: RadarDataset(
            label=rank_name.capitalize(),
            values={k: round(v, 2) for k, v in b_vals.items()},
            normalized_values={k: normalize_metric(k, v) for k, v in b_vals.items()},
        )
        for rank_name, b_vals in rank_benchmarks.items()
    }

    # ── Cuenta de comparación (opcional) ──────────────────────────────────────
    pro_datasets: dict = {}
    if compare_game_name and compare_tag_line:
        from app.service.riot_client import RiotAPIClient
        from app.service.http_client import create_secure_session
        from app.db.models.player import Player as PlayerModel

        region_to_use = compare_region or (player.region if hasattr(player, "region") else None) or "euw"
        client = RiotAPIClient(region=region_to_use)
        compare_player = PlayerModel()
        compare_player.game_name = compare_game_name
        compare_player.tag_line  = compare_tag_line
        compare_player.region    = region_to_use
        compare_player.id        = 0

        async with create_secure_session() as session:
            try:
                puuid = await client.get_puuid(session, compare_game_name, compare_tag_line)
                compare_player.puuid = puuid
                compare_matches = await client.fetch_matches(
                    session=session,
                    player=compare_player,
                    max_matches=50,
                    role_filter=active_role,
                    include_timeline=True,
                )

                def get_avg_cmp(extractor) -> float:
                    vals = [extractor(m) for m in compare_matches if extractor(m) is not None]
                    return round(sum(vals) / len(vals), 2) if vals else 0.0

                cmp_values = _build_radar_values(compare_matches, get_avg_cmp, active_role)

                pro_datasets[f"{compare_game_name}#{compare_tag_line}"] = RadarDataset(
                    label=f"{compare_game_name}#{compare_tag_line}",
                    values={k: round(v, 2) for k, v in cmp_values.items()},
                    normalized_values={k: normalize_metric(k, v) for k, v in cmp_values.items()},
                )
            except Exception:
                pro_datasets = {}

    radar_chart_data = RadarChartData(
        axes=axes,
        player_dataset=player_dataset,
        rank_datasets=rank_datasets,
        pro_datasets=pro_datasets,
    )

    matches_response = [MatchResponse.model_validate(m) for m in matches]

    return SnapshotDashboardResponse(
        snapshot_id=snapshot.id,
        player_id=player.id,
        player_name=player_name,
        date_from=snapshot.date_from,
        date_to=snapshot.date_to,
        description=snapshot.description,
        notes=snapshot.notes,
        active_role=active_role,
        role_averages=role_averages,
        played_champions=played_champions,
        matches=matches_response,
        radar_data=radar_chart_data,
    )