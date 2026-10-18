"""A player's match history, by pages and in Riot's order.

Riot only paginates ids. The matches already stored for THIS player are not
downloaded again, and each page is added to the history without deleting the
previous ones: that way "load more" accumulates and the database acts as a cache.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.participants import add_history_entries, known_participants, upsert_participants
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.player_history import PlayerHistoryEntry
from app.service.dashboard_cache import invalidate_dashboards_for_participants
from app.service.match_details import missing_summaries, save_summary
from app.service.riot import create_secure_session, player_ref, riot_client

logger = logging.getLogger(__name__)

_HISTORY_TTL = timedelta(hours=1)
DEFAULT_HISTORY_LIMIT = 100


class _Payloads(dict):
    """Riot payloads for this request: each match's summary comes from the same download."""

    def get_payload(self, kind: str, match_id: str):
        return self.get((kind, match_id))

    def put_payload(self, kind: str, match_id: str, payload) -> None:
        self[(kind, match_id)] = payload


def is_history_fresh(player: Player) -> bool:
    """The first page was synced with Riot less than an hour ago."""
    if not player.match_history_cached_at:
        return False
    return datetime.now(timezone.utc) - player.match_history_cached_at < _HISTORY_TTL


def _newest_first():
    return MatchParticipant.creation_time.desc(), MatchParticipant.id.desc()


async def get_history_from_cache(
    db: AsyncSession, player_id: int, limit: int = DEFAULT_HISTORY_LIMIT, offset: int = 0
) -> list[MatchParticipant]:
    stmt = (
        select(MatchParticipant)
        .join(PlayerHistoryEntry, PlayerHistoryEntry.match_participant_id == MatchParticipant.id)
        .where(PlayerHistoryEntry.player_id == player_id)
        .order_by(*_newest_first())
        .offset(offset)
        .limit(limit)
    )
    return list(await db.scalars(stmt))


async def fetch_history_page(
    db: AsyncSession,
    player: Player,
    *,
    offset: int,
    limit: int,
    start_t: int | None = None,
    end_t: int | None = None,
    with_timelines: bool = True,
) -> tuple[list[MatchParticipant], int]:
    """Requests from Riot the `offset`/`limit` page of the history and stores it.

    Only the missing matches are downloaded, and with them their 10-player
    summary (grade and MVP/ACE badge). With `with_timelines` each match brings
    its timeline too: the history grade is the WPA one, as in the analyses.
    Without it (the season, hundreds of matches) it costs half the requests and the
    grade is the stats one. The first page renews the freshness mark.

    Returns the stored matches and how many ids Riot gave for that page. They are not
    the same: remakes and matches Riot doesn't serve leave no row, and whoever
    paginates needs the ids to know where to continue and whether more remain.
    """
    client = riot_client(player.region)
    client.raw_cache = _Payloads()
    async with create_secure_session() as session:
        match_ids = await client.fetch_match_ids_page(session, player.puuid, start_t, end_t, offset, count=limit)
        known = await known_participants(db, player.puuid, match_ids) if match_ids else {}
        missing = [match_id for match_id in match_ids if match_id not in known]
        fresh = (
            await client.fetch_participants(
                session, player_ref(player), role_filter=None, include_timeline=with_timelines, match_ids=missing
            )
            if missing
            else []
        )
        # The freshly downloaded ones come from _Payloads; only those stored earlier without a summary go to Riot.
        listed = set(known) | {p.match_id for p in fresh}
        summaries = await missing_summaries(
            db,
            lambda match_id: client.fetch_match(session, match_id),
            [m for m in match_ids if m in listed],
            (lambda match_id: client.fetch_timeline(session, match_id)) if with_timelines else None,
        )

    fresh_ids = await upsert_participants(db, fresh)
    participant_ids = [row.id for row in known.values()] + list(fresh_ids.values())
    await add_history_entries(db, player.id, participant_ids)
    for summary in summaries:
        await save_summary(db, summary)
    if offset == 0:
        player.match_history_cached_at = datetime.now(timezone.utc)
    await db.commit()
    if fresh_ids:
        await invalidate_dashboards_for_participants(db, fresh_ids.values())

    logger.info(
        "[%s] History page offset=%d: %d matches (%d reused, %d downloaded).",
        player.game_name, offset, len(participant_ids), len(known), len(fresh_ids),
    )
    if not participant_ids:
        return [], len(match_ids)
    rows = await db.scalars(
        select(MatchParticipant).where(MatchParticipant.id.in_(participant_ids)).order_by(*_newest_first())
    )
    return list(rows), len(match_ids)
