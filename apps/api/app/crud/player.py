import logging
import random
from datetime import UTC, datetime

from sqlalchemy import RowMapping, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.riot.errors import RiotNotFoundError

from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.queries import load
from app.schemas.player import PlayerCreate, PlayerUpdate
from app.service.dashboard_cache import invalidate_dashboards
from app.service.elo import record_elo
from app.service.riot import apply_rank, apply_summoner, create_secure_session, riot_client

logger = logging.getLogger(__name__)


# The profile icons every account has since it is created: one can be requested without having to buy it.
STARTER_ICONS = range(1, 29)  # 0 too, but the web takes it as "no icon"


def verification_icon(current: int | None) -> int:
    """A starter icon different from the one currently set: putting it on in the client is what proves the account is theirs."""
    return random.choice([i for i in STARTER_ICONS if i != current])


async def current_icon(player: Player) -> int | None:
    """The profile icon currently set, according to Riot (None if Riot doesn't respond)."""
    async with create_secure_session() as session:
        summoner = await riot_client(player.region).fetch_summoner(session, player.puuid)
    return summoner.profile_icon_id if summoner else None


async def create_player(db: AsyncSession, player_in: PlayerCreate, user_id: int) -> Player | None:
    """
    Creates a player, validating it first against the Riot API.
    Gets the PUUID, rank and icon before persisting.
    Returns None if the player doesn't exist in Riot.
    """
    client = riot_client(player_in.region)

    async with create_secure_session() as session:
        try:
            puuid = await client.get_puuid(session, player_in.game_name, player_in.tag_line)
        except RiotNotFoundError as e:
            logger.warning("Player not found on Riot: %s", e)
            return None
        except ConnectionError as e:
            logger.error("Riot API connection error: %s", e)
            raise

        player = Player(
            user_id=user_id,
            puuid=puuid,
            game_name=player_in.game_name,
            tag_line=player_in.tag_line,
            region=player_in.region,
            nickname=player_in.nickname,
            role=player_in.role,
            notes=player_in.notes,
        )

        # A 404 from summoner means the region isn't the account's.
        try:
            apply_rank(player, await client.fetch_rank(session, puuid))
            apply_summoner(player, await client.fetch_summoner(session, puuid))
        except RiotNotFoundError as e:
            raise ValueError(
                f"Player '{player_in.game_name}' does not exist in region '{player_in.region}'. "
                "Please verify that the region is correct."
            ) from e
        player.verify_icon = verification_icon(player.profile_icon_id)

    db.add(player)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("duplicate")
    await db.refresh(player)
    return player


async def get_player_by_id(db: AsyncSession, player_id: int, user_id: int) -> Player | None:
    """Gets a player by ID, verifying that it belongs to the authenticated user."""
    return await db.scalar(select(Player).where(Player.id == player_id, Player.user_id == user_id))


async def get_players(
    db: AsyncSession, user_id: int, *, limit: int, offset: int
) -> tuple[list[Player], int]:
    """The user's players (a page) and the total."""
    total = await db.scalar(select(func.count(Player.id)).where(Player.user_id == user_id)) or 0
    stmt = (
        select(Player)
        .where(Player.user_id == user_id)
        .order_by(Player.id)
        .limit(limit)
        .offset(offset)
    )
    return list(await db.scalars(stmt)), total


async def update_player(db: AsyncSession, player: Player, player_in: PlayerUpdate) -> Player:
    """Updates a player's editable fields.

    The role and target rank change their dashboards: those of their snapshots are invalidated.
    """
    player.game_name = player_in.game_name
    player.tag_line = player_in.tag_line
    player.role = player_in.role
    player.nickname = player_in.nickname
    player.notes = player_in.notes
    if player_in.target_rank is not None:
        player.target_rank = player_in.target_rank
    await db.commit()
    await db.refresh(player)
    await invalidate_dashboards(await db.scalars(select(Snapshot.id).where(Snapshot.player_id == player.id)))
    return player


async def refresh_player_rank(db: AsyncSession, player: Player) -> Player:
    """Refreshes a player's rank and icon by querying the Riot API.

    With elo tracking on, the rank becomes today's point.
    """
    client = riot_client(player.region)

    async with create_secure_session() as session:
        ranked = apply_rank(player, await client.fetch_rank(session, player.puuid))
        try:
            apply_summoner(player, await client.fetch_summoner(session, player.puuid))
        except RiotNotFoundError:
            logger.warning("Summoner %s not found in region %s", player.puuid, player.region)

    if ranked and player.verified:
        await record_elo(db, player)
    await db.commit()
    await db.refresh(player)
    return player


async def delete_player(db: AsyncSession, player: Player) -> None:
    """Deletes a player and their snapshots. The matches are kept."""
    await db.delete(player)
    await db.commit()


async def role_summary(db: AsyncSession, puuid: str) -> list[RowMapping]:
    result = await db.execute(load("player_role_summary"), {"puuid": puuid})
    return list(result.mappings())


async def champion_stats(
    db: AsyncSession,
    player_id: int,
    limit: int = 10,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[RowMapping]:
    result = await db.execute(
        load("player_champion_stats"),
        {
            "player_id": player_id,
            "limit": limit,
            "since": since or datetime.min.replace(tzinfo=UTC),
            "until": until or datetime.max.replace(tzinfo=UTC),
        },
    )
    return list(result.mappings())
