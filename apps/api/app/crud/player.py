import logging

from sqlalchemy import RowMapping, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.riot.errors import RiotNotFoundError

from app.db.models.player import Player
from app.queries import load
from app.schemas.player import PlayerCreate, PlayerUpdate
from app.service.riot import apply_rank, apply_summoner, create_secure_session, riot_client

logger = logging.getLogger(__name__)


async def create_player(db: AsyncSession, player_in: PlayerCreate, user_id: int) -> Player | None:
    """
    Crea un jugador validándolo primero contra la Riot API.
    Obtiene el PUUID, rango e icono antes de persistir.
    Devuelve None si el jugador no existe en Riot.
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

        # Un 404 del summoner significa que la región no es la de la cuenta.
        try:
            apply_rank(player, await client.fetch_rank(session, puuid))
            apply_summoner(player, await client.fetch_summoner(session, puuid))
        except RiotNotFoundError as e:
            raise ValueError(
                f"Player '{player_in.game_name}' does not exist in region '{player_in.region}'. "
                "Please verify that the region is correct."
            ) from e

    db.add(player)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("duplicate")
    await db.refresh(player)
    return player


async def get_player_by_id(db: AsyncSession, player_id: int, user_id: int) -> Player | None:
    """Obtiene un jugador por ID verificando que pertenece al usuario autenticado."""
    return await db.scalar(select(Player).where(Player.id == player_id, Player.user_id == user_id))


async def get_players(
    db: AsyncSession, user_id: int, *, limit: int, offset: int
) -> tuple[list[Player], int]:
    """Jugadores del usuario (página) y el total."""
    total = await db.scalar(select(func.count(Player.id)).where(Player.user_id == user_id)) or 0
    stmt = (
        select(Player)
        .where(Player.user_id == user_id)
        .order_by(Player.nickname, Player.id)
        .limit(limit)
        .offset(offset)
    )
    return list(await db.scalars(stmt)), total


async def get_player_by_riot_id(
    db: AsyncSession, game_name: str, tag_line: str, user_id: int
) -> Player | None:
    """Busca un jugador por su Riot ID dentro de los jugadores del usuario."""
    return await db.scalar(
        select(Player).where(
            Player.game_name == game_name,
            Player.tag_line == tag_line,
            Player.user_id == user_id,
        )
    )


async def update_player(db: AsyncSession, player: Player, player_in: PlayerUpdate) -> Player:
    """Actualiza los campos editables de un jugador."""
    player.game_name = player_in.game_name
    player.tag_line = player_in.tag_line
    player.role = player_in.role
    player.nickname = player_in.nickname
    player.notes = player_in.notes
    await db.commit()
    await db.refresh(player)
    return player


async def refresh_player_rank(db: AsyncSession, player: Player) -> Player:
    """Refresca el rango e icono de un jugador consultando la Riot API."""
    client = riot_client(player.region)

    async with create_secure_session() as session:
        apply_rank(player, await client.fetch_rank(session, player.puuid))
        try:
            apply_summoner(player, await client.fetch_summoner(session, player.puuid))
        except RiotNotFoundError:
            logger.warning("Summoner %s not found in region %s", player.puuid, player.region)

    await db.commit()
    await db.refresh(player)
    return player


async def delete_player(db: AsyncSession, player: Player) -> None:
    """Elimina un jugador y sus snapshots. Las partidas se conservan."""
    await db.delete(player)
    await db.commit()


async def role_summary(db: AsyncSession, puuid: str) -> list[RowMapping]:
    result = await db.execute(load("player_role_summary"), {"puuid": puuid})
    return list(result.mappings())
