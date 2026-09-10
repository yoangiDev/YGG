import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ygg_core.riot.errors import RiotNotFoundError

from app.db.models.player import Player
from app.schemas.player import PlayerCreate, PlayerUpdate
from app.service.riot import apply_rank, apply_summoner, create_secure_session, riot_client

logger = logging.getLogger(__name__)


async def create_player(db: Session, player_in: PlayerCreate, user_id: int) -> Player | None:
    """
    Crea un jugador validándolo primero contra la Riot API.
    Obtiene el PUUID, rango e icono antes de persistir.
    Devuelve None si el jugador no existe en Riot.
    """
    client = riot_client(player_in.region)

    async with create_secure_session() as session:
        # 1. Validar que el jugador existe en Riot y obtener PUUID
        try:
            puuid = await client.get_puuid(session, player_in.game_name, player_in.tag_line)
        except RiotNotFoundError as e:
            logger.warning(f"Player not found on Riot: {e}")
            return None
        except ConnectionError as e:
            logger.error(f"Riot API connection error: {e}")
            raise

        # 2. Construir el objeto Player
        player = Player(
            user_id   = user_id,
            puuid     = puuid,
            game_name = player_in.game_name,
            tag_line  = player_in.tag_line,
            region    = player_in.region,
            nickname  = player_in.nickname,
            role      = player_in.role,
            notes     = player_in.notes,
        )

        # 3. Enriquecer con rango e icono. Un 404 del summoner significa región incorrecta.
        try:
            apply_rank(player, await client.fetch_rank(session, puuid))
            apply_summoner(player, await client.fetch_summoner(session, puuid))
        except RiotNotFoundError as e:
            raise ValueError(
                f"Player '{player_in.game_name}' does not exist in region '{player_in.region}'. "
                "Please verify that the region is correct."
            ) from e
        except ConnectionError as e:
            logger.error(f"Riot API connection error: {e}")
            raise

    # 4. Persistir en la base de datos
    db.add(player)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("duplicate")
    db.refresh(player)
    return player


def get_player_by_id(db: Session, player_id: int, user_id: int) -> Player | None:
    """Obtiene un jugador por ID verificando que pertenece al usuario autenticado."""
    return db.scalar(select(Player).where(Player.id == player_id, Player.user_id == user_id))


def get_all_players(db: Session, user_id: int) -> list[Player]:
    """Devuelve todos los jugadores del usuario autenticado."""
    return list(db.scalars(select(Player).where(Player.user_id == user_id).order_by(Player.nickname)))


def get_player_by_riot_id(
    db: Session, game_name: str, tag_line: str, user_id: int
) -> Player | None:
    """Busca un jugador por su Riot ID dentro de los jugadores del usuario."""
    return db.scalar(
        select(Player).where(
            Player.game_name == game_name,
            Player.tag_line == tag_line,
            Player.user_id == user_id,
        )
    )


def update_player(db: Session, player: Player, player_in: PlayerUpdate) -> Player:
    """Actualiza los campos editables de un jugador."""
    player.game_name = player_in.game_name
    player.tag_line  = player_in.tag_line
    player.role      = player_in.role
    player.nickname  = player_in.nickname
    player.notes     = player_in.notes

    db.commit()
    db.refresh(player)
    return player


async def refresh_player_rank(db: Session, player: Player) -> Player:
    """
    Refresca el rango e icono de un jugador consultando la Riot API.
    Se llama al arrancar la app o manualmente desde la UI.
    """
    client = riot_client(player.region)

    async with create_secure_session() as session:
        apply_rank(player, await client.fetch_rank(session, player.puuid))
        try:
            apply_summoner(player, await client.fetch_summoner(session, player.puuid))
        except RiotNotFoundError:
            logger.warning("Summoner %s not found in region %s", player.puuid, player.region)

    db.commit()
    db.refresh(player)
    return player


def delete_player(db: Session, player: Player) -> None:
    """Elimina un jugador y todos sus snapshots y partidas en cascada."""
    db.delete(player)
    db.commit()
