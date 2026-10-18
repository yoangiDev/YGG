"""Grade of a match with only what Riot's API gives (match and timeline), fitted to the analyses' grade.

The analyses' grade comes from the replay (`research/replays/coach.py`): what a player's moments add and subtract, in neutral WP points and
scaled to 30 minutes, compared with the Challenger percentiles for their position (the anchors 40, 55, 62.5, 70 and 85 of `match_score`). The API does not
have the replay, but it does have the timeline, and with it that same quantity can be predicted: a per-position regression over 43 variables —deaths and
when, dead time, enemy objectives that fall while you are dead, gold, XP and CS differences against the lane opponent at 10, 14 and 20
minutes, kills and assists, damage, plates, vision...— fitted with 8,660 players from 866 Challenger-to-Bronze matches of the harvest
(`research/replays/fit_history.py`, which stores `timeline_grade_model.json`).

Measured with per-match cross-validation, the mean error against the analysis grade is 5 to 9 grade points depending on the position (today's
stats grade: 8 to 14; the WPA one: 11 to 15), and between 67% and 87% of players land within ±10 points.

No dependencies: the regression is a dot product with the mean and standard deviation of each variable.
"""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path
from typing import Any

from ygg_core.metrics.match_score import metric_score
from ygg_core.riot.match_record import match_record

JsonDict = dict[str, Any]

# Seconds of respawn wait per level 1-18 (the wiki) and its increase from minute 15: what each death costs.
BRW = (10, 10, 12, 12, 14, 16, 20, 25, 28, 32.5, 35, 37.5, 40, 42.5, 45, 47.5, 50, 52.5)
RESPAWN_MARGIN = 12  # seconds of walking back from base after reviving
# Weight of the objective that falls while you are dead (docs/model/match_grade.md).
BUILDING_WEIGHT = {
    ("OUTER_TURRET", "MID_LANE"): 9, ("INNER_TURRET", "MID_LANE"): 7, ("OUTER_TURRET", "TOP_LANE"): 4, ("OUTER_TURRET", "BOT_LANE"): 4,
    ("INNER_TURRET", "TOP_LANE"): 8, ("INNER_TURRET", "BOT_LANE"): 8, ("BASE_TURRET", None): 3, ("INHIBITOR_BUILDING", None): 3,
}
MONSTER_WEIGHT = {"DRAGON": 5, "ELDER_DRAGON": 10, "BARON_NASHOR": 8, "RIFTHERALD": 4}
MODEL_FILE = Path(__file__).with_name("timeline_grade_model.json")


@cache
def model() -> JsonDict:
    return json.loads(MODEL_FILE.read_text(encoding="utf-8"))


def respawn_seconds(level: int, minute: float) -> float:
    base = BRW[max(0, min(17, level - 1))]
    if minute < 15:
        extra = 0.0
    elif minute < 30:
        extra = 0.00425 * math.ceil(2 * (minute - 15))
    else:
        extra = 0.1275 + 0.003 * math.ceil(2 * (minute - 30))
    return base * (1 + min(0.5, extra))


def frame(record: JsonDict, pid: int, minute: int) -> list[int] | None:
    frames = record["frames"].get(str(pid))
    if not frames:
        return None
    return next((f for f in frames if f[0] == minute), frames[-1] if minute >= frames[-1][0] else None)


