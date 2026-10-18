"""Season 26 Role Quest times from the match-v5 timeline.

Discovery (patch 26.1+): the quest is completed with an ITEM_DESTROYED on the
marker items of each role (1200 TOP, 1201 MID, 1203 SUPPORT, 1204 JUNGLE,
1222 alternative TOP) or, for ADC, with the ITEM_PURCHASED of its roleBoundItem.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from ygg_core.domain.roles import lane_opponent_id, normalize_role
from ygg_core.domain.season import SEASON_START

JsonDict = dict[str, Any]

QUEST_DESTROY_ITEMS: dict[str, frozenset[int]] = {
    "TOP": frozenset({1200, 1222}),
    "MID": frozenset({1201}),
    "JUNGLE": frozenset({1204}),
    "SUPPORT": frozenset({1203}),
    "ADC": frozenset(),
}

# Default reward items when the real one has not been stored yet.
DEFAULT_ROLE_BOUND_ITEMS: dict[str, int] = {
    "TOP": 1220,
    "MID": 1206,
    "JUNGLE": 1209,
    "SUPPORT": 1208,
    "ADC": 3020,
}

ADC_ROLE_BOUND_ITEMS = frozenset({3020, 3006, 3008, 3047})

# Riot's roleBoundItem is the quest marker while it is in progress (1202 for
# bot) and its reward on completion: the ADC's boots, the top's 1220 Unleashed Teleport,
# the support's 2055 (control wards)...
QUEST_MARKER_ITEMS = frozenset({1202}).union(*QUEST_DESTROY_ITEMS.values())

S26_START = SEASON_START


class QuestFields(Protocol):
    quest_completed: bool
    quest_completion_time: int | None
    enemy_quest_completion_time: int | None
    quest_completion_time_diff: int | None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def is_s26_match(creation_time: datetime | None) -> bool:
    if creation_time is None:
        return False
    return _as_utc(creation_time) >= S26_START


def quest_reward_item(role_bound_item: int | None) -> int:
    """Reward item if the quest was completed, or 0. Doesn't need the timeline."""
    return role_bound_item if role_bound_item and role_bound_item not in QUEST_MARKER_ITEMS else 0


def extract_quest_completion_time(
    timeline: JsonDict,
    participant_id: int,
    role: str,
    *,
    role_bound_item: int | None = None,
) -> int | None:
    """Second at which the quest is completed, or None."""
    role = normalize_role(role)
    destroy_ids = QUEST_DESTROY_ITEMS.get(role, frozenset())
    first: int | None = None

    for frame in timeline.get("info", {}).get("frames", []):
        for event in frame.get("events", []):
            if event.get("participantId") != participant_id:
                continue
            ts = event.get("timestamp", 0) // 1000
            is_destroy = event.get("type") == "ITEM_DESTROYED" and event.get("itemId") in destroy_ids
            is_adc_purchase = (
                role == "ADC"
                and event.get("type") == "ITEM_PURCHASED"
                and bool(role_bound_item)
                and event.get("itemId") == role_bound_item
            )
            if (is_destroy or is_adc_purchase) and (first is None or ts < first):
                first = ts
    return first


def apply_role_quest_stats(
    target: QuestFields,
    timeline: JsonDict,
    participant_id: int,
    *,
    player_role: str | None,
    participants: list[JsonDict],
) -> None:
    """Fills in the quest fields of the player and their lane opponent."""
    by_id = {p["participantId"]: p for p in participants}
    player = by_id.get(participant_id, {})
    role_bound_item = player.get("roleBoundItem") or 0

    if not role_bound_item:
        target.quest_completed = False
        target.quest_completion_time = None
        target.enemy_quest_completion_time = None
        target.quest_completion_time_diff = None
        return

    role = normalize_role(player_role or player.get("teamPosition", ""))
    player_time = extract_quest_completion_time(
        timeline, participant_id, role, role_bound_item=role_bound_item
    )

    opponent_id = lane_opponent_id(participant_id)
    opponent = by_id.get(opponent_id, {})
    enemy_time = None
    if opponent:
        enemy_time = extract_quest_completion_time(
            timeline,
            opponent_id,
            normalize_role(opponent.get("teamPosition", "")),
            role_bound_item=opponent.get("roleBoundItem"),
        )

    target.quest_completed = player_time is not None
    target.quest_completion_time = player_time
    target.enemy_quest_completion_time = enemy_time
    target.quest_completion_time_diff = (
        player_time - enemy_time if player_time is not None and enemy_time is not None else None
    )
