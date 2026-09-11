"""Detalle de una partida: sus 10 participantes, pedidos a Riot una sola vez."""

import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.match_summary import MATCH_SUMMARY_VERSION, MatchSummary
from ygg_core.riot.match_summary import parse_match_summary
from ygg_core.riot.routing import region_from_match_id

from app.core.config import settings
from app.db.models.match_detail import MatchDetail
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.service.riot import create_secure_session, riot_client

logger = logging.getLogger(__name__)


class MatchDetailsUnavailable(Exception):
    """Riot no devolvió la partida, o estamos en la demo y no está guardada."""


async def user_can_view_match(db: AsyncSession, match_id: str, user_id: int) -> bool:
    """Solo partidas de los jugadores del usuario: la API no es un proxy abierto hacia Riot."""
    stmt = (
        select(MatchParticipant.id)
        .join(Player, Player.puuid == MatchParticipant.puuid)
        .where(MatchParticipant.match_id == match_id, Player.user_id == user_id)
        .limit(1)
    )
    return await db.scalar(stmt) is not None


async def get_match_summary(db: AsyncSession, match_id: str) -> MatchSummary:
    """Resumen guardado o, si no existe (o es de otra versión), pedido a Riot y guardado."""
    stored = await db.get(MatchDetail, match_id)
    if stored is not None and stored.version == MATCH_SUMMARY_VERSION:
        return MatchSummary.from_dict(stored.summary)
    if settings.demo_mode:
        raise MatchDetailsUnavailable("Match details are not available in the demo for this match.")

    client = riot_client(region_from_match_id(match_id))
    async with create_secure_session() as session:
        payload = await client.fetch_match(session, match_id)
    if not payload:
        raise MatchDetailsUnavailable("Riot API did not return this match. Try again in a moment.")

    summary = parse_match_summary(payload)
    stmt = insert(MatchDetail).values(match_id=match_id, version=MATCH_SUMMARY_VERSION, summary=summary.to_dict())
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["match_id"],
            set_={"version": stmt.excluded.version, "summary": stmt.excluded.summary, "fetched_at": func.now()},
        )
    )
    await db.commit()
    logger.info("Match %s details stored.", match_id)
    return summary
