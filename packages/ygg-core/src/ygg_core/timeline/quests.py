"""Tiempos de Role Quest de la temporada 26 a partir del timeline de match-v5.

Descubrimiento (parche 26.1+): la quest se completa con un ITEM_DESTROYED sobre
objetos marcadores de cada rol (1200 TOP, 1201 MID, 1203 SUPPORT, 1204 JUNGLE,
1222 TOP alternativo) o, para ADC, con el ITEM_PURCHASED de su roleBoundItem.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from ygg_core.domain.roles import lane_opponent_id, normalize_role

JsonDict = dict[str, Any]

QUEST_DESTROY_ITEMS: dict[str, frozenset[int]] = {
    "TOP": frozenset({1200, 1222}),
    "MID": frozenset({1201}),
    "JUNGLE": frozenset({1204}),
    "SUPPORT": frozenset({1203}),
    "ADC": frozenset(),
}

# Objetos de recompensa por defecto cuando aún no se ha guardado el real.
DEFAULT_ROLE_BOUND_ITEMS: dict[str, int] = {
    "TOP": 1220,
    "MID": 1206,
    "JUNGLE": 1209,
    "SUPPORT": 1208,
    "ADC": 3020,
}

ADC_ROLE_BOUND_ITEMS = frozenset({3020, 3006, 3008, 3047})

S26_START = datetime(2026, 1, 1, tzinfo=UTC)


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


def resolve_role_bound_item(
    role_bound_item: int | None,
    player_role: str | None,
    creation_time: datetime | None,
    build_items: list[int] | None = None,
) -> int:
    """Objeto de recompensa para mostrar: el guardado o el de por defecto en S26."""
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
    timeline: JsonDict,
    participant_id: int,
    role: str,
    *,
    role_bound_item: int | None = None,
) -> int | None:
    """Segundo en que se completa la quest, o None."""
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
    """Rellena los campos de quest del jugador y de su rival de línea."""
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
