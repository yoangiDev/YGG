import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.db.models.job import Job
from app.db.models.snapshot import Snapshot
from app.db.models.user import User
from app.db.session import SessionLocal, get_db
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
from app.service.stats_runner import run_stats_extraction

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

# Referencias fuertes a los análisis en curso: el event loop solo guarda
# referencias débiles y una tarea sin referencia puede desaparecer a mitad.
_background_tasks: set[asyncio.Task] = set()


async def _owned_snapshot(snapshot_id: int, db: AsyncSession, user: User) -> Snapshot:
    snapshot = await get_snapshot_by_id(db, snapshot_id, user_id=user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return snapshot


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
    responses={429: {"description": "Too many analyses requested"}},
)
async def create_snapshot(
    snapshot_in: SnapshotCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lanza el análisis de un período. Devuelve un job_id; el análisis corre en segundo plano."""
    # Cada análisis cuesta muchas llamadas a Riot: límite estricto por usuario.
    await enforce("snapshots", str(current_user.id), settings.rate_limit_snapshots_per_hour, 3600, response)

    player = await get_player_by_id(db, snapshot_in.player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    job_id = str(uuid.uuid4())
    db.add(Job(job_id=job_id, user_id=current_user.id, status="processing"))
    await db.commit()

    task = asyncio.create_task(_run_analysis(job_id, player.id, current_user.id, snapshot_in))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return SnapshotJobResponse(job_id=job_id)


async def _run_analysis(job_id: str, player_id: int, user_id: int, snapshot_in: SnapshotCreate) -> None:
    """Tarea en segundo plano con su propia sesión: la de la petición ya se cerró."""
    async with SessionLocal() as db:
        try:
            player = await get_player_by_id(db, player_id, user_id=user_id)
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
            job = await db.get(Job, job_id)
            if job:
                job.status = "done"
                job.snapshot_id = snapshot_id
                job.progress = 100
                await db.commit()
        except Exception as e:
            await db.rollback()
            job = await db.get(Job, job_id)
            if job:
                job.status = "error"
                job.error = str(e)
                await db.commit()


@router.get("/jobs/{job_id}", response_model=SnapshotJobStatus)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Estado de un análisis. Solo lo ve quien lo lanzó; para cualquier otro es un 404."""
    job = await db.scalar(select(Job).where(Job.job_id == job_id, Job.user_id == current_user.id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return SnapshotJobStatus(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress if job.progress is not None else 0,
        snapshot_id=job.snapshot_id,
        error=job.error,
    )


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
