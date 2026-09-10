from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.db.models.user import User
from app.db.models.job import Job
from app.auth.dependencies import get_current_user
from app.schemas.snapshot import (
    SnapshotCreate, SnapshotResponse,
    SnapshotDescriptionUpdate, SnapshotNotesUpdate,
    SnapshotJobResponse, SnapshotJobStatus
)
from app.crud.player import get_player_by_id
from app.crud.snapshot import (
    get_snapshots_by_player, get_snapshot_by_id,
    update_snapshot_description, update_snapshot_notes,
    delete_snapshot
)
from app.service.stats_runner import run_stats_extraction

import asyncio
import uuid

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


# ── GET /snapshots/player/{player_id} ─────────────────────────────────────────

@router.get("/player/{player_id}", response_model=list[SnapshotResponse])
def list_snapshots(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Devuelve todos los snapshots de un jugador."""
    player = get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    return get_snapshots_by_player(db, player_id, user_id=current_user.id)


# ── POST /snapshots ────────────────────────────────────────────────────────────

@router.post("/", response_model=SnapshotJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_snapshot(
    snapshot_in: SnapshotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lanza el análisis de un período para un jugador.
    Devuelve un job_id inmediatamente — el análisis corre en background.
    Flutter hace polling sobre GET /snapshots/jobs/{job_id} hasta que status == 'done'.
    """
    player = get_player_by_id(db, snapshot_in.player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id, status="processing")
    db.add(job)
    db.commit()

    # Pasamos solo el player_id, no el objeto ORM
    # Así evitamos el DetachedInstanceError cuando la sesión del endpoint se cierre
    asyncio.create_task(_run_analysis(job_id, player.id, current_user.id, snapshot_in))

    return SnapshotJobResponse(job_id=job_id)


async def _run_analysis(job_id: str, player_id: int, user_id: int, snapshot_in: SnapshotCreate):
    """
    Tarea background con sesión de BBDD independiente.
    Recibe player_id en lugar del objeto Player para evitar DetachedInstanceError.
    """
    db = SessionLocal()
    try:
        # Recargamos el player dentro de nuestra propia sesión
        player = get_player_by_id(db, player_id, user_id=user_id)
        if not player:
            raise ValueError(f"Player {player_id} not found when starting analysis.")

        snapshot_id = await run_stats_extraction(
            db=db,
            player=player,
            date_from=snapshot_in.date_from,
            date_to=snapshot_in.date_to,
            description=snapshot_in.description,
            job_id=job_id,
        )

        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = "done"
            job.snapshot_id = snapshot_id
            db.commit()

    except Exception as e:
        db.rollback()
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = "error"
            job.error = str(e)
            db.commit()
    finally:
        db.close()


# ── GET /snapshots/jobs/{job_id} ───────────────────────────────────────────────

@router.get("/jobs/{job_id}", response_model=SnapshotJobStatus)
def get_job_status(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Devuelve el estado de un job de análisis.
    Flutter hace polling cada 2s hasta que status == 'done' o 'error'.
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return SnapshotJobStatus(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress if job.progress is not None else 0,
        snapshot_id=job.snapshot_id,
        error=job.error,
    )


# ── GET /snapshots/{snapshot_id} ──────────────────────────────────────────────

@router.get("/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Devuelve un snapshot por su ID."""
    snapshot = get_snapshot_by_id(db, snapshot_id, user_id=current_user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return snapshot


# ── PATCH /snapshots/{snapshot_id}/description ────────────────────────────────

@router.patch("/{snapshot_id}/description", response_model=SnapshotResponse)
def edit_description(
    snapshot_id: int,
    data: SnapshotDescriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza la descripción de un snapshot."""
    snapshot = get_snapshot_by_id(db, snapshot_id, user_id=current_user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return update_snapshot_description(db, snapshot, data)


# ── PATCH /snapshots/{snapshot_id}/notes ──────────────────────────────────────

@router.patch("/{snapshot_id}/notes", response_model=SnapshotResponse)
def edit_notes(
    snapshot_id: int,
    data: SnapshotNotesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza las notas libres de un snapshot (edición inline desde la UI)."""
    snapshot = get_snapshot_by_id(db, snapshot_id, user_id=current_user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return update_snapshot_notes(db, snapshot, data)


# ── DELETE /snapshots/{snapshot_id} ───────────────────────────────────────────

@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina un snapshot y todas sus partidas en cascada."""
    snapshot = get_snapshot_by_id(db, snapshot_id, user_id=current_user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    delete_snapshot(db, snapshot)


# ── GET /snapshots/{snapshot_id}/dashboard ────────────────────────────────────

@router.get("/{snapshot_id}/dashboard")
async def get_snapshot_dashboard(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    compare_game_name: str | None = None,
    compare_tag_line: str | None = None,
    compare_region: str | None = None,
):
    from app.service.dashboard_service import build_snapshot_dashboard

    snapshot = get_snapshot_by_id(db, snapshot_id, user_id=current_user.id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found.")

    return await build_snapshot_dashboard(
        db=db,
        snapshot=snapshot,
        compare_game_name=compare_game_name,
        compare_tag_line=compare_tag_line,
        compare_region=compare_region,
    )