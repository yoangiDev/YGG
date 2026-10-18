"""The compact record of a Riot match (match + timeline): what the grades and the analyses read.

It comes from the match-v5 match and its timeline, with the timeline reduced to what is used: one frame per minute and player (gold, XP, level,
minions, position, damage to champions) and the events that matter, with each kill's damage breakdown summarised as how much damage the victim dealt and received
and to/from how many enemies. It is the harvest format (`research/ladder`) and the one `metrics/timeline_grade.py` fits.
"""

from __future__ import annotations

from typing import Any

from ygg_core.domain.roles import role_from_position
from ygg_core.riot.parsers import REMAKE_MAX_SECONDS

JsonDict = dict[str, Any]

KEEP_EVENTS = {
    "CHAMPION_KILL",
    "CHAMPION_SPECIAL_KILL",
    "ELITE_MONSTER_KILL",
    "BUILDING_KILL",
    "TURRET_PLATE_DESTROYED",
    "DRAGON_SOUL_GIVEN",
    "WARD_PLACED",
    "WARD_KILL",
    "ITEM_PURCHASED",
    "LEVEL_UP",
    "GAME_END",
}
# Damage breakdown per spell of each kill: it is 3/4 of the match's weight. It is
# summarised as how much damage the victim dealt and received and to/from how many enemies.
FIGHT_DAMAGE_KEYS = {
    "victimTeamfightDamageDealt": "victim_dealt",
    "victimTeamfightDamageReceived": "victim_received",
    "victimDamageDealt": "victim_dealt",
    "victimDamageReceived": "victim_received",
}
FRAME_FIELDS = ["minute", "total_gold", "xp", "level", "minions", "jungle_minions", "x", "y", "damage_to_champions"]


def _participant(p: JsonDict) -> JsonDict:
    record: JsonDict = {k: v for k, v in p.items() if isinstance(v, (int, float, str, bool))}
    record["challenges"] = p.get("challenges") or {}
    styles = (p.get("perks") or {}).get("styles") or []
    record["keystone"] = styles[0]["selections"][0]["perk"] if styles and styles[0].get("selections") else 0
    record["secondary_tree"] = styles[1].get("style", 0) if len(styles) > 1 else 0
    record["role"] = role_from_position(p.get("teamPosition"))
    return record


def _frames(timeline: JsonDict) -> dict[str, list[list[int]]]:
    per_player: dict[str, list[list[int]]] = {}
    for frame in timeline["info"]["frames"]:
        minute = frame["timestamp"] // 60_000
        for pid, pf in frame.get("participantFrames", {}).items():
            position = pf.get("position") or {}
            per_player.setdefault(pid, []).append([
                minute,
                pf.get("totalGold", 0),
                pf.get("xp", 0),
                pf.get("level", 0),
                pf.get("minionsKilled", 0),
                pf.get("jungleMinionsKilled", 0),
                position.get("x", 0),
                position.get("y", 0),
                (pf.get("damageStats") or {}).get("totalDamageDoneToChampions", 0),
            ])
    return per_player


def _damage(hit: JsonDict) -> int:
    return int(hit.get("physicalDamage", 0) + hit.get("magicDamage", 0) + hit.get("trueDamage", 0))


def _compact_event(event: JsonDict) -> JsonDict:
    """A kill: the victim's damage to/from champions and how many distinct enemies, and the turret damage received."""
    compact = {k: v for k, v in event.items() if k not in FIGHT_DAMAGE_KEYS}
    for key, name in FIGHT_DAMAGE_KEYS.items():
        hits = event.get(key) or []
        champions = [h for h in hits if h.get("type") == "OTHER"]  # MINION, MONSTER and TOWER are not champions
        if hits:
            compact[name] = sum(map(_damage, champions))
            compact[f"{name}_champions"] = len({h.get("participantId") for h in champions})
        if name == "victim_received" and hits:
            compact["victim_received_tower"] = sum(_damage(h) for h in hits if h.get("type") == "TOWER")
    return compact


def _events(timeline: JsonDict) -> list[JsonDict]:
    return [
        _compact_event(event)
        for frame in timeline["info"]["frames"]
        for event in frame.get("events", [])
        if event.get("type") in KEEP_EVENTS
    ]


def match_record(match: JsonDict, timeline: JsonDict | None) -> JsonDict:
    info = match["info"]
    return {
        "match_id": match["metadata"]["matchId"],
        "game_version": info.get("gameVersion"),
        "game_creation": info.get("gameCreation"),
        "duration": info.get("gameDuration"),
        "remake": info.get("gameDuration", 0) < REMAKE_MAX_SECONDS,
        "teams": info.get("teams"),
        "participants": [_participant(p) for p in info["participants"]],
        "frame_fields": FRAME_FIELDS,
        "frames": _frames(timeline) if timeline else None,
        "events": _events(timeline) if timeline else None,
    }
