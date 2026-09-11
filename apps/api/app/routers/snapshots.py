import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limit import enforce
from app.crud.player import get_player_by_id
from app.crud.snapshot import (
    delete_snapshot,
    get_snapshot_by_id,
    get_snapshots_by_player,
    update_snapshot_description,
    update_snapshot_notes,
)
from app.db.models.job import ACTIVE_JOB_STATUSES, Job
from app.db.models.snapshot import Snapshot
from app.db.models.user import User
from app.db.session import get_db
from app.jobs.progress import job_event_stream, job_status_from_row, publish_job_state, update_job
from app.jobs.queue import JobQueue, get_job_queue
from app.schemas.common import Page, PageParams
from app.schemas.dashboard import SnapshotDashboardResponse
from app.schemas.snapshot import (
    SnapshotCreate,
    SnapshotDescriptionUpdate,
    SnapshotJobResponse,
    SnapshotJobStatus,
    SnapshotNotesUpdate,
    SnapshotResponse,
)
from app.service.dashboard import get_snapshot_dashboard

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


async def _owned_snapshot(snapshot_id: int, db: AsyncSession, user: User) -> Snapshot:
    snapshot = await get_snapshot_by_id(db, snapshot_id, user_id=user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return snapshot


async def _owned_job(job_id: str, db: AsyncSession, user: User) -> Job:
    """Solo quien lanzó el job lo ve; para cualquier otro es un 404 (no revela que existe)."""
    job = await db.scalar(select(Job).where(Job.job_id == job_id, Job.user_id == user.id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


async def _enqueue(queue: JobQueue, job: Job) -> None:
    await publish_job_state(job_status_from_row(job))
    try:
        await queue.enqueue_analysis(job.job_id)
    except Exception as exc:
        logger.error("job_enqueue_failed", job_id=job.job_id, error=str(exc))
        await update_job(job.job_id, status="error", error="Could not queue the analysis. Try again.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Analysis queue unavailable."
        ) from exc


@router.get("/player/{player_id}", response_model=Page[SnapshotResponse])
async def list_snapshots(
    player_id: int,
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Snapshots de un jugador, del más reciente al más antiguo."""
    if not await get_player_by_id(db, player_id, user_id=current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    snapshots, total = await get_snapshots_by_player(
        db, player_id, current_user.id, limit=page.limit, offset=page.offset
    )
    return Page[SnapshotResponse](
        items=[SnapshotResponse.model_validate(s) for s in snapshots],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/",
    response_model=SnapshotJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={429: {"description": "Too many analyses requested"}, 503: {"description": "Queue unavailable"}},
)
async def create_snapshot(
    snapshot_in: SnapshotCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """Encola el análisis de un período y devuelve su job.

    Idempotente: si ya hay un análisis en marcha del mismo jugador y rango, se
    devuelve ese job en lugar de lanzar otro. El progreso se sigue por SSE en
    GET /snapshots/jobs/{job_id}/stream.
    """
    # Cada análisis cuesta muchas llamadas a Riot: límite estricto por usuario.
    await enforce("snapshots", str(current_user.id), settings.rate_limit_snapshots_per_hour, 3600, response)

    player = await get_player_by_id(db, snapshot_in.player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    same_request = select(Job).where(
        Job.user_id == current_user.id,
        Job.player_id == player.id,
        Job.date_from == snapshot_in.date_from,
        Job.date_to == snapshot_in.date_to,
        Job.status.in_(ACTIVE_JOB_STATUSES),
    )
    if existing := await db.scalar(same_request):
        return SnapshotJobResponse(job_id=existing.job_id, status=existing.status)

    job = Job(
        job_id=str(uuid.uuid4()),
        user_id=current_user.id,
        player_id=player.id,
        date_from=snapshot_in.date_from,
        date_to=snapshot_in.date_to,
        description=snapshot_in.description,
        status="queued",
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError:
        # Otra petición idéntica ganó la carrera: el índice único parcial lo impide.
        await db.rollback()
        if existing := await db.scalar(same_request):
            return SnapshotJobResponse(job_id=existing.job_id, status=existing.status)
        raise

    await _enqueue(queue, job)
    return SnapshotJobResponse(job_id=job.job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=SnapshotJobStatus)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return job_status_from_row(await _owned_job(job_id, db, current_user))


@router.get(
    "/jobs/{job_id}/stream",
    response_class=EventSourceResponse,
    responses={200: {"description": "Eventos `progress`, `done` y `error` con un SnapshotJobStatus en JSON",
                     "content": {"text/event-stream": {}}}},
)
async def stream_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Progreso en tiempo real por Server-Sent Events.

    SSE y no WebSockets: el flujo es unidireccional, funciona sobre HTTP normal
    y el navegador se reconecta solo. Al conectar (o reconectar) se envía
    primero el estado actual.
    """
    job = await _owned_job(job_id, db, current_user)
    return EventSourceResponse(
        job_event_stream(job_id, job_status_from_row(job), request.is_disconnected),
        ping=15,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=SnapshotJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"description": "The job has not failed, or an equivalent analysis is running"}},
)
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    queue: JobQueue = Depends(get_job_queue),
):
    """Vuelve a encolar un análisis fallido (por ejemplo, uno interrumpido)."""
    job = await _owned_job(job_id, db, current_user)
    if job.status != "error" or job.player_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed analyses can be retried.")

    job.status, job.error, job.progress, job.finished_at = "queued", None, 0, None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An equivalent analysis is already running."
        ) from exc

    await _enqueue(queue, job)
    return job_status_from_row(job)


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(snapshot_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await _owned_snapshot(snapshot_id, db, current_user)


@router.patch("/{snapshot_id}/description", response_model=SnapshotResponse)
async def edit_description(
    snapshot_id: int,
    data: SnapshotDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_snapshot_description(db, await _owned_snapshot(snapshot_id, db, current_user), data)


@router.patch("/{snapshot_id}/notes", response_model=SnapshotResponse)
async def edit_notes(
    snapshot_id: int,
    data: SnapshotNotesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_snapshot_notes(db, await _owned_snapshot(snapshot_id, db, current_user), data)


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_snapshot(
    snapshot_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Elimina un snapshot; las partidas se conservan para otros snapshots."""
    await delete_snapshot(db, await _owned_snapshot(snapshot_id, db, current_user))


@router.get("/{snapshot_id}/dashboard", response_model=SnapshotDashboardResponse)
async def read_snapshot_dashboard(
    snapshot_id: int,
    compare_game_name: str | None = None,
    compare_tag_line: str | None = None,
    compare_region: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard del snapshot (cacheado). `compare_*` superpone en vivo el radar de otra cuenta."""
    snapshot = await _owned_snapshot(snapshot_id, db, current_user)
    return await get_snapshot_dashboard(db, snapshot, compare_game_name, compare_tag_line, compare_region)
