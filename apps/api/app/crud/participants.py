"""Batch persistence of matches and participants.

Replaces the per-match query loops (P8) with INSERT ... ON CONFLICT:
a few statements per analysis, however many matches it has.
"""

from collections.abc import Iterable, Iterator, Sequence
from itertools import batched
from typing import TypeVar

from sqlalchemy import or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import ParticipantStats

from app.db.models.match import Match
from app.db.models.participant import MatchParticipant
from app.db.models.player_history import PlayerHistoryEntry
from app.db.models.snapshot_participant import SnapshotParticipant
from app.service.riot import match_row, participant_row

ParticipantKey = tuple[str, str]  # (match_id, puuid)

# Postgres supports 65,535 parameters per statement; ~60 columns × 500 rows fits comfortably.
CHUNK_SIZE = 500

_KEY_COLUMNS = frozenset({"id", "match_id", "puuid"})
_UPDATABLE_COLUMNS = tuple(
    column.key for column in MatchParticipant.__table__.columns if column.key not in _KEY_COLUMNS
)

T = TypeVar("T")


def _chunks(items: Iterable[T]) -> Iterator[list[T]]:
    # As lists: with a tuple, the ORM INSERT doesn't treat it as a batch of rows.
    return map(list, batched(items, CHUNK_SIZE))


async def upsert_participants(
    db: AsyncSession, participants: Sequence[ParticipantStats]
) -> dict[ParticipantKey, int]:
    """Inserts or updates matches and participants. Returns (match_id, puuid) → id."""
    if not participants:
        return {}

    matches = list({p.match_id: match_row(p) for p in participants}.values())
    for chunk in _chunks(matches):
        await db.execute(insert(Match).on_conflict_do_nothing(index_elements=["match_id"]), chunk)

    rows = list({(p.match_id, p.puuid): participant_row(p) for p in participants}.values())
    stmt = insert(MatchParticipant)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_match_participants_match_puuid",
        set_={name: stmt.excluded[name] for name in _UPDATABLE_COLUMNS},
        # A download without a timeline doesn't overwrite the metrics of an already enriched row.
        where=or_(stmt.excluded.timeline_enriched, MatchParticipant.timeline_enriched.is_(False)),
    )
    for chunk in _chunks(rows):
        await db.execute(stmt, chunk)

    keys = [(row["match_id"], row["puuid"]) for row in rows]
    ids: dict[ParticipantKey, int] = {}
    for chunk in _chunks(keys):
        result = await db.execute(
            select(MatchParticipant.id, MatchParticipant.match_id, MatchParticipant.puuid).where(
                tuple_(MatchParticipant.match_id, MatchParticipant.puuid).in_(chunk)
            )
        )
        ids.update({(row.match_id, row.puuid): row.id for row in result})
    return ids


async def link_snapshot(db: AsyncSession, snapshot_id: int, participant_ids: Iterable[int]) -> None:
    values = [
        {"snapshot_id": snapshot_id, "match_participant_id": pid}
        for pid in dict.fromkeys(participant_ids)
    ]
    for chunk in _chunks(values):
        await db.execute(insert(SnapshotParticipant).on_conflict_do_nothing(), chunk)


async def add_history_entries(db: AsyncSession, player_id: int, participant_ids: Iterable[int]) -> None:
    values = [
        {"player_id": player_id, "match_participant_id": pid}
        for pid in dict.fromkeys(participant_ids)
    ]
    for chunk in _chunks(values):
        await db.execute(insert(PlayerHistoryEntry).on_conflict_do_nothing(), chunk)


async def known_participants(
    db: AsyncSession, puuid: str, match_ids: Sequence[str]
) -> dict[str, MatchParticipant]:
    """Already stored rows of THIS player for those matches (never another player's)."""
    found: dict[str, MatchParticipant] = {}
    for chunk in _chunks(match_ids):
        rows = await db.scalars(
            select(MatchParticipant).where(
                MatchParticipant.puuid == puuid, MatchParticipant.match_id.in_(chunk)
            )
        )
        found.update({row.match_id: row for row in rows})
    return found


async def participants_for_snapshot(db: AsyncSession, snapshot_id: int) -> list[MatchParticipant]:
    stmt = (
        select(MatchParticipant)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .where(SnapshotParticipant.snapshot_id == snapshot_id)
        .order_by(MatchParticipant.creation_time.desc())
    )
    return list(await db.scalars(stmt))


async def snapshot_ids_for_participants(db: AsyncSession, participant_ids: Iterable[int]) -> list[int]:
    """Snapshots that contain any of these participants (to invalidate their cache)."""
    ids = list(dict.fromkeys(participant_ids))
    snapshot_ids: set[int] = set()
    for chunk in _chunks(ids):
        result = await db.scalars(
            select(SnapshotParticipant.snapshot_id)
            .where(SnapshotParticipant.match_participant_id.in_(chunk))
            .distinct()
        )
        snapshot_ids.update(result)
    return sorted(snapshot_ids)
