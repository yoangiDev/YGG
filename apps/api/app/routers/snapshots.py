import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.crud.player import get_player_by_id
from app.crud.snapshot import (
    delete_snapshot,
    get_snapshot_by_id,
    get_snapshots_by_player,
    update_snapshot_description,
    update_snapshot_notes,
)
from app.db.models.job import Job
from app.db.models.user import User
from app.db.session import SessionLocal, get_db
from app.schemas.snapshot import (
    SnapshotCreate,
    SnapshotDescriptionUpdate,
    SnapshotJobResponse,
    SnapshotJobStatus,
    SnapshotNotesUpdate,
    SnapshotResponse,
)
from app.service.stats_runner import run_stats_extraction

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

# Referencias fuertes a los análisis en curso: sin ellas el event loop solo
# guarda referencias débiles y una tarea puede desaparecer a mitad.
_background_tasks: set[asyncio.Task] = set()


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
    """
    player = get_player_by_id(db, snapshot_in.player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    job_id = str(uuid.uuid4())
    db.add(Job(job_id=job_id, user_id=current_user.id, status="processing"))
    db.commit()

    # Se pasa el player_id y no el objeto ORM: la sesión de esta petición se cierra antes.
    task = asyncio.create_task(_run_analysis(job_id, player.id, current_user.id, snapshot_in))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return SnapshotJobResponse(job_id=job_id)


async def _run_analysis(job_id: str, player_id: int, user_id: int, snapshot_in: SnapshotCreate):
    """Tarea background con su propia sesión de BD."""
    db = SessionLocal()
    try:
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

        job = db.get(Job, job_id)
        if job:
            job.status = "done"
            job.snapshot_id = snapshot_id
            db.commit()

    except Exception as e:
        db.rollback()
        job = db.get(Job, job_id)
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
    Estado de un job de análisis. Solo lo ve quien lo lanzó: para cualquier
    otro usuario responde 404, sin revelar que el job existe.
    """
    job = db.scalar(select(Job).where(Job.job_id == job_id, Job.user_id == current_user.id))
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
    """Elimina un snapshot; las partidas se conservan para otros snapshots."""
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
    from app.service.dashboard import build_snapshot_dashboard

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
