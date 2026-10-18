"""Analysis of individual matches after 16.20.

Riot no longer lets replays be downloaded by anything but the League client itself, so you download it (Match History → download) and
upload it on the web (`POST /games/{id}/replay`). The API checks that the file is that match and that your
account played it, spends the quota and decodes and analyses it in the background (30-60 s); the web polls until it comes out. The
quota is FREE_LIMIT matches every FREE_WINDOW; accounts with replay access have none.

What a user uploads is a file from someone we don't know and it ends up in the decoder, so the upload is defended
in layers: session, verified account and own match (against Riot), rate limit, size limit (also without
Content-Length) and limit of uploads in progress, the .rofl's structure and the memory it declares (`replays.rofl_info`), each upload
in its own folder, the decoder with a deadline and one at a time, and the file deleted when done."""

import asyncio
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, is_premium
from app.core.rate_limit import enforce
from app.db.models.game_analysis import GameAnalysis
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.user import User
from app.db.session import SessionLocal, get_db
from app.service import replays
from app.service.review import write_review

logger = structlog.get_logger()
router = APIRouter(prefix="/games", tags=["games"])

FREE_LIMIT = 3  # matches per window…
FREE_WINDOW = timedelta(hours=24)  # …every rolling 24 hours, since each one was requested
MAX_ROFL = 40 * 1024 * 1024  # a replay is 12-20 MB
MATCH_ID = re.compile(r"[A-Z0-9]{2,5}_[0-9]{6,15}")  # ASCII: \d would also match digits from other alphabets
UPLOADS_PER_HOUR = 12  # attempts per user, including those that are rejected
MAX_PER_USER = 2  # your own uploads being analysed at the same time
MAX_QUEUE = 10  # and everyone's, before asking them to come back in a while
RECENT = 50  # ponytail: the latest ones, unpaginated; paginate when there are months of history
# ponytail: one at a time (decoding is 30-60 s of CPU and ~110 MB): a real queue when there are long queues
_analysing = asyncio.Lock()


class GameAnalysisResponse(BaseModel):
    match_id: str
    status: str  # requested (a snapshot is waiting for its replay) | processing | done | error
    error: str | None = None
    created_at: datetime
    result: dict[str, Any] | None = None  # like a snapshot's: summary, games (one), missing
    review: dict[str, Any] | None = None


class Quota(BaseModel):
    limit: int | None  # None: no limit
    used: int
    next_at: datetime | None  # when the next one frees up, if all are used


class GameAnalyses(BaseModel):
    quota: Quota
    items: list[GameAnalysisResponse]


