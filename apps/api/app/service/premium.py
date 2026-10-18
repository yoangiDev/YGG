"""A snapshot's replay analysis after 16.20.

The snapshot's matches are left requested (`requested`), one `game_analyses` row per match: the web shows
which ones are missing (`waiting`) and you upload their replays, as in "My games" (this spends no quota). When none
is left pending, the analysed ones are put together with `replays.summarize` and the review, and those that failed come out in
`missing` with their why. There is no worker: it advances every time the web asks (`refresh`), every 2 s while it is
running."""

import asyncio
from datetime import datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.game_analysis import GameAnalysis
from app.db.models.participant import MatchParticipant
from app.db.models.premium_analysis import PremiumAnalysis
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.service import replays
from app.service.review import write_review

logger = structlog.get_logger()

def in_coverage(date_from_unix: int) -> bool:
    """Whether the period starts when replays and the patch's exe already exist (PremiumCoverage.since)."""
    return date_from_unix >= int(settings.premium_since.timestamp())


async def _games(db: AsyncSession, snapshot: Snapshot) -> list[tuple[str, datetime]]:
    """The snapshot's matches and when they were played, from oldest to newest (which orders the trends)."""
    rows = await db.execute(
        select(MatchParticipant.match_id, MatchParticipant.creation_time)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .where(SnapshotParticipant.snapshot_id == snapshot.id)
        .order_by(MatchParticipant.creation_time)
    )
    return [(m, t) for m, t in rows.all()]


async def request_premium(db: AsyncSession, snapshot: Snapshot) -> PremiumAnalysis:
    """Requests the snapshot's matches that aren't yet (and again those that failed) and leaves the analysis running.
    If all were already analysed, it finishes right here."""
    user_id = snapshot.player.user_id
    ids = [m for m, _ in await _games(db, snapshot)]
    if ids:
        await db.execute(insert(GameAnalysis).values([{"user_id": user_id, "match_id": m} for m in ids])
                         .on_conflict_do_nothing(index_elements=["user_id", "match_id"]))
        await db.execute(update(GameAnalysis)
                         .where(GameAnalysis.user_id == user_id, GameAnalysis.match_id.in_(ids),
                                GameAnalysis.status == "error")
                         .values(status="requested", error=None))
    values = {"status": "processing", "progress": 1, "error": None}
    await db.execute(insert(PremiumAnalysis).values(snapshot_id=snapshot.id, **values)
                     .on_conflict_do_update(index_elements=[PremiumAnalysis.snapshot_id], set_=values))
    await db.commit()
    analysis = await db.get(PremiumAnalysis, snapshot.id, populate_existing=True)
    assert analysis is not None
    return await refresh(db, analysis, snapshot)


def _asked(snapshot: Snapshot):
    """The snapshot's `game_analyses` rows that are waiting for their replay."""
    ids = (select(MatchParticipant.match_id)
           .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
           .where(SnapshotParticipant.snapshot_id == snapshot.id))
    return (GameAnalysis.user_id == snapshot.player.user_id, GameAnalysis.match_id.in_(ids),
            GameAnalysis.status == "requested")


async def waiting(db: AsyncSession, snapshot: Snapshot) -> list[dict[str, object]]:
    """The snapshot's matches whose replay is still to be uploaded, with their champion and when they were played (which is how you
    find them in the client's history), from oldest to newest."""
    rows = await db.execute(
        select(MatchParticipant.match_id, MatchParticipant.champion, MatchParticipant.creation_time)
        .join(SnapshotParticipant, SnapshotParticipant.match_participant_id == MatchParticipant.id)
        .join(GameAnalysis, GameAnalysis.match_id == MatchParticipant.match_id)
        .where(SnapshotParticipant.snapshot_id == snapshot.id, *_asked(snapshot))
        .order_by(MatchParticipant.creation_time))
    return [{"match_id": m, "champion": c, "played_at": t} for m, c, t in rows.all()]


async def skip_waiting(db: AsyncSession, snapshot: Snapshot) -> None:
    """Finish with what there is: those waiting for their replay become failed (an earlier patch can no longer be downloaded)
    and come out in `missing`."""
    await db.execute(update(GameAnalysis).where(*_asked(snapshot))
                     .values(status="error", error="Its replay wasn't uploaded."))
    await db.commit()


async def refresh(db: AsyncSession, analysis: PremiumAnalysis, snapshot: Snapshot) -> PremiumAnalysis:
    """If it is running: the progress according to the matches that have already finished and, when none is left pending,
    the result (90 to 100 is the review)."""
    if analysis.status != "processing":
        return analysis
    games = await _games(db, snapshot)
    rows = {r.match_id: r for r in await db.scalars(select(GameAnalysis).where(
        GameAnalysis.user_id == snapshot.player.user_id, GameAnalysis.match_id.in_([m for m, _ in games])))}
    pending = sum(1 for m, _ in games if m not in rows or rows[m].status in ("requested", "processing"))
    if pending:
        progress = 1 + 88 * (len(games) - pending) // len(games)
        if progress != analysis.progress:
            analysis.progress = progress
            await db.commit()
        return analysis

    # whoever arrives first closes it: two simultaneous queries don't write two reviews
    claimed = (await db.execute(
        update(PremiumAnalysis)
        .where(PremiumAnalysis.snapshot_id == snapshot.id, PremiumAnalysis.status == "processing",
               PremiumAnalysis.progress < 90)
        .values(progress=90).returning(PremiumAnalysis.snapshot_id)
    )).first()
    await db.commit()
    if claimed is not None:
        try:
            analysed = [rows[m].result["games"][0] | {"played_at": t.isoformat()}
                        for m, t in games if rows[m].status == "done" and rows[m].result]
            missing = {m: rows[m].error or "The replay could not be analysed." for m, _ in games
                       if rows[m].status != "done"}
            if not analysed:
                raise ValueError(next(iter(missing.values()), "This snapshot has no games to analyse."))
            summary = await asyncio.to_thread(replays.summarize, analysed, snapshot.player.tier)
            review = await write_review(summary, analysed)
            values = {"status": "done", "progress": 100, "error": None, "review": review,
                      "result": {"summary": summary, "games": analysed, "missing": missing}}
        except Exception as exc:
            logger.exception("premium_failed", snapshot_id=snapshot.id)
            values = {"status": "error", "error": str(exc)}
        await db.execute(update(PremiumAnalysis).where(PremiumAnalysis.snapshot_id == snapshot.id).values(**values))
        await db.commit()
    fresh = await db.get(PremiumAnalysis, snapshot.id, populate_existing=True)
    assert fresh is not None
    return fresh
