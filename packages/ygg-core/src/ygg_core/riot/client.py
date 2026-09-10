"""Cliente de la Riot API con rate limiting global, reintentos y caché de payloads."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC
from typing import Any, Protocol

import aiohttp

from ygg_core.domain.participant import ParticipantStats, PlayerRef, RankInfo, SummonerInfo
from ygg_core.domain.roles import role_matches_filter
from ygg_core.riot.errors import RiotNotFoundError, RiotUnavailableError
from ygg_core.riot.parsers import parse_participant, player_role_in_match
from ygg_core.riot.rate_limiter import RiotRateLimiter, get_riot_rate_limiter
from ygg_core.riot.routing import resolve_region
from ygg_core.timeline.enrichment import apply_timeline
from ygg_core.timeline.quests import S26_START

logger = logging.getLogger(__name__)

JsonDict = dict[str, Any]
ProgressCallback = Callable[[int, int], None]

RANKED_SOLO_QUEUE_ID = 420
RANKED_SOLO_QUEUE = "RANKED_SOLO_5x5"
MATCH_IDS_PAGE_SIZE = 100


class RawPayloadCache(Protocol):
    """Almacén de payloads crudos de Riot (match y timeline) indexado por match_id."""

    def get_payload(self, kind: str, match_id: str) -> JsonDict | None: ...

    def put_payload(self, kind: str, match_id: str, payload: JsonDict) -> None: ...


def cached_participant_usable(
    existing: ParticipantStats,
    role_filter: str | None,
    puuid: str | None = None,
) -> bool:
    """¿Sirve una fila ya calculada o hay que volver a pedir la partida a Riot?"""
    if not existing.timeline_enriched:
        return False
    # Nunca reutilizar las estadísticas de otro jugador de la misma partida.
    if puuid and existing.puuid and existing.puuid != puuid:
        return False
    created = existing.creation_time
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    if created >= S26_START and existing.quest_completion_time is None:
        return False
    if not role_filter or role_filter.upper() == "ALL":
        return True
    return existing.player_role.upper() == role_filter.upper()


class RiotAPIClient:
    def __init__(
        self,
        api_key: str,
        region: str = "europe",
        *,
        raw_cache: RawPayloadCache | None = None,
        limiter: RiotRateLimiter | None = None,
        max_connections: int = 6,
        max_concurrent_matches: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("RIOT_API_KEY not found in environment variables.")
        self.api_key = api_key
        self.headers = {"X-Riot-Token": api_key}
        routing, platform = resolve_region(region)
        self.base_routing = f"https://{routing}.api.riotgames.com"
        self.base_platform = f"https://{platform}.api.riotgames.com"
        self.raw_cache = raw_cache
        self._limiter = limiter
        # Limita conexiones en vuelo; la cuota la impone el RiotRateLimiter.
        self.semaphore = asyncio.Semaphore(max_connections)
        # Limita pares match+timeline descargándose a la vez.
        self._pair_semaphore = asyncio.Semaphore(max_concurrent_matches)

    @property
    def limiter(self) -> RiotRateLimiter:
        return self._limiter or get_riot_rate_limiter()

    async def _riot_get(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        max_retries: int = 5,
        default_retry_after: float = 1.5,
    ) -> tuple[int, Any]:
        """GET con rate limiting. Devuelve (status, json); json es None si falla."""
        retry_after = default_retry_after
        for _ in range(max_retries):
            await self.limiter.acquire()
            status = 0
            try:
                async with self.semaphore, session.get(url, headers=self.headers) as response:
                    status = response.status
                    if status == 200:
                        return status, await response.json()
                    if status != 429:
                        return status, None
                    retry_after = float(response.headers.get("Retry-After", default_retry_after))
                    if await self.limiter.pause(retry_after):
                        logger.warning(
                            "Riot rate limit — pausing all API calls for %.0fs", retry_after
                        )
            except (TimeoutError, aiohttp.ClientError):
                retry_after = default_retry_after
                status = 0

            if status == 0:
                logger.debug("Riot GET timeout/error, retrying %s", url)
                await asyncio.sleep(retry_after)
        return 429, None

    # ── Cuenta ─────────────────────────────────────────────────────────────────

    async def get_puuid(self, session: aiohttp.ClientSession, game_name: str, tag_line: str) -> str:
        url = (
            f"{self.base_routing}/riot/account/v1/accounts/by-riot-id/"
            f"{urllib.parse.quote(game_name)}/{urllib.parse.quote(tag_line)}"
        )
        for _ in range(3):
            status, data = await self._riot_get(session, url, default_retry_after=2.0)
            if status == 200 and isinstance(data, dict):
                return str(data["puuid"])
            if status == 404:
                raise RiotNotFoundError(f"Player '{game_name}#{tag_line}' not found on Riot.")
            if status not in (429, 0):
                raise RiotUnavailableError(f"Error al obtener PUUID: HTTP {status}")
        raise RiotUnavailableError("Rate limit persistente al obtener PUUID tras 3 intentos.")

    async def fetch_rank(self, session: aiohttp.ClientSession, puuid: str) -> RankInfo | None:
        """Rango en SoloQ, o None si no tiene partidas clasificatorias o Riot falla."""
        url = f"{self.base_platform}/lol/league/v4/entries/by-puuid/{puuid}"
        status, data = await self._riot_get(session, url, max_retries=1)
        if status != 200 or not isinstance(data, list):
            logger.error("Riot API error (%s) fetching rank for %s", status, puuid)
            return None
        for entry in data:
            if entry.get("queueType") == RANKED_SOLO_QUEUE:
                return RankInfo(
                    tier=entry["tier"],
                    rank=entry["rank"],
                    lp=entry["leaguePoints"],
                    wins=entry["wins"],
                    losses=entry["losses"],
                )
        return None

    async def fetch_summoner(
        self, session: aiohttp.ClientSession, puuid: str
    ) -> SummonerInfo | None:
        """Icono de invocador. Lanza RiotNotFoundError si la cuenta no existe en esta región."""
        url = f"{self.base_platform}/lol/summoner/v4/summoners/by-puuid/{puuid}"
        status, data = await self._riot_get(session, url, max_retries=1)
        if status == 404:
            raise RiotNotFoundError("Summoner does not exist in this region.")
        if status != 200 or not isinstance(data, dict):
            logger.warning("Could not fetch summoner info for %s", puuid)
            return None
        return SummonerInfo(profile_icon_id=data.get("profileIconId", 0))

    async def fetch_league_entries(
        self,
        session: aiohttp.ClientSession,
        league: str,
        queue: str = RANKED_SOLO_QUEUE,
    ) -> list[JsonDict]:
        """Entradas de challengerleagues / grandmasterleagues / masterleagues."""
        url = f"{self.base_platform}/lol/league/v4/{league}/by-queue/{queue}"
        status, data = await self._riot_get(session, url, max_retries=2)
        if status == 200 and isinstance(data, dict):
            return list(data.get("entries") or [])
        if status == 429:
            raise RiotUnavailableError("Riot API rate limit exceeded.")
        logger.error("Riot API error (%s) for %s", status, league)
        return []

    # ── Partidas: peticiones ───────────────────────────────────────────────────

    async def fetch_match_ids_page(
        self,
        session: aiohttp.ClientSession,
        puuid: str,
        start_t: int | None,
        end_t: int | None,
        start_index: int,
        count: int = MATCH_IDS_PAGE_SIZE,
    ) -> list[str]:
        count = max(1, min(MATCH_IDS_PAGE_SIZE, count))
        url = (
            f"{self.base_routing}/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?queue={RANKED_SOLO_QUEUE_ID}&start={start_index}&count={count}"
        )
        if start_t:
            url += f"&startTime={start_t}"
        if end_t:
            url += f"&endTime={end_t}"

        status, data = await self._riot_get(session, url, default_retry_after=2.0)
        if status == 200 and isinstance(data, list):
            return [str(match_id) for match_id in data]
        if status != 429:
            logger.error("Error fetching match IDs: HTTP %s", status)
        return []

    async def fetch_match_ids(
        self,
        session: aiohttp.ClientSession,
        puuid: str,
        start_t: int | None,
        end_t: int | None,
        max_matches: int | None = None,
    ) -> list[str]:
        """Recorre la paginación de Riot hasta agotar los IDs o llegar a `max_matches`."""
        match_ids: list[str] = []
        start_index = 0
        while True:
            page = MATCH_IDS_PAGE_SIZE
            if max_matches is not None:
                remaining = max_matches - len(match_ids)
                if remaining <= 0:
                    break
                page = min(MATCH_IDS_PAGE_SIZE, remaining)
            chunk = await self.fetch_match_ids_page(
                session, puuid, start_t, end_t, start_index, count=page
            )
            if not chunk:
                break
            match_ids.extend(chunk if max_matches is None else chunk[: max_matches - len(match_ids)])
            start_index += len(chunk)
            if len(chunk) < page:
                break
        return match_ids

    async def _fetch_payload(
        self, session: aiohttp.ClientSession, kind: str, url: str, match_id: str, retry_after: float
    ) -> JsonDict | None:
        if self.raw_cache is not None:
            cached = self.raw_cache.get_payload(kind, match_id)
            if cached is not None:
                return cached
        status, data = await self._riot_get(session, url, default_retry_after=retry_after)
        if status != 200 or not isinstance(data, dict):
            return None
        if self.raw_cache is not None:
            self.raw_cache.put_payload(kind, match_id, data)
        return data

    async def fetch_match(self, session: aiohttp.ClientSession, match_id: str) -> JsonDict | None:
        url = f"{self.base_routing}/lol/match/v5/matches/{match_id}"
        return await self._fetch_payload(session, "match", url, match_id, 1.5)

    async def fetch_timeline(
        self, session: aiohttp.ClientSession, match_id: str
    ) -> JsonDict | None:
        url = f"{self.base_routing}/lol/match/v5/matches/{match_id}/timeline"
        return await self._fetch_payload(session, "timeline", url, match_id, 2.0)

    async def fetch_participant(
        self,
        session: aiohttp.ClientSession,
        match_id: str,
        puuid: str,
        *,
        include_timeline: bool = True,
    ) -> ParticipantStats | None:
        """Descarga y calcula las estadísticas de un jugador en una partida concreta."""
        match_data = await self.fetch_match(session, match_id)
        if not match_data:
            return None
        stats = parse_participant(match_data, puuid, role_filter="ALL")
        if stats is None or not include_timeline:
            return stats
        timeline = await self.fetch_timeline(session, match_id)
        if not timeline or "info" not in timeline:
            return None
        apply_timeline(stats, match_data, timeline, puuid)
        return stats

    # ── Partidas: orquestación ─────────────────────────────────────────────────

    async def fetch_participants(
        self,
        session: aiohttp.ClientSession,
        player: PlayerRef,
        start_t: int | None = None,
        end_t: int | None = None,
        role_filter: str | None = "ALL",
        max_matches: int | None = None,
        include_timeline: bool = True,
        on_progress: ProgressCallback | None = None,
        known: Mapping[str, ParticipantStats] | None = None,
        match_ids: list[str] | None = None,
    ) -> list[ParticipantStats]:
        """Descarga y calcula las partidas de un jugador.

        `known` (match_id → estadísticas ya calculadas de ESTE jugador) evita
        volver a pedir a Riot las partidas que ya están enriquecidas.
        """
        known = known or {}
        cached: list[ParticipantStats] = []
        tasks: list[asyncio.Task[tuple[str, JsonDict | None, JsonDict | None]]] = []
        role_skipped = 0

        async def _fetch_pair(match_id: str) -> tuple[str, JsonDict | None, JsonDict | None]:
            nonlocal role_skipped
            async with self._pair_semaphore:
                match_data = await self.fetch_match(session, match_id)
                if not match_data:
                    return match_id, None, None
                role = player_role_in_match(match_data, player.puuid)
                if not role_matches_filter(role, role_filter):
                    role_skipped += 1
                    return match_id, None, None
                timeline = await self.fetch_timeline(session, match_id) if include_timeline else None
            return match_id, match_data, timeline

        def _schedule(match_id: str) -> None:
            existing = known.get(match_id)
            if (
                include_timeline
                and existing is not None
                and cached_participant_usable(existing, role_filter, player.puuid)
            ):
                cached.append(existing)
                return
            tasks.append(asyncio.create_task(_fetch_pair(match_id)))

        if match_ids is None:
            # Filtrando por rol se piden IDs de más: muchas partidas serán de otro rol.
            id_limit = max_matches
            if max_matches is not None and role_filter and role_filter.upper() != "ALL" and include_timeline:
                id_limit = min(max_matches * 3, MATCH_IDS_PAGE_SIZE)
            match_ids = await self.fetch_match_ids(session, player.puuid, start_t, end_t, id_limit)

        for match_id in match_ids:
            _schedule(match_id)

        if not match_ids:
            logger.info("No matches found for %s.", player.label)
            return []

        total = len(match_ids)
        completed = len(cached)
        logger.info(
            "[%s] %d matches (%d cached, %d to fetch). Processing...",
            player.label, total, completed, len(tasks),
        )
        if on_progress and completed:
            on_progress(completed, total)

        results: list[ParticipantStats] = list(cached)
        for future in asyncio.as_completed(tasks):
            match_id, match_data, timeline = await future
            completed += 1
            if on_progress:
                on_progress(completed, total)
            if not match_data or (include_timeline and not timeline):
                continue

            stats = parse_participant(match_data, player.puuid, role_filter)
            if stats is None:
                continue
            if include_timeline and timeline and "info" in timeline:
                try:
                    await asyncio.to_thread(apply_timeline, stats, match_data, timeline, player.puuid)
                except Exception as exc:  # un timeline corrupto no debe tumbar el análisis
                    logger.warning("Error enriching match %s: %s", match_id, exc)
            results.append(stats)

        logger.info(
            "[%s] Done. %d/%d valid matches (%d skipped wrong role).",
            player.label, len(results), total, role_skipped,
        )
        results.sort(key=lambda s: s.creation_time, reverse=True)
        return results[:max_matches] if max_matches is not None else results

    async def fetch_participants_until_known(
        self,
        session: aiohttp.ClientSession,
        player: PlayerRef,
        known_match_ids: set[str],
        role_filter: str | None = "ALL",
        *,
        include_timeline: bool = False,
        max_new: int = 20,
        max_fetches: int = 30,
    ) -> list[ParticipantStats]:
        """Partidas nuevas (de la más reciente hacia atrás) hasta toparse con una ya guardada."""
        if not known_match_ids:
            return await self.fetch_participants(
                session,
                player,
                max_matches=max_new,
                role_filter=role_filter,
                include_timeline=include_timeline,
            )

        page_size = 20
        new: list[ParticipantStats] = []
        start_index = 0
        fetches = 0
        hit_known = False

        while len(new) < max_new and fetches < max_fetches:
            chunk = await self.fetch_match_ids_page(
                session, player.puuid, None, None, start_index, count=page_size
            )
            if not chunk:
                break

            for match_id in chunk:
                if match_id in known_match_ids:
                    hit_known = True
                    break
                fetches += 1
                if fetches > max_fetches:
                    break

                async with self._pair_semaphore:
                    match_data = await self.fetch_match(session, match_id)
                    if not match_data:
                        continue
                    if not role_matches_filter(player_role_in_match(match_data, player.puuid), role_filter):
                        continue
                    timeline = await self.fetch_timeline(session, match_id) if include_timeline else None
                if include_timeline and not timeline:
                    continue

                stats = parse_participant(match_data, player.puuid, role_filter)
                if stats is None:
                    continue
                if include_timeline and timeline and "info" in timeline:
                    try:
                        apply_timeline(stats, match_data, timeline, player.puuid)
                    except Exception as exc:
                        logger.warning("Error enriching match %s: %s", match_id, exc)
                new.append(stats)
                if len(new) >= max_new:
                    break

            if hit_known or len(new) >= max_new or fetches >= max_fetches:
                break
            start_index += len(chunk)
            if len(chunk) < page_size:
                break

        logger.info(
            "[%s] Synced %d new matches (%d Riot fetches, stopped at known=%s).",
            player.label, len(new), fetches, hit_known,
        )
        new.sort(key=lambda s: s.creation_time, reverse=True)
        return new