def _valid(match_id: str) -> None:
    if not MATCH_ID.fullmatch(match_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid match id.")


async def _mine(db: AsyncSession, user: User, match_id: str) -> GameAnalysis | None:
    return await db.scalar(select(GameAnalysis).where(GameAnalysis.user_id == user.id, GameAnalysis.match_id == match_id))


async def _quota(db: AsyncSession, user: User) -> Quota:
    """The finished ones (`done`) in the last 24 hours: the quota is only spent when the analysis comes out complete. One that is running or that
    failed spends nothing (the one that is running reserves its slot when another is uploaded, see `upload_replay`)."""
    if is_premium(user):
        return Quota(limit=None, used=0, next_at=None)
    since = datetime.now(UTC) - FREE_WINDOW
    times = list(await db.scalars(select(GameAnalysis.created_at).where(
        GameAnalysis.user_id == user.id, GameAnalysis.created_at > since, GameAnalysis.status == "done")
        .order_by(GameAnalysis.created_at)))
    return Quota(limit=FREE_LIMIT, used=len(times), next_at=times[0] + FREE_WINDOW if len(times) >= FREE_LIMIT else None)


async def recover_processing() -> None:
    """At startup: whatever was half done died with the previous process. It comes out as failed (spends no quota) and can be
    uploaded again."""
    shutil.rmtree(replays._uploads(), ignore_errors=True)  # whatever was left of the uploads that were cut off
    async with SessionLocal() as session:
        await session.execute(update(GameAnalysis).where(GameAnalysis.status == "processing")
                              .values(status="error", error="The server restarted while analysing it: upload it again."))
        await session.commit()


@router.get("/analyses", response_model=GameAnalyses)
async def list_game_analyses(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Your uploaded and analysed matches, from newest to oldest, and the quota you have left."""
    items = list(await db.scalars(select(GameAnalysis).where(GameAnalysis.user_id == current_user.id)
                                  .order_by(GameAnalysis.created_at.desc()).limit(RECENT)))
    return GameAnalyses(quota=await _quota(db, current_user),
                        items=[GameAnalysisResponse.model_validate(i, from_attributes=True) for i in items])


@router.get(
    "/analyses/{match_id}",
    response_model=GameAnalysisResponse,
    responses={404: {"description": "You haven't analysed this game"}},
)
async def get_game_analysis(match_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The analysis of one of your matches (the web opens it in its own tab)."""
    _valid(match_id)
    row = await _mine(db, current_user, match_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You haven't analysed this game.")
    return row


async def _process(row_id: int, match_id: str, build: str, champion: str, record: dict[str, Any],
                   tier: str | None, rofl: Path) -> None:
    """Decodes and analyses the uploaded replay, in the background, and deletes the .rofl and its folder: what is stored is what was
    decoded."""
    try:
        async with _analysing:
            if not replays.stored(match_id):  # the first checked copy is the good one: another isn't decoded
                replays.forget_decoded(match_id)
                failures = await asyncio.to_thread(replays.decode, {match_id: build}, {match_id: rofl})
                if match_id in failures:
                    raise ValueError(failures[match_id])
                if not await asyncio.to_thread(replays.matches_riot, match_id, record):
                    replays.forget_decoded(match_id)
                    raise ValueError("This replay doesn't match the game Riot has on record.")
            game = replays.rate(await asyncio.to_thread(replays.analyse, match_id, champion, record), tier)
            summary = await asyncio.to_thread(replays.summarize, [game], tier)
        values: dict[str, Any] = {"status": "done", "error": None, "review": await write_review(summary, [game]),
                                  "result": {"summary": summary, "games": [game], "missing": {}}}
    except ValueError as exc:
        values = {"status": "error", "error": str(exc)}
    except Exception as exc:
        logger.warning("game_analysis_failed", match_id=match_id, error=str(exc))
        values = {"status": "error", "error": "The game could not be analysed."}
    finally:
        shutil.rmtree(rofl.parent, ignore_errors=True)
    async with SessionLocal() as session:
        await session.execute(update(GameAnalysis).where(GameAnalysis.id == row_id).values(**values))
        await session.commit()


async def _read_body(request: Request) -> bytes:
    """The body, without exceeding MAX_ROFL: it is cut off as soon as it goes over, also if it doesn't declare its size (chunked), so
    that nobody fills the server's memory with an endless upload."""
    too_big = HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The file is too large.")
    try:
        declared = int(request.headers.get("content-length", 0))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length.") from exc
    if declared > MAX_ROFL:
        raise too_big
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_ROFL:
            raise too_big
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/{match_id}/replay",
    response_model=GameAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"description": "Not a replay, or not this game"},
               403: {"description": "Your linked account didn't play this game"},
               429: {"description": "Free limit reached for the last 24 hours"}},
    openapi_extra={"requestBody": {"required": True, "content": {
        "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def upload_replay(
    match_id: str,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The .rofl you downloaded with your client. Before spending quota it is checked that it is that match (the file's ten Riot IDs are
    Riot's) and that your account played it; then it stays in `processing` until `done` or `error` comes out.
    A match already analysed or in progress is returned as it is."""
    _valid(match_id)
    await enforce("replays", str(current_user.id), UPLOADS_PER_HOUR, 3600, response)
    row = await _mine(db, current_user, match_id)
    if row is not None and row.status in ("processing", "done"):
        return row
    accounts = list(await db.scalars(select(Player).where(Player.user_id == current_user.id).order_by(Player.id)))
    if not accounts:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Link your League account first.")
    verified = [p for p in accounts if p.verified]
    if not verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Verify your League account first, in Account.")
    working = select(func.count()).select_from(GameAnalysis).where(GameAnalysis.status == "processing")
    mine_working = await db.scalar(working.where(GameAnalysis.user_id == current_user.id))
    quota = await _quota(db, current_user)  # the cheap check, before reading 20 MB and asking Riot
    # what is in progress reserves its slot: if it ends well, it spends. It also applies to retrying one that failed
    if quota.limit is not None and quota.used + mine_working >= quota.limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="daily_limit")
    if mine_working >= MAX_PER_USER:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Wait for your other analyses to finish.")
    if await db.scalar(working) >= MAX_QUEUE:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Busy: try again in a minute.")

    data = await _read_body(request)
    try:
        build, players = replays.rofl_info(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    # Which of your accounts the match belongs to is said by Riot, not the file nor the client: the one that already has it
    # in its history is tried first and, if not, the others (at most MAX_ACCOUNTS questions).
    played = set(await db.scalars(select(MatchParticipant.puuid).where(
        MatchParticipant.match_id == match_id, MatchParticipant.puuid.in_([p.puuid for p in verified]))))
    verified.sort(key=lambda p: p.puuid not in played)
    record: dict[str, Any] | None = None
    linked: Player | None = None
    you: dict[str, Any] | None = None
    for account in verified:
        found = (await replays.records(account, [match_id])).get(match_id)
        if found is None:
            continue
        record = found
        you = next((p for p in found["participants"] if p.get("puuid") == account.puuid), None)
        if you is not None:
            linked = account
            break
    if record is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Riot didn't return this game. Try again in a minute.")
    if linked is None or you is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="None of your accounts played this game.")
    if players != {replays.riot_id(p.get("riotIdGameName", ""), p.get("riotIdTagline", ""))
                   for p in record["participants"]}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"This file is not the replay of {match_id}.")

    if row is None:  # the quota is spent here, with the replay already checked
        row = GameAnalysis(user_id=current_user.id, match_id=match_id)
        db.add(row)
    row.status, row.error = "processing", None
    try:
        await db.commit()
    except IntegrityError:  # another upload of this same match won the race
        await db.rollback()
        winner = await _mine(db, current_user, match_id)
        assert winner is not None
        return winner
    await db.refresh(row)
    path = replays.new_upload(match_id)
    try:
        await asyncio.to_thread(path.write_bytes, data)
    except OSError as exc:
        logger.error("replay_store_failed", error=str(exc))
        shutil.rmtree(path.parent, ignore_errors=True)
        row.status, row.error = "error", "The server couldn't store the file. Try again later."
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=row.error) from exc
    background.add_task(_process, row.id, match_id, build, you["championName"], record, linked.tier, path)
    return row
