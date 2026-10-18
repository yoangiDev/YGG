import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import distinct, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.dependencies import get_current_user, is_premium, require_premium
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
from app.db.models.match import Match
from app.db.models.participant import MatchParticipant
from app.db.models.premium_analysis import PremiumAnalysis
from app.db.models.snapshot import Snapshot
from app.db.models.user import User
from app.db.session import get_db
from app.jobs.progress import job_event_stream, job_status_from_row, publish_job_state, update_job
from app.jobs.queue import JobQueue, get_job_queue
from app.schemas.common import Page, PageParams, Region
from app.schemas.dashboard import SnapshotDashboardResponse
from app.schemas.snapshot import (
    PremiumAnalysisResponse,
    PremiumCoverage,
    SnapshotCreate,
    SnapshotDescriptionUpdate,
    SnapshotJobResponse,
    SnapshotJobStatus,
    SnapshotNotesUpdate,
    SnapshotResponse,
)
from app.service.dashboard import get_snapshot_dashboard
from app.service.premium import in_coverage, refresh, request_premium, skip_waiting, waiting

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


async def _owned_snapshot(snapshot_id: int, db: AsyncSession, user: User) -> Snapshot:
    snapshot = await get_snapshot_by_id(db, snapshot_id, user_id=user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return snapshot


async def _owned_job(job_id: str, db: AsyncSession, user: User) -> Job:
    """Only whoever launched the job sees it; for anyone else it is a 404 (it doesn't reveal that it exists)."""
    job = await db.scalar(select(Job).where(Job.job_id == job_id, Job.user_id == user.id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


def _check_premium_request(user: User, date_from: int) -> None:
    """A replay analysis: an account with replay access, and a period for which replays and the patch's exe already exist."""
    if not is_premium(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="premium_required")
    if not in_coverage(date_from):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Replay analyses start on {settings.premium_since:%Y-%m-%d}: pick a later start date.",
        )


async def _one_build(db: AsyncSession, puuid: str, date_from: int, date_to: int) -> None:
    """A snapshot doesn't cross builds: each build (16.19.820, .821, .823…) has its own type table and its
    matches are not compared with those of another. It looks at the already stored history, which is what the web just
    showed in the sessions, so it costs no Riot calls. Matches without a version (from before it was stored)
    don't count."""
    since, until = datetime.fromtimestamp(date_from, UTC), datetime.fromtimestamp(date_to, UTC)
    versions = await db.scalars(
        select(distinct(Match.game_version)).join(MatchParticipant, MatchParticipant.match_id == Match.match_id)
        .where(MatchParticipant.puuid == puuid, MatchParticipant.creation_time.between(since, until),
               Match.game_version != ""))
    builds = {".".join(v.split(".")[:3]) for v in versions}
    if len(builds) > 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"A snapshot must stay within one game build; this period has {len(builds)}.")


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
    """A player's snapshots, from newest to oldest."""
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
    current_user: User = Depends(require_premium),
    queue: JobQueue = Depends(get_job_queue),
):
    """Enqueues the analysis of a period and returns its job. Since 16.20 snapshots require replay access, and their matches
    must be from a single build (`_one_build`).

    Idempotent: if there is already an analysis running for the same player and rank, that
    job is returned instead of launching another. Progress is followed over SSE at
    GET /snapshots/jobs/{job_id}/stream.
    """
    if snapshot_in.premium:
        _check_premium_request(current_user, snapshot_in.date_from)
    # Each analysis costs many Riot calls: strict per-user limit.
    await enforce("snapshots", str(current_user.id), settings.rate_limit_snapshots_per_hour, 3600, response)

    player = await get_player_by_id(db, snapshot_in.player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    await _one_build(db, player.puuid, snapshot_in.date_from, snapshot_in.date_to)

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
        premium=snapshot_in.premium,
        status="queued",
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError:
        # Another identical request won the race: the partial unique index prevents it.
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
    responses={200: {"description": "`progress`, `done` and `error` events with a SnapshotJobStatus as JSON",
                     "content": {"text/event-stream": {}}}},
)
async def stream_job(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Real-time progress via Server-Sent Events.

    SSE and not WebSockets: the flow is one-directional, works over plain HTTP
    and the browser reconnects by itself. On connecting (or reconnecting) the
    current state is sent first.
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
    """Re-enqueues a failed analysis (for example, an interrupted one)."""
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


@router.get("/premium/coverage", response_model=PremiumCoverage)
async def premium_coverage(current_user: User = Depends(get_current_user)):
    """Since when replay analysis exists (the web calendar doesn't allow requesting earlier)."""
    return PremiumCoverage(since=int(settings.premium_since.timestamp()))


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
    """Deletes a snapshot; the matches are kept for other snapshots."""
    await delete_snapshot(db, await _owned_snapshot(snapshot_id, db, current_user))


@router.get("/{snapshot_id}/dashboard", response_model=SnapshotDashboardResponse)
async def read_snapshot_dashboard(
    snapshot_id: int,
    compare_game_name: str | None = None,
    compare_tag_line: str | None = None,
    compare_region: Region | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The snapshot's dashboard (cached). `compare_*` overlays another account's radar live."""
    snapshot = await _owned_snapshot(snapshot_id, db, current_user)
    return await get_snapshot_dashboard(db, snapshot, compare_game_name, compare_tag_line, compare_region)


@router.get(
    "/{snapshot_id}/premium",
    response_model=PremiumAnalysisResponse,
    responses={403: {"description": "Replay access required"}, 404: {"description": "No replay analysis yet"}},
)
async def read_premium_analysis(
    snapshot_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_premium)
):
    """The snapshot's replay analysis: its status and, when it finishes, its numbers and the review. While it is
    running, each query advances it with the replays you have already uploaded (`premium.refresh`)."""
    snapshot = await _owned_snapshot(snapshot_id, db, current_user)
    analysis = await db.get(PremiumAnalysis, snapshot_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No replay analysis for this snapshot.")
    return await _premium_response(db, await refresh(db, analysis, snapshot), snapshot)


@router.post(
    "/{snapshot_id}/premium",
    response_model=PremiumAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={403: {"description": "Replay access required"}, 400: {"description": "Before replay coverage"}},
)
async def start_premium_analysis(
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_premium),
):
    """Launches (or relaunches) the replay analysis of an already made snapshot: requests its matches (again the ones that failed),
    which wait for you to upload their replays. If it is already running, it is returned as it is."""
    snapshot = await _owned_snapshot(snapshot_id, db, current_user)
    _check_premium_request(current_user, int(snapshot.date_from.timestamp()))
    running = await db.get(PremiumAnalysis, snapshot_id)
    if running is not None and running.status in ACTIVE_JOB_STATUSES:
        return await _premium_response(db, await refresh(db, running, snapshot), snapshot)
    return await _premium_response(db, await request_premium(db, snapshot), snapshot)


@router.post(
    "/{snapshot_id}/premium/skip",
    response_model=PremiumAnalysisResponse,
    responses={403: {"description": "Replay access required"}, 404: {"description": "No replay analysis yet"}},
)
async def skip_missing_replays(
    snapshot_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_premium)
):
    """Finishes the analysis with the replays already uploaded: the missing ones come out as not uploaded."""
    snapshot = await _owned_snapshot(snapshot_id, db, current_user)
    analysis = await db.get(PremiumAnalysis, snapshot_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No replay analysis for this snapshot.")
    if analysis.status == "processing":
        await skip_waiting(db, snapshot)
    return await _premium_response(db, await refresh(db, analysis, snapshot), snapshot)


async def _premium_response(db: AsyncSession, analysis: PremiumAnalysis, snapshot: Snapshot) -> PremiumAnalysisResponse:
    """The analysis and, while it is running, the replays still to be uploaded."""
    pending = await waiting(db, snapshot) if analysis.status == "processing" else []
    return PremiumAnalysisResponse.model_validate(analysis).model_copy(update={"waiting": pending})
