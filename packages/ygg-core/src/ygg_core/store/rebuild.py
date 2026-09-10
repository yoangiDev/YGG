"""Recalcula estadísticas a partir de los payloads crudos guardados, sin llamar a Riot."""

from __future__ import annotations

from ygg_core.riot.parsers import find_participant, parse_participant
from ygg_core.store.duckdb_store import MatchStore
from ygg_core.timeline.enrichment import apply_timeline


def rebuild_participants(store: MatchStore, puuid: str, role_filter: str | None = "ALL") -> int:
    """Vuelve a parsear y enriquecer todas las partidas cacheadas en las que aparece `puuid`.

    Útil al cambiar una fórmula: se itera sobre las métricas sin gastar cuota.
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
