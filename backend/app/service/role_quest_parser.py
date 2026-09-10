"""Extract Season 26 Role Quest completion times from match v5 timeline data.

Discovery (Patch 26.1+): quest completion is signaled by ITEM_DESTROYED on
role-specific placeholder items (1200 TOP, 1201 MID, 1203 SUPPORT, 1204 JUNGLE,
1222 TOP alt) or ITEM_PURCHASED of the participant's roleBoundItem for ADC.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.match import Match

# Placeholder items destroyed when the lane role quest completes.
QUEST_DESTROY_ITEMS: dict[str, set[int]] = {
    "TOP": {1200, 1222},
    "MID": {1201},
    "JUNGLE": {1204},
    "SUPPORT": {1203},
    "ADC": set(),
}

_RIOT_ROLE_TO_INTERNAL = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MIDDLE": "MID",
    "MID": "MID",
    "BOTTOM": "ADC",
    "ADC": "ADC",
    "UTILITY": "SUPPORT",
    "SUPPORT": "SUPPORT",
}


def normalize_role(role: str | None) -> str:
    if not role:
        return "UNKNOWN"
    return _RIOT_ROLE_TO_INTERNAL.get(role.upper(), role.upper())


def lane_opponent_id(participant_id: int) -> int:
    return participant_id + 5 if participant_id <= 5 else participant_id - 5


# Default role-bound reward items (Season 26) when not stored in DB yet.
DEFAULT_ROLE_BOUND_ITEMS: dict[str, int] = {
    "TOP": 1220,
    "MID": 1206,
    "JUNGLE": 1209,
    "SUPPORT": 1208,
    "ADC": 3020,
}

ADC_ROLE_BOUND_ITEMS = frozenset({3020, 3006, 3008, 3047})

S26_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_s26_match(creation_time: datetime | None) -> bool:
    if creation_time is None:
        return False
    return _as_utc(creation_time) >= S26_START


def resolve_role_bound_item(
    role_bound_item: int,
    player_role: str | None,
    creation_time: datetime | None,
    build_items: list[int] | None = None,
) -> int:
    """Resolve quest reward item id for display (stored value or S26 fallback)."""
    if role_bound_item:
        return role_bound_item
    if not is_s26_match(creation_time):
        return 0
    role = normalize_role(player_role or "")
    if role == "ADC" and build_items:
        for item_id in build_items:
            if item_id in ADC_ROLE_BOUND_ITEMS:
                return item_id
    return DEFAULT_ROLE_BOUND_ITEMS.get(role, 0)


def extract_quest_completion_time(
    timeline: dict,
    participant_id: int,
    role: str,
    *,
    role_bound_item: int | None = None,
) -> int | None:
    """Return quest completion time in seconds from game start, or None."""
    role = normalize_role(role)
    destroy_ids = QUEST_DESTROY_ITEMS.get(role, set())
    first: int | None = None

    for frame in timeline.get("info", {}).get("frames", []):
        for event in frame.get("events", []):
            if event.get("participantId") != participant_id:
                continue
            ts = event.get("timestamp", 0) // 1000
            if event.get("type") == "ITEM_DESTROYED" and event.get("itemId") in destroy_ids:
                if first is None or ts < first:
                    first = ts
            if (
                role == "ADC"
                and event.get("type") == "ITEM_PURCHASED"
                and role_bound_item
                and event.get("itemId") == role_bound_item
            ):
                if first is None or ts < first:
                    first = ts

    return first


def apply_role_quest_stats(
    match: Match,
    timeline: dict,
    participant_id: int,
    *,
    player_role: str | None,
    participants: list[dict],
) -> None:
    """Populate quest completion fields on a Match from timeline + participants."""
    participants_by_id = {p["participantId"]: p for p in participants}
    player_part = participants_by_id.get(participant_id, {})
    role_bound_item = player_part.get("roleBoundItem") or 0

    if not role_bound_item:
        match.quest_completed = False
        match.quest_completion_time = None
        match.enemy_quest_completion_time = None
        match.quest_completion_time_diff = None
        return

    role = normalize_role(
        player_role or player_part.get("teamPosition", "")
    )
    player_time = extract_quest_completion_time(
        timeline,
        participant_id,
        role,
        role_bound_item=role_bound_item,
    )

    opponent_id = lane_opponent_id(participant_id)
    opponent_part = participants_by_id.get(opponent_id, {})
    opponent_role = normalize_role(opponent_part.get("teamPosition", ""))
    enemy_time = None
    if opponent_part:
        enemy_time = extract_quest_completion_time(
            timeline,
            opponent_id,
            opponent_role,
            role_bound_item=opponent_part.get("roleBoundItem"),
        )

    match.quest_completed = player_time is not None
    match.quest_completion_time = player_time
    match.enemy_quest_completion_time = enemy_time
    match.quest_completion_time_diff = (
        player_time - enemy_time
        if player_time is not None and enemy_time is not None
        else None
    )
