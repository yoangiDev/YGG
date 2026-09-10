"""Persistencia en lote de partidas y participantes.

Sustituye los bucles de `db.query` por partida (P8) por INSERT ... ON CONFLICT:
unas pocas sentencias por análisis, sin importar cuántas partidas tenga.
"""

from collections.abc import Iterable, Iterator, Sequence
from typing import TypeVar

from sqlalchemy import delete, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from ygg_core.domain.participant import ParticipantStats

from app.db.models.match import Match
from app.db.models.participant import MatchParticipant
from app.db.models.player_history import PlayerHistoryEntry
from app.db.models.snapshot_participant import SnapshotParticipant
from app.service.riot import match_row, participant_row

ParticipantKey = tuple[str, str]  # (match_id, puuid)

# Postgres admite 65 535 parámetros por sentencia; ~60 columnas × 500 filas cabe holgado.
CHUNK_SIZE = 500

_KEY_COLUMNS = frozenset({"id", "match_id", "puuid"})
_UPDATABLE_COLUMNS = tuple(
    column.key for column in MatchParticipant.__table__.columns if column.key not in _KEY_COLUMNS
)

T = TypeVar("T")


def _chunks(items: Sequence[T], size: int = CHUNK_SIZE) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def upsert_participants(
    db: Session, participants: Sequence[ParticipantStats]
) -> dict[ParticipantKey, int]:
    """Inserta o actualiza partidas y participantes. Devuelve (match_id, puuid) → id."""
    if not participants:
        return {}

    matches = list({p.match_id: match_row(p) for p in participants}.values())
    for chunk in _chunks(matches):
        db.execute(insert(Match).on_conflict_do_nothing(index_elements=["match_id"]), chunk)

    rows = list({(p.match_id, p.puuid): participant_row(p) for p in participants}.values())
    stmt = insert(MatchParticipant)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_match_participants_match_puuid",
        set_={name: stmt.excluded[name] for name in _UPDATABLE_COLUMNS},
        # Una descarga sin timeline no pisa las métricas de una fila ya enriquecida.
        where=or_(stmt.excluded.timeline_enriched, MatchParticipant.timeline_enriched.is_(False)),
    )
    for chunk in _chunks(rows):
        db.execute(stmt, chunk)

    keys = [(row["match_id"], row["puuid"]) for row in rows]
    ids: dict[ParticipantKey, int] = {}
    for chunk in _chunks(keys):
        result = db.execute(
            select(MatchParticipant.id, MatchParticipant.match_id, MatchParticipant.puuid).where(
                tuple_(MatchParticipant.match_id, MatchParticipant.puuid).in_(chunk)
            )
        )
        ids.update({(row.match_id, row.puuid): row.id for row in result})
    return ids


def link_snapshot(db: Session, snapshot_id: int, participant_ids: Iterable[int]) -> None:
    values = [
        {"snapshot_id": snapshot_id, "match_participant_id": pid}
        for pid in dict.fromkeys(participant_ids)
    ]
    for chunk in _chunks(values):
        db.execute(insert(SnapshotParticipant).on_conflict_do_nothing(), chunk)


def add_history_entries(db: Session, player_id: int, participant_ids: Iterable[int]) -> None:
    values = [
        {"player_id": player_id, "match_participant_id": pid}
        for pid in dict.fromkeys(participant_ids)
    ]
    for chunk in _chunks(values):
        db.execute(insert(PlayerHistoryEntry).on_conflict_do_nothing(), chunk)


def replace_history(db: Session, player_id: int, participant_ids: Sequence[int]) -> None:
    """Deja en el historial exactamente estos participantes, sin borrar y reinsertar los que siguen."""
    ids = list(dict.fromkeys(participant_ids))
    stale = delete(PlayerHistoryEntry).where(PlayerHistoryEntry.player_id == player_id)
    if ids:
        stale = stale.where(PlayerHistoryEntry.match_participant_id.not_in(ids))
    db.execute(stale)
    add_history_entries(db, player_id, ids)


def known_participants(db: Session, puuid: str, match_ids: Sequence[str]) -> dict[str, MatchParticipant]:
    """Filas ya guardadas de ESTE jugador para esas partidas (nunca las de otro)."""
    found: dict[str, MatchParticipant] = {}
    for chunk in _chunks(list(match_ids)):
        rows = db.scalars(
            select(MatchParticipant).where(
                MatchParticipant.puuid == puuid, MatchParticipant.match_id.in_(chunk)
            )
        )
        found.update({row.match_id: row for row in rows})
    return found


def participants_for_snapshot(db: Session, snapshot_id: int) -> list[MatchParticipant]:
    stmt = (
        select(MatchParticipant)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .where(SnapshotParticipant.snapshot_id == snapshot_id)
        .order_by(MatchParticipant.creation_time.desc())
    )
    return list(db.scalars(stmt))
