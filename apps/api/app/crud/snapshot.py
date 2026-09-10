import logging
from collections.abc import Sequence

from sqlalchemy import RowMapping, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import ParticipantStats

from app.crud.participants import link_snapshot, upsert_participants
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.queries import load
from app.schemas.snapshot import SnapshotDescriptionUpdate, SnapshotNotesUpdate
from app.service.dashboard_cache import (
    invalidate_dashboards,
    invalidate_dashboards_for_participants,
)

logger = logging.getLogger(__name__)


async def _count(db: AsyncSession, stmt) -> int:
    return await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


# ── SNAPSHOTS ──────────────────────────────────────────────────────────────────

async def get_snapshots_by_player(
    db: AsyncSession, player_id: int, user_id: int, *, limit: int | None = None, offset: int = 0
) -> tuple[list[Snapshot], int]:
    """Snapshots de un jugador del usuario, del más reciente al más antiguo, y el total."""
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
    """Obtiene un snapshot por ID verificando que pertenece al usuario autenticado."""
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
    """Elimina un snapshot; sus enlaces se borran por ON DELETE CASCADE. Las partidas se quedan."""
    snapshot_id = snapshot.id
    await db.delete(snapshot)
    await db.commit()
    await invalidate_dashboards([snapshot_id])


async def get_latest_snapshot_for_player(
    db: AsyncSession, player_id: int, user_id: int
) -> Snapshot | None:
    stmt = (
        select(Snapshot)
        .join(Player, Player.id == Snapshot.player_id)
        .where(Snapshot.player_id == player_id, Player.user_id == user_id)
        .order_by(Snapshot.created_at.desc())
        .limit(1)
    )
    return await db.scalar(stmt)


# ── PARTICIPANTES ──────────────────────────────────────────────────────────────

def _snapshot_matches_stmt(snapshot_id: int, user_id: int):
    return (
        select(MatchParticipant)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .join(Snapshot, Snapshot.id == SnapshotParticipant.snapshot_id)
        .join(Player, Player.id == Snapshot.player_id)
        .where(SnapshotParticipant.snapshot_id == snapshot_id, Player.user_id == user_id)
        .order_by(MatchParticipant.creation_time.desc())
    )


async def get_matches_by_snapshot(
    db: AsyncSession, snapshot_id: int, user_id: int
) -> list[MatchParticipant]:
    """Partidas (del jugador) de un snapshot del usuario, de la más reciente a la más antigua."""
    return list(await db.scalars(_snapshot_matches_stmt(snapshot_id, user_id)))


async def get_matches_page(
    db: AsyncSession, snapshot_id: int, user_id: int, *, limit: int, offset: int
) -> tuple[list[MatchParticipant], int]:
    stmt = _snapshot_matches_stmt(snapshot_id, user_id)
    total = await _count(db, stmt)
    return list(await db.scalars(stmt.limit(limit).offset(offset))), total


async def snapshot_summary(db: AsyncSession, snapshot_id: int) -> RowMapping:
    result = await db.execute(load("snapshot_summary"), {"snapshot_id": snapshot_id})
    return result.mappings().one()


async def get_recent_matches_for_player(
    db: AsyncSession,
    player_id: int,
    user_id: int,
    limit: int = 20,
    role_filter: str | None = None,
) -> list[MatchParticipant]:
    """Partidas recientes del snapshot más nuevo del jugador."""
    latest = await get_latest_snapshot_for_player(db, player_id, user_id)
    if not latest:
        return []

    stmt = (
        select(MatchParticipant)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .where(SnapshotParticipant.snapshot_id == latest.id)
        .order_by(MatchParticipant.creation_time.desc())
        .limit(limit)
    )
    if role_filter and role_filter.upper() != "ALL":
        stmt = stmt.where(
            or_(MatchParticipant.player_role == role_filter.upper(), MatchParticipant.player_role == "UNKNOWN")
        )
    return list(await db.scalars(stmt))


async def get_stored_match_ids_for_player(
    db: AsyncSession, player_id: int, user_id: int
) -> set[str]:
    """IDs de partida ya enlazados al snapshot más reciente del jugador."""
    latest = await get_latest_snapshot_for_player(db, player_id, user_id)
    if not latest:
        return set()
    stmt = (
        select(MatchParticipant.match_id)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .where(SnapshotParticipant.snapshot_id == latest.id)
    )
    return set(await db.scalars(stmt))


async def persist_participants_to_snapshot(
    db: AsyncSession, snapshot: Snapshot, participants: Sequence[ParticipantStats]
) -> None:
    """Guarda las partidas del jugador, las enlaza a un snapshot existente e invalida cachés."""
    ids = await upsert_participants(db, participants)
    await link_snapshot(db, snapshot.id, ids.values())
    await db.commit()
    await invalidate_dashboards([snapshot.id])
    await invalidate_dashboards_for_participants(db, ids.values())
