import logging
from sqlalchemy.orm import Session

from app.db.models.snapshot import Snapshot
from app.db.models.match import Match
from app.schemas.snapshot import SnapshotDescriptionUpdate, SnapshotNotesUpdate

logger = logging.getLogger(__name__)


# ── SNAPSHOTS ──────────────────────────────────────────────────────────────────

def get_snapshots_by_player(db: Session, player_id: int, user_id: int) -> list[Snapshot]:
    """
    Devuelve los snapshots de un jugador verificando que pertenece al usuario.
    Ordenados del más reciente al más antiguo.
    """
    return (
        db.query(Snapshot)
        .join(Snapshot.player)
        .filter(
            Snapshot.player_id == player_id,
            Snapshot.player.has(user_id=user_id),   # Seguridad: solo snapshots del usuario
        )
        .order_by(Snapshot.date_from.desc())
        .all()
    )


def get_snapshot_by_id(db: Session, snapshot_id: int, user_id: int) -> Snapshot | None:
    """Obtiene un snapshot por ID verificando que pertenece al usuario autenticado."""
    return (
        db.query(Snapshot)
        .join(Snapshot.player)
        .filter(
            Snapshot.id == snapshot_id,
            Snapshot.player.has(user_id=user_id),
        )
        .first()
    )


def update_snapshot_description(
    db: Session, snapshot: Snapshot, data: SnapshotDescriptionUpdate
) -> Snapshot:
    """Actualiza la descripción de un snapshot."""
    snapshot.description = data.description
    db.commit()
    db.refresh(snapshot)
    return snapshot


def update_snapshot_notes(
    db: Session, snapshot: Snapshot, data: SnapshotNotesUpdate
) -> Snapshot:
    """Actualiza las notas libres de un snapshot (edición inline desde la UI)."""
    snapshot.notes = data.notes
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_snapshot(db: Session, snapshot: Snapshot) -> None:
    """Elimina un snapshot; match_snapshots se borra por ON DELETE CASCADE del FK."""
    db.delete(snapshot)
    db.commit()


# ── MATCHES ────────────────────────────────────────────────────────────────────

def get_matches_by_snapshot(
    db: Session, snapshot_id: int, user_id: int
) -> list[Match]:
    """
    Devuelve las partidas de un snapshot verificando que pertenece al usuario.
    Ordenadas de la más reciente a la más antigua.
    """
    from app.db.models.match_snapshot import MatchSnapshot
    
    return (
        db.query(Match)
        .join(MatchSnapshot, MatchSnapshot.match_id == Match.id)
        .join(Snapshot, Snapshot.id == MatchSnapshot.snapshot_id)
        .join(Snapshot.player)
        .filter(
            MatchSnapshot.snapshot_id == snapshot_id,
            Snapshot.player.has(user_id=user_id),
        )
        .order_by(Match.creation_time.desc())
        .all()
    )


def get_latest_snapshot_for_player(
    db: Session, player_id: int, user_id: int
) -> Snapshot | None:
    return (
        db.query(Snapshot)
        .join(Snapshot.player)
        .filter(
            Snapshot.player_id == player_id,
            Snapshot.player.has(user_id=user_id),
        )
        .order_by(Snapshot.created_at.desc())
        .first()
    )


def get_recent_matches_for_player(
    db: Session,
    player_id: int,
    user_id: int,
    limit: int = 20,
    role_filter: str | None = None,
) -> list[Match]:
    """Partidas recientes del snapshot más nuevo del jugador."""
    latest = get_latest_snapshot_for_player(db, player_id, user_id)
    if not latest:
        return []

    matches = get_matches_by_snapshot(db, latest.id, user_id)
    if role_filter and role_filter.upper() != "ALL":
        role = role_filter.upper()
        matches = [
            m for m in matches
            if not m.player_role or m.player_role.upper() == role
        ]
    return matches[:limit]


def get_stored_match_ids_for_player(
    db: Session, player_id: int, user_id: int
) -> set[str]:
    """Riot match_id strings already linked to the player's latest snapshot."""
    latest = get_latest_snapshot_for_player(db, player_id, user_id)
    if not latest:
        return set()
    matches = get_matches_by_snapshot(db, latest.id, user_id)
    return {m.match_id for m in matches}


def persist_matches_to_snapshot(
    db: Session, snapshot: Snapshot, matches: list[Match]
) -> None:
    """Upsert match rows and link them to an existing snapshot."""
    from sqlalchemy.exc import IntegrityError

    from app.service.riot_client import copy_timeline_fields
    from app.db.models.match_snapshot import MatchSnapshot

    for match in matches:
        existing_match = db.query(Match).filter(Match.match_id == match.match_id).first()

        if existing_match:
            copy_timeline_fields(existing_match, match)
            if match.timeline_enriched:
                existing_match.timeline_enriched = True
            target = existing_match
        else:
            try:
                sp = db.begin_nested()
                db.add(match)
                db.flush()
                target = match
            except IntegrityError:
                sp.rollback()
                existing_match = (
                    db.query(Match).filter(Match.match_id == match.match_id).first()
                )
                if not existing_match:
                    continue
                copy_timeline_fields(existing_match, match)
                if match.timeline_enriched:
                    existing_match.timeline_enriched = True
                target = existing_match

        try:
            sp = db.begin_nested()
            db.add(MatchSnapshot(snapshot_id=snapshot.id, match_id=target.id))
            sp.commit()
        except IntegrityError:
            sp.rollback()

    db.commit()