import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.schemas.snapshot import SnapshotDescriptionUpdate, SnapshotNotesUpdate
from app.service.dashboard_cache import invalidate_dashboards

logger = logging.getLogger(__name__)


async def _count(db: AsyncSession, stmt) -> int:
    return await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


# ── SNAPSHOTS ──────────────────────────────────────────────────────────────────

async def get_snapshots_by_player(
    db: AsyncSession, player_id: int, user_id: int, *, limit: int | None = None, offset: int = 0
) -> tuple[list[Snapshot], int]:
    """Snapshots of one of the user's players, from newest to oldest, and the total."""
    stmt = (
        select(Snapshot)
        .join(Player, Player.id == Snapshot.player_id)
        .where(Snapshot.player_id == player_id, Player.user_id == user_id)
        .order_by(Snapshot.date_from.desc())
    )
    total = await _count(db, stmt)
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list(await db.scalars(stmt)), total


async def get_snapshot_by_id(db: AsyncSession, snapshot_id: int, user_id: int) -> Snapshot | None:
    """Gets a snapshot by ID, verifying that it belongs to the authenticated user."""
    stmt = (
        select(Snapshot)
        .join(Player, Player.id == Snapshot.player_id)
        .where(Snapshot.id == snapshot_id, Player.user_id == user_id)
    )
    return await db.scalar(stmt)


async def update_snapshot_description(
    db: AsyncSession, snapshot: Snapshot, data: SnapshotDescriptionUpdate
) -> Snapshot:
    snapshot.description = data.description
    await db.commit()
    await db.refresh(snapshot)
    await invalidate_dashboards([snapshot.id])
    return snapshot


async def update_snapshot_notes(
    db: AsyncSession, snapshot: Snapshot, data: SnapshotNotesUpdate
) -> Snapshot:
    snapshot.notes = data.notes
    await db.commit()
    await db.refresh(snapshot)
    await invalidate_dashboards([snapshot.id])
    return snapshot


async def delete_snapshot(db: AsyncSession, snapshot: Snapshot) -> None:
    """Deletes a snapshot; its links are removed by ON DELETE CASCADE. The matches stay."""
    snapshot_id = snapshot.id
    await db.delete(snapshot)
    await db.commit()
    await invalidate_dashboards([snapshot_id])


# ── PARTICIPANTS ───────────────────────────────────────────────────────────────

def _snapshot_matches(snapshot_id: int, user_id: int):
    """Matches (of the player) in a snapshot, if the snapshot is the user's."""
    return (
        select(MatchParticipant)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .join(Snapshot, Snapshot.id == SnapshotParticipant.snapshot_id)
        .join(Player, Player.id == Snapshot.player_id)
        .where(SnapshotParticipant.snapshot_id == snapshot_id, Player.user_id == user_id)
    )


async def get_snapshot_match(db: AsyncSession, snapshot_id: int, user_id: int, match_id: str) -> MatchParticipant | None:
    return await db.scalar(_snapshot_matches(snapshot_id, user_id).where(MatchParticipant.match_id == match_id))


async def get_matches_page(
    db: AsyncSession, snapshot_id: int, user_id: int, *, limit: int, offset: int
) -> tuple[list[MatchParticipant], int]:
    """Matches (of the player) in one of the user's snapshots, from newest to oldest, and the total."""
    stmt = _snapshot_matches(snapshot_id, user_id).order_by(MatchParticipant.creation_time.desc())
    total = await _count(db, stmt)
    return list(await db.scalars(stmt.limit(limit).offset(offset))), total
