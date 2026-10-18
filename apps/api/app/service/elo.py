"""Elo tracking: one point per day for the players who have it turned on.

Riot doesn't keep the LP history; the only way is to note down each day's rank.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.elo_entry import EloEntry
from app.db.models.player import Player


def _today() -> date:
    return datetime.now(UTC).date()


async def record_elo(db: AsyncSession, player: Player) -> None:
    """Stores (without commit) the player's current rank as today's point."""
    values = {
        "tier": player.tier or "",
        "division": player.rank or "",
        "lp": player.lp or 0,
        "wins": player.wins or 0,
        "losses": player.losses or 0,
    }
    stmt = insert(EloEntry).values(player_id=player.id, day=_today(), **values)
    await db.execute(stmt.on_conflict_do_update(index_elements=["player_id", "day"], set_=values))


async def elo_history(db: AsyncSession, player_id: int) -> list[EloEntry]:
    return list(await db.scalars(select(EloEntry).where(EloEntry.player_id == player_id).order_by(EloEntry.day)))


async def player_ids_due_for_elo(db: AsyncSession) -> list[int]:
    """Verified accounts (elo is tracked automatically on all of them) that don't have today's point yet.

    ponytail: a player without a rank stores no point and is queried again every hour;
    if there are many, note the attempt too.
    """
    checked_today = select(EloEntry.player_id).where(EloEntry.day == _today())
    return list(await db.scalars(select(Player.id).where(Player.verified_at.is_not(None), Player.id.not_in(checked_today))))
