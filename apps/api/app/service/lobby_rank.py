"""Rank of the 10 players in a match and the lobby's average elo.

Riot doesn't keep the rank each one had when playing: the one from the moment
the match is first opened is used, and that result is stored in Redis without
being computed again. Each rank is also cached, so opening matches with the
same opponents doesn't repeat calls. It is only computed when a match is expanded,
never when loading the history.
"""

import asyncio
import json
from dataclasses import asdict

import structlog
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import RankInfo
from ygg_core.riot.routing import region_from_match_id

from app.core.config import settings
from app.core.redis import get_redis
from app.schemas.match_details import LobbyRank, PlayerRank
from app.service.league_service import get_rank_cutoffs
from app.service.match_details import get_match_summary
from app.service.riot import create_secure_session, riot_client

logger = structlog.get_logger(__name__)

RANK_TTL_SECONDS = 24 * 3600
# The history shows the latest matches: after a month there is no need to keep its lobby.
LOBBY_TTL_SECONDS = 30 * 24 * 3600
TIERS = ("IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER")
DIVISIONS = ("IV", "III", "II", "I")
APEX_BASE = TIERS.index("MASTER") * 400  # from Master there are no divisions: only the LP counts


def ladder_points(rank: RankInfo) -> int:
    """LP on a continuous ladder (Iron IV 0 LP = 0, 100 per division), as ladderPoints on the web."""
    tier = TIERS.index(rank.tier)
    if tier >= TIERS.index("MASTER"):
        return APEX_BASE + rank.lp
    return tier * 400 + DIVISIONS.index(rank.rank) * 100 + min(rank.lp, 100)


def from_ladder_points(points: float, cutoffs: tuple[int, int] | None = None) -> tuple[str, str, int]:
    """Tier, division and LP of a point on the ladder.

    From Master the tier comes from the LP and the region's cutoffs (grandmaster,
    challenger); with no cutoffs it stays at Master.
    """
    if points >= APEX_BASE:
        lp = round(points - APEX_BASE)
        grandmaster, challenger = cutoffs or (None, None)
        if challenger is not None and lp >= challenger:
            return "CHALLENGER", "I", lp
        if grandmaster is not None and lp >= grandmaster:
            return "GRANDMASTER", "I", lp
        return "MASTER", "I", lp
    tier, rest = divmod(int(points), 400)
    division, lp = divmod(rest, 100)
    return TIERS[tier], DIVISIONS[division], lp


def _cache_key(region: str, puuid: str) -> str:
    return f"rank:{region}:{puuid}"


def _lobby_key(match_id: str) -> str:
    return f"lobby-rank:v3:{match_id}"  # v3: Master+ tier with the Grandmaster cutoff fixed


async def _rank(client, session, region: str, puuid: str) -> RankInfo | None:
    try:
        cached = await get_redis().get(_cache_key(region, puuid))
    except RedisError as exc:
        logger.warning("rank_cache_unavailable", error=str(exc))
        cached = None
    if cached is not None:
        return RankInfo(**json.loads(cached))

    rank = await client.fetch_rank(session, puuid, raise_on_error=True)
    # ponytail: with no rank it isn't cached, so players without ranked matches are requested again
    # in every opened match.
    if rank is not None:
        try:
            await get_redis().set(_cache_key(region, puuid), json.dumps(asdict(rank)), ex=RANK_TTL_SECONDS)
        except RedisError as exc:
            logger.warning("rank_cache_unavailable", error=str(exc))
    return rank


async def _apex_cutoffs(db: AsyncSession, region: str) -> tuple[int, int] | None:
    """LP cutoffs (grandmaster, challenger) of the region; None if Riot doesn't give them."""
    try:
        record = await get_rank_cutoffs(db, region)
    except Exception as exc:
        logger.warning("lobby_rank_cutoffs_unavailable", region=region, error=repr(exc))
        return None
    return record.grandmaster_cutoff_lp, record.challenger_cutoff_lp


async def _cached_lobby(match_id: str) -> LobbyRank | None:
    try:
        cached = await get_redis().get(_lobby_key(match_id))
    except RedisError as exc:
        logger.warning("rank_cache_unavailable", error=str(exc))
        return None
    return LobbyRank.model_validate_json(cached) if cached is not None else None


async def get_lobby_rank(db: AsyncSession, match_id: str) -> LobbyRank:
    """Rank of each player and the lobby average, computed the first time the match is opened.

    The result is stored as is for LOBBY_TTL_SECONDS: it doesn't change even if the
    players keep playing, and opening it again doesn't call Riot.
    """
    if settings.demo_mode:  # the demo never calls Riot
        return LobbyRank(ranked_players=0)
    if (cached := await _cached_lobby(match_id)) is not None:
        return cached

    summary = await get_match_summary(db, match_id)
    region = region_from_match_id(match_id)
    client = riot_client(region)
    puuids = [participant.puuid for participant in summary.participants() if participant.puuid]
    async with create_secure_session() as session:
        results = await asyncio.gather(*(_rank(client, session, region, puuid) for puuid in puuids), return_exceptions=True)

    failed = [result for result in results if isinstance(result, Exception)]
    for error in failed:
        logger.warning("lobby_rank_player_failed", match_id=match_id, error=repr(error))
    ranks = {puuid: result for puuid, result in zip(puuids, results, strict=True) if isinstance(result, RankInfo) and result.tier in TIERS}
    lobby = LobbyRank(
        ranked_players=len(ranks),
        players=[
            PlayerRank(puuid=puuid, tier=rank.tier, division=rank.rank, lp=rank.lp) if (rank := ranks.get(puuid)) else PlayerRank(puuid=puuid)
            for puuid in puuids
        ],
    )
    if ranks:
        average = sum(map(ladder_points, ranks.values())) / len(ranks)
        cutoffs = await _apex_cutoffs(db, region) if average >= APEX_BASE else None
        lobby.tier, lobby.division, lobby.lp = from_ladder_points(average, cutoffs)

    if not failed:  # a 429 or 5xx from Riot isn't stored as "unranked": it is requested again when opened
        try:
            await get_redis().set(_lobby_key(match_id), lobby.model_dump_json(), ex=LOBBY_TTL_SECONDS)
        except RedisError as exc:
            logger.warning("rank_cache_unavailable", error=str(exc))
    return lobby
