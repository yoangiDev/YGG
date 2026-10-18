"""Detail of a match: its 10 participants, requested from Riot only once."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Collection
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.match_summary import MATCH_SUMMARY_VERSION, MatchSummary, ParticipantSummary
from ygg_core.metrics.match_score import score_match
from ygg_core.riot.match_summary import parse_match_summary
from ygg_core.riot.routing import region_from_match_id

from app.core.config import settings
from app.db.models.match_detail import MatchDetail
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.service.riot import create_secure_session, riot_client

logger = logging.getLogger(__name__)


class MatchDetailsUnavailable(Exception):
    """Riot didn't return the match, or we are in the demo and it isn't stored."""


async def user_can_view_match(db: AsyncSession, match_id: str, user_id: int) -> bool:
    """Only matches of the user's players: the API isn't an open proxy to Riot."""
    stmt = (
        select(MatchParticipant.id)
        .join(Player, Player.puuid == MatchParticipant.puuid)
        .where(MatchParticipant.match_id == match_id, Player.user_id == user_id)
        .limit(1)
    )
    return await db.scalar(stmt) is not None


async def get_match_summary(db: AsyncSession, match_id: str) -> MatchSummary:
    """Stored summary or, if it doesn't exist (or is of another version), requested from Riot and stored.

    The grades are recomputed on reading: if the Challenger references change there is no need
    to request the matches again.
    """
    stored = await db.get(MatchDetail, match_id)
    if stored is not None and stored.version == MATCH_SUMMARY_VERSION:
        return score_match(MatchSummary.from_dict(stored.summary))
    if settings.demo_mode:
        raise MatchDetailsUnavailable("Match details are not available in the demo for this match.")

    client = riot_client(region_from_match_id(match_id))
    async with create_secure_session() as session:
        payload = await client.fetch_match(session, match_id)
    if not payload:
        raise MatchDetailsUnavailable("Riot API did not return this match. Try again in a moment.")

    summary = parse_match_summary(payload)
    await save_summary(db, summary)
    await db.commit()
    logger.info("Match %s details stored.", match_id)
    return summary


async def save_summary(db: AsyncSession, summary: MatchSummary) -> None:
    """No commit. The match must already be in `matches`."""
    stmt = insert(MatchDetail).values(match_id=summary.match_id, version=MATCH_SUMMARY_VERSION, summary=summary.to_dict())
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["match_id"],
            set_={"version": stmt.excluded.version, "summary": stmt.excluded.summary, "fetched_at": func.now()},
        )
    )


async def _stored(db: AsyncSession, match_ids: Collection[str]):
    return await db.scalars(
        select(MatchDetail.summary).where(MatchDetail.match_id.in_(match_ids), MatchDetail.version == MATCH_SUMMARY_VERSION)
    )


Fetch = Callable[[str], Awaitable[dict[str, Any] | None]]


def _has_wpa(summary: dict[str, Any]) -> bool:
    return any(p.get("wpa_grade") is not None for team in summary["teams"] for p in team["participants"])


async def missing_summaries(
    db: AsyncSession, fetch_match: Fetch, match_ids: Collection[str], fetch_timeline: Fetch | None = None
) -> list[MatchSummary]:
    """Summaries of the matches that don't have one stored yet.

    With `fetch_timeline`, also the stored ones without a WPA grade, and they are read with their
    timeline. A match Riot doesn't return is left without a summary (or with the one it
    had): it will be requested when expanded.
    """
    stored = {s["match_id"] for s in await _stored(db, match_ids) if fetch_timeline is None or _has_wpa(s)}
    missing = [match_id for match_id in match_ids if match_id not in stored]

    async def load(match_id: str) -> MatchSummary | None:
        payload = await fetch_match(match_id)
        if not payload:
            return None
        return parse_match_summary(payload, await fetch_timeline(match_id) if fetch_timeline else None)

    loaded = await asyncio.gather(*(load(match_id) for match_id in missing), return_exceptions=True)
    return [summary for summary in loaded if isinstance(summary, MatchSummary)]


async def ranked_participants(db: AsyncSession, puuid: str, match_ids: Collection[str]) -> dict[str, ParticipantSummary]:
    """match_id → the player's grade, position and badge, from the summaries already stored."""
    ranked: dict[str, ParticipantSummary] = {}
    for data in await _stored(db, match_ids):
        summary = score_match(MatchSummary.from_dict(data))
        ranked.update({summary.match_id: p for p in summary.participants() if p.puuid == puuid})
    return ranked
