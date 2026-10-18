"""Download of a player's current season, page by page.

The season dates come from the configuration (`SEASON_START` and
`SEASON_END`): Riot changes them every year and they are set by hand.

Each call fetches a page of ranked matches (without a timeline: it isn't needed for
per-champion stats) and stores them in their history. The frontend
repeats with the `next_offset` it is given until `done` is true, so that a
request is never left hanging by Riot's quota. With a production key
it is enough to raise the quota in the configuration: the loop works the same but faster.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.riot.client import MATCH_IDS_PAGE_SIZE

from app.core.config import settings
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.player_history import PlayerHistoryEntry
from app.schemas.player import SeasonSync
from app.service.match_history import fetch_history_page


def season_range() -> tuple[datetime, datetime | None]:
    return settings.season_start, settings.season_end


def _epoch(moment: datetime | None) -> int | None:
    return int(moment.timestamp()) if moment else None


async def stored_season_games(db: AsyncSession, player_id: int) -> int:
    """Season matches already stored in the player's history."""
    start, end = season_range()
    stmt = (
        select(func.count())
        .select_from(PlayerHistoryEntry)
        .join(MatchParticipant, MatchParticipant.id == PlayerHistoryEntry.match_participant_id)
        .where(PlayerHistoryEntry.player_id == player_id, MatchParticipant.creation_time >= start)
    )
    if end:
        stmt = stmt.where(MatchParticipant.creation_time <= end)
    return await db.scalar(stmt) or 0


async def sync_season_page(db: AsyncSession, player: Player, offset: int = 0) -> SeasonSync:
    """Fetches the page of the season that starts at `offset`.

    The cursor goes by Riot ids, not by stored matches: a remake or a match
    Riot doesn't serve leaves no row, and counting rows would leave the download half done
    (`done`) or would request the same ids twice.
    """
    start, end = season_range()
    rows, listed = await fetch_history_page(
        db, player, offset=offset, limit=MATCH_IDS_PAGE_SIZE, start_t=_epoch(start), end_t=_epoch(end),
        with_timelines=False,  # the grade isn't needed per champion, and it would be hundreds more requests
    )
    return SeasonSync(
        downloaded=len(rows),
        stored_games=await stored_season_games(db, player.id),
        done=listed < MATCH_IDS_PAGE_SIZE,
        next_offset=offset + listed,
    )
