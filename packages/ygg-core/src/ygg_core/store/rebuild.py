"""Recomputes stats from the stored raw payloads, without calling Riot."""

from __future__ import annotations

from ygg_core.riot.parsers import find_participant, parse_participant
from ygg_core.store.duckdb_store import MatchStore
from ygg_core.timeline.enrichment import apply_timeline


def rebuild_participants(store: MatchStore, puuid: str, role_filter: str | None = "ALL") -> int:
    """Re-parses and re-enriches all the cached matches in which `puuid` appears.

    Useful when a formula changes: the metrics are iterated without spending quota.
    """
    rebuilt = []
    for match_id, match_data in store.iter_payloads("match"):
        if find_participant(match_data, puuid) is None:
            continue
        stats = parse_participant(match_data, puuid, role_filter)
        if stats is None:
            continue
        timeline = store.get_payload("timeline", match_id)
        if timeline and "info" in timeline:
            apply_timeline(stats, match_data, timeline, puuid)
        rebuilt.append(stats)
    return store.upsert_participants(rebuilt)
