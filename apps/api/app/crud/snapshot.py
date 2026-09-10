import logging
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from ygg_core.domain.participant import ParticipantStats

from app.crud.participants import link_snapshot, upsert_participants
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.schemas.snapshot import SnapshotDescriptionUpdate, SnapshotNotesUpdate

logger = logging.getLogger(__name__)


# ── SNAPSHOTS ──────────────────────────────────────────────────────────────────

def get_snapshots_by_player(db: Session, player_id: int, user_id: int) -> list[Snapshot]:
    """Snapshots de un jugador del usuario, del más reciente al más antiguo."""
    stmt = (
        select(Snapshot)
        .join(Snapshot.player)
        .where(Snapshot.player_id == player_id, Player.user_id == user_id)
        .order_by(Snapshot.date_from.desc())
    )
    return list(db.scalars(stmt))


def get_snapshot_by_id(db: Session, snapshot_id: int, user_id: int) -> Snapshot | None:
    """Obtiene un snapshot por ID verificando que pertenece al usuario autenticado."""
    stmt = (
        select(Snapshot)
        .join(Snapshot.player)
        .where(Snapshot.id == snapshot_id, Player.user_id == user_id)
    )
    return db.scalars(stmt).first()


def update_snapshot_description(
    db: Session, snapshot: Snapshot, data: SnapshotDescriptionUpdate
) -> Snapshot:
    snapshot.description = data.description
    db.commit()
    db.refresh(snapshot)
    return snapshot


def update_snapshot_notes(
    db: Session, snapshot: Snapshot, data: SnapshotNotesUpdate
) -> Snapshot:
    snapshot.notes = data.notes
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_snapshot(db: Session, snapshot: Snapshot) -> None:
    """Elimina un snapshot; sus enlaces se borran por ON DELETE CASCADE. Las partidas se quedan."""
    db.delete(snapshot)
    db.commit()


def get_latest_snapshot_for_player(
    db: Session, player_id: int, user_id: int
) -> Snapshot | None:
    stmt = (
        select(Snapshot)
        .join(Snapshot.player)
        .where(Snapshot.player_id == player_id, Player.user_id == user_id)
        .order_by(Snapshot.created_at.desc())
    )
    return db.scalars(stmt).first()


# ── PARTICIPANTES ──────────────────────────────────────────────────────────────

def get_matches_by_snapshot(
    db: Session, snapshot_id: int, user_id: int
) -> list[MatchParticipant]:
    """Partidas (del jugador) de un snapshot del usuario, de la más reciente a la más antigua."""
    stmt = (
        select(MatchParticipant)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .join(Snapshot, Snapshot.id == SnapshotParticipant.snapshot_id)
        .join(Player, Player.id == Snapshot.player_id)
        .where(SnapshotParticipant.snapshot_id == snapshot_id, Player.user_id == user_id)
        .order_by(MatchParticipant.creation_time.desc())
    )
    return list(db.scalars(stmt))


def get_recent_matches_for_player(
    db: Session,
    player_id: int,
    user_id: int,
    limit: int = 20,
    role_filter: str | None = None,
) -> list[MatchParticipant]:
    """Partidas recientes del snapshot más nuevo del jugador."""
    latest = get_latest_snapshot_for_player(db, player_id, user_id)
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
    return list(db.scalars(stmt))


def get_stored_match_ids_for_player(
    db: Session, player_id: int, user_id: int
) -> set[str]:
    """IDs de partida ya enlazados al snapshot más reciente del jugador."""
    latest = get_latest_snapshot_for_player(db, player_id, user_id)
    if not latest:
        return set()
    stmt = (
        select(MatchParticipant.match_id)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .where(SnapshotParticipant.snapshot_id == latest.id)
    )
    return set(db.scalars(stmt))


def persist_participants_to_snapshot(
    db: Session, snapshot: Snapshot, participants: Sequence[ParticipantStats]
) -> None:
    """Guarda las partidas del jugador y las enlaza a un snapshot existente."""
    ids = upsert_participants(db, participants)
    link_snapshot(db, snapshot.id, ids.values())
    db.commit()