def variables(record: JsonDict, p: JsonDict) -> dict[str, float]:
    """A player's variables taken from the match and its timeline (`match_record`)."""
    d = max(record["duration"] / 60, 1.0)
    scale = 30.0 / max(10.0, d)  # to a 30-minute match, like the analysis grade
    pid, team = p["participantId"], p["teamId"]
    c = p.get("challenges") or {}
    everyone = record["participants"]
    mine = [q for q in everyone if q["teamId"] == team]
    rival = next((q for q in everyone if q["teamId"] != team and q.get("teamPosition") == p.get("teamPosition")), None)
    team_kills = max(1, sum(q["kills"] for q in mine))
    v: dict[str, float] = {
        "kills30": p["kills"] * scale, "deaths30": p["deaths"] * scale, "assists30": p["assists"] * scale,
        "kp": 100 * c.get("killParticipation", (p["kills"] + p["assists"]) / team_kills),
        "dmg_share": 100 * c.get("teamDamagePercentage", 0.0), "dmg_min": p["totalDamageDealtToChampions"] / d,
        "gold_min": p["goldEarned"] / d, "cs_min": (p["totalMinionsKilled"] + p["neutralMinionsKilled"]) / d,
        "solo30": c.get("soloKills", 0) * scale, "vision_min": p.get("visionScore", 0) / d,
        "ctrl_wards30": p.get("detectorWardsPlaced", 0) * scale, "wards30": p.get("wardsPlaced", 0) * scale,
        "wards_killed30": p.get("wardsKilled", 0) * scale, "plates30": c.get("turretPlatesTaken", 0) * scale,
        "turret_dmg_min": p.get("damageDealtToTurrets", 0) / d, "turret_td30": c.get("turretTakedowns", 0) * scale,
        "dragon_td30": c.get("dragonTakedowns", 0) * scale, "obj_dmg_min": p.get("damageDealtToObjectives", 0) / d,
        "heal_shield_min": c.get("effectiveHealAndShielding", 0) / d, "taken_share": 100 * c.get("damageTakenOnTeamPercentage", 0.0),
        "win": float(p["win"]), "duration": d,
    }
    for minute in (10, 14, 20):
        a = frame(record, pid, minute)
        b = frame(record, rival["participantId"], minute) if rival else None
        if a and b:
            v[f"gold_diff_{minute}"], v[f"xp_diff_{minute}"] = a[1] - b[1], a[2] - b[2]
            v[f"cs_diff_{minute}"], v[f"lvl_diff_{minute}"] = (a[4] + a[5]) - (b[4] + b[5]), a[3] - b[3]
        else:
            v.update({f"gold_diff_{minute}": 0.0, f"xp_diff_{minute}": 0.0, f"cs_diff_{minute}": 0.0, f"lvl_diff_{minute}": 0.0})
    for minute in (15, 20):
        ours = sum((frame(record, q["participantId"], minute) or [0, 0])[1] for q in mine)
        theirs = sum((frame(record, q["participantId"], minute) or [0, 0])[1] for q in everyone if q["teamId"] != team)
        v[f"team_gold_{minute}"] = ours - theirs
    # objectives: (second, weight, team, type); a building carries the OWNING team, a monster the team that kills it
    objectives = []
    for e in record["events"]:
        if e["type"] == "BUILDING_KILL":
            kind = e.get("towerType") or e.get("buildingType")
            lane = e.get("laneType") if e.get("towerType") in ("OUTER_TURRET", "INNER_TURRET") else None
            objectives.append((e["timestamp"] / 1000, BUILDING_WEIGHT.get((kind, lane), 1), e.get("teamId"), "BUILDING_KILL"))
        elif e["type"] == "ELITE_MONSTER_KILL":
            objectives.append((e["timestamp"] / 1000, MONSTER_WEIGHT.get(e.get("monsterType"), 0), e.get("killerTeamId"), "ELITE_MONSTER_KILL"))
    before = after = isolated = 0
    waited = paid = bounty = 0.0
    for e in record["events"]:
        if e["type"] != "CHAMPION_KILL" or e.get("victimId") != pid:
            continue
        t = e["timestamp"] / 1000
        minute = t / 60
        w = respawn_seconds((frame(record, pid, int(minute)) or [0, 0, 0, 1])[3], minute)
        waited += w
        before += minute < 14
        after += minute >= 14
        isolated += e.get("victim_received_champions", 9) <= 1
        bounty += e.get("bounty", 0)
        for at, weight, owner, kind in objectives:
            theirs = owner == team if kind == "BUILDING_KILL" else owner != team
            if theirs and t < at <= t + w + RESPAWN_MARGIN:
                paid += weight
    v.update({"deaths_early30": before * scale, "deaths_late30": after * scale, "deaths_isolated30": isolated * scale,
              "time_dead30": waited * scale, "bounty_given30": bounty * scale, "obj_paid30": paid * scale})
    won = 0.0
    for e in record["events"]:
        if e["type"] != "CHAMPION_KILL" or (e.get("killerId") != pid and pid not in (e.get("assistingParticipantIds") or [])):
            continue
        t = e["timestamp"] / 1000
        victim = e.get("victimId")
        if not any(q["participantId"] == victim for q in everyone):
            continue
        w = respawn_seconds((frame(record, victim, int(t / 60)) or [0, 0, 0, 1])[3], t / 60)
        for at, weight, owner, kind in objectives:
            ours = owner != team if kind == "BUILDING_KILL" else owner == team
            if ours and t < at <= t + w + RESPAWN_MARGIN:
                won += weight
    v["obj_won30"] = won * scale
    return v


def predicted_total(record: JsonDict, p: JsonDict) -> float | None:
    """What the moments of their analysis would add up to, according to their position and their match; None if the position is unknown."""
    role = model()["positions"].get(p.get("teamPosition") or "")
    if role is None:
        return None
    v = variables(record, p)
    names = model()["variables"]
    z = sum((v[n] - mu) / sd * w for n, mu, sd, w in zip(names, role["mu"], role["sd"], role["weight"], strict=True))
    return float(z + role["mean"])


def grade_from_total(total: float, position: str) -> int:
    """The conversion of `coach.grades`: analysis points → 1-100 with the position's Challenger percentiles."""
    cuts = model()["positions"][position]["cuts"]
    return max(1, min(100, round(metric_score("wpa", total, tuple(cuts)))))


def timeline_grades(match_data: JsonDict, timeline: JsonDict) -> dict[str, int]:
    """puuid → 1-100 grade of each player in the match, or {} if it cannot be done (no timeline, short match or no positions)."""
    if not timeline or "info" not in timeline:
        return {}
    record = match_record(match_data, timeline)
    if record["remake"] or not record["frames"]:
        return {}
    grades: dict[str, int] = {}
    for p in record["participants"]:
        try:
            total = predicted_total(record, p)
        except (KeyError, TypeError, ValueError):
            total = None
        if total is not None and p.get("puuid"):
            grades[p["puuid"]] = grade_from_total(total, p["teamPosition"])
    return grades
