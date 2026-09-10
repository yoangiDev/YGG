import urllib.parse
import logging
import aiohttp
import asyncio
from datetime import datetime, timezone

from app.db.session import settings
from app.db.models.player import Player
from app.db.models.match import Match
from app.service.riot_rate_limiter import get_riot_rate_limiter
from app.service.role_quest_parser import apply_role_quest_stats

logger = logging.getLogger(__name__)

# Riot API devuelve algunos nombres que no coinciden exactamente con las claves de ddragon
_CHAMPION_NAME_FIXES: dict[str, str] = {
    "FiddleSticks": "Fiddlesticks",
}

def _normalize_champion(name: str) -> str:
    return _CHAMPION_NAME_FIXES.get(name, name)

# Summoner's Rift objective pits (Riot game coordinates, 0–15000).
# ELITE_MONSTER_KILL events usually omit `position`.
_OBJECTIVE_PIT_POSITIONS: dict[str, dict[str, int]] = {
    "DRAGON": {"x": 9866, "y": 4414},
    "BARON_NASHOR": {"x": 5007, "y": 10471},
}
_OBJECTIVE_PREP_RADIUS_SQ = 2500 * 2500
_OBJECTIVE_PREP_WINDOW_MS = 90_000
_DRAGON_CONTEST_AFTER_MS = 30_000


def _jungler_in_zone_during_window(
    frames: list,
    participant_id: int,
    start_ms: int,
    end_ms: int,
    pit_x: int,
    pit_y: int,
) -> bool:
    pid_key = str(participant_id)
    for frame in frames:
        ts = frame.get("timestamp", 0)
        if ts < start_ms:
            continue
        if ts > end_ms:
            break
        pf = frame.get("participantFrames", {}).get(pid_key) or {}
        pos = pf.get("position")
        if not pos:
            continue
        if _within_objective_radius(pos.get("x", 0), pos.get("y", 0), pit_x, pit_y):
            return True
    return False


def _jungler_at_kill_moment(
    frames: list,
    participant_id: int,
    kill_ts: int,
    pit_x: int,
    pit_y: int,
) -> bool:
    pid_key = str(participant_id)
    sample_frame = None
    for frame in frames:
        if frame.get("timestamp", 0) <= kill_ts:
            sample_frame = frame
        else:
            break
    if sample_frame is None:
        return False
    pf = sample_frame.get("participantFrames", {}).get(pid_key) or {}
    pos = pf.get("position")
    if not pos:
        return False
    return _within_objective_radius(pos.get("x", 0), pos.get("y", 0), pit_x, pit_y)


def _dragon_contested(
    frames: list,
    kill_ts: int,
    pit_x: int,
    pit_y: int,
    window_before_ms: int = _OBJECTIVE_PREP_WINDOW_MS,
    window_after_ms: int = _DRAGON_CONTEST_AFTER_MS,
) -> bool:
    start_ms = kill_ts - window_before_ms
    end_ms = kill_ts + window_after_ms
    for frame in frames:
        for event in frame.get("events", []):
            if event.get("type") != "CHAMPION_KILL":
                continue
            ts = event.get("timestamp", 0)
            if not (start_ms <= ts <= end_ms):
                continue
            pos = event.get("position") or {}
            if _within_objective_radius(pos.get("x", 0), pos.get("y", 0), pit_x, pit_y):
                return True
    return False


def extract_dragon_setups(
    timeline: dict,
    participant_id: int,
    player_team_id: int,
    window_ms: int = _OBJECTIVE_PREP_WINDOW_MS,
) -> list[dict]:
    """
    Per-dragon objective control signals for the jungler.
    Uses all timeline frames in the 90s prep window (not a single point 30s before).
    """
    frames = timeline.get("info", {}).get("frames", [])
    if not frames:
        return []

    pit = _OBJECTIVE_PIT_POSITIONS["DRAGON"]
    pit_x, pit_y = pit["x"], pit["y"]
    setups: list[dict] = []

    for frame in frames:
        for event in frame.get("events", []):
            if event.get("type") != "ELITE_MONSTER_KILL":
                continue
            if event.get("monsterType") != "DRAGON":
                continue

            kill_ts = event.get("timestamp", 0)
            prep_start = kill_ts - window_ms
            killer_team_id = event.get("killerTeamId", 0)
            team_dragon = killer_team_id == player_team_id

            in_prep_zone = _jungler_in_zone_during_window(
                frames, participant_id, prep_start, kill_ts, pit_x, pit_y
            )
            at_kill_zone = _jungler_at_kill_moment(
                frames, participant_id, kill_ts, pit_x, pit_y
            )
            secured_by_jg = event.get("killerId") == participant_id
            contested = _dragon_contested(frames, kill_ts, pit_x, pit_y)

            setups.append({
                "dragon_time": kill_ts // 1000,
                "dragon_type": event.get("monsterSubType", "UNKNOWN"),
                "team_dragon": team_dragon,
                "in_prep_zone": in_prep_zone,
                "at_kill_zone": at_kill_zone,
                "secured_by_jg": secured_by_jg,
                "contested": contested,
            })

    return setups


def _resolve_elite_monster_position(event: dict) -> dict[str, int] | None:
    monster_type = event.get("monsterType")
    fallback = _OBJECTIVE_PIT_POSITIONS.get(monster_type)
    if fallback is None:
        return None

    pos = event.get("position") or {}
    x = pos.get("x", 0)
    y = pos.get("y", 0)
    if x > 0 and y > 0:
        return {"x": x, "y": y}
    return dict(fallback)


def _within_objective_radius(px: float, py: float, ox: float, oy: float) -> bool:
    dx = px - ox
    dy = py - oy
    return (dx * dx + dy * dy) <= _OBJECTIVE_PREP_RADIUS_SQ


def region_from_match_id(match_id: str) -> str:
    """Derive the Riot platform key from a match id (e.g. EUW1_123 -> euw1)."""
    return match_id.split("_", 1)[0].lower()


def extract_elite_objective_kills(timeline: dict) -> list[dict]:
    """Return dragon/baron kills with resolved pit positions from a match timeline."""
    elite_kills: list[dict] = []
    frames = timeline.get("info", {}).get("frames", [])
    for frame in frames:
        for event in frame.get("events", []):
            if event.get("type") != "ELITE_MONSTER_KILL":
                continue
            pos = _resolve_elite_monster_position(event)
            if pos is None:
                continue
            elite_kills.append({
                "pos": pos,
                "timestamp": event.get("timestamp", 0),
            })
    return elite_kills


def compute_objective_vision_score(
    ward_events: list | None,
    *,
    timeline: dict | None = None,
    elite_kills: list[dict] | None = None,
) -> int:
    """
    Count wards placed within 2500 units of Baron/Dragon in the 90s before they die.
    Provide either `timeline` or precomputed `elite_kills`.
    """
    wards = ward_events or []
    if not wards:
        return 0

    kills = elite_kills if elite_kills is not None else (
        extract_elite_objective_kills(timeline) if timeline else []
    )
    if not kills:
        return 0

    score = 0
    for ward in wards:
        wx = ward.get("x", 0)
        wy = ward.get("y", 0)
        w_time_ms = ward.get("time", 0) * 1000
        for kill in kills:
            k_pos = kill["pos"]
            k_time_ms = kill["timestamp"]
            if not (0 <= k_time_ms - w_time_ms <= _OBJECTIVE_PREP_WINDOW_MS):
                continue
            if _within_objective_radius(wx, wy, k_pos["x"], k_pos["y"]):
                score += 1
                break
    return score


# Fields populated by _enrich_with_timeline — refreshed when a match is re-fetched.
TIMELINE_ENRICHMENT_FIELDS = (
    "xp_diff_8", "xp_diff_14",
    "gold_diff_8", "gold_diff_14", "gold_diff_25",
    "cs_8", "cs_14", "cs_25",
    "cs_diff_8", "cs_diff_14", "cs_diff_25",
    "death_events", "ward_events", "dragon_setups", "timeline_enriched",
    "solo_kills", "roaming_proactivity", "objective_vision_score",
    "early_gank_deaths",
    "quest_completed", "quest_completion_time",
    "enemy_quest_completion_time", "quest_completion_time_diff",
)


def copy_timeline_fields(target: Match, source: Match) -> None:
    """Copy timeline-derived metrics from a freshly parsed match onto an existing row."""
    for field in TIMELINE_ENRICHMENT_FIELDS:
        setattr(target, field, getattr(source, field))

# ── Mapeo de región lógica → routing y platform endpoints de Riot ──────────────
REGION_ROUTING = {
    # EUROPA
    "europe":   ("europe", "euw1"),
    "euw":      ("europe", "euw1"),
    "euw1":     ("europe", "euw1"),
    "eune":     ("europe", "eun1"),
    "eun1":     ("europe", "eun1"),
    "tr":       ("europe", "tr1"),
    "tr1":      ("europe", "tr1"),
    "ru":       ("europe", "ru"),
    
    # AMÉRICAS
    "americas": ("americas", "na1"),
    "na":       ("americas", "na1"),
    "na1":      ("americas", "na1"),
    "lan":      ("americas", "la1"),
    "la1":      ("americas", "la1"),
    "las":      ("americas", "la2"),
    "la2":      ("americas", "la2"),
    "br":       ("americas", "br1"),
    "br1":      ("americas", "br1"),
    
    # ASIA
    "asia":     ("asia", "kr"),
    "kr":       ("asia", "kr"),
    "jp":       ("asia", "jp1"),
    "jp1":      ("asia", "jp1"),
    
    # ESPORTS (Para torneos oficiales si fuera necesario)
    "esports":  ("esports", "esports"),
    
    # SEA (Sudeste Asiático / Oceanía)
    "sea":      ("sea", "oc1"),
    "oce":      ("sea", "oc1"),
    "oc1":      ("sea", "oc1"),
    "ph":       ("sea", "ph2"),
    "ph2":      ("sea", "ph2"),
    "sg":       ("sea", "sg2"),
    "sg2":      ("sea", "sg2"),
    "th":       ("sea", "th2"),
    "th2":      ("sea", "th2"),
    "tw":       ("sea", "tw2"),
    "tw2":      ("sea", "tw2"),
    "vn":       ("sea", "vn2"),
    "vn2":      ("sea", "vn2"),
}

# ── Mapeo de roles Riot → nuestro formato ──────────────────────────────────────
ROLE_MAPPING = {
    "TOP":     "TOP",
    "JUNGLE":  "JUNGLE",
    "MIDDLE":  "MID",
    "BOTTOM":  "ADC",
    "UTILITY": "SUPPORT",
}


class RiotAPIClient:
    """Cliente para la Riot Games API con manejo de reintentos y rate limiting."""

    def __init__(self, region: str = "europe"):
        self.api_key = settings.riot_api_key
        if not self.api_key:
            raise ValueError("RIOT_API_KEY not found in environment variables.")

        self.headers = {"X-Riot-Token": self.api_key}

        routing, platform = REGION_ROUTING.get(region.lower(), ("europe", "euw1"))
        self.base_routing = f"https://{routing}.api.riotgames.com"
        self.base_platform = f"https://{platform}.api.riotgames.com"

        # Caps in-flight HTTP connections; rate quota enforced by RiotRateLimiter
        self.semaphore = asyncio.Semaphore(6)
        self._pair_semaphore = asyncio.Semaphore(3)

    @staticmethod
    def _player_role_in_match(data: dict, puuid: str) -> str:
        participant = next(
            (p for p in data["info"]["participants"] if p["puuid"] == puuid),
            None,
        )
        if participant is None:
            return "UNKNOWN"
        riot_role = participant.get("teamPosition", "").upper()
        return ROLE_MAPPING.get(riot_role, "UNKNOWN")

    @staticmethod
    def _role_matches_filter(player_role: str, role_filter: str) -> bool:
        if not role_filter or role_filter.upper() == "ALL":
            return True
        return player_role.upper() == role_filter.upper()

    @staticmethod
    def _cached_match_usable(existing: Match, role_filter: str) -> bool:
        if not getattr(existing, "timeline_enriched", False):
            return False
        created = getattr(existing, "creation_time", None)
        if created is not None:
            from datetime import datetime, timezone

            s26 = datetime(2026, 1, 1, tzinfo=timezone.utc)
            ct = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            if ct >= s26 and getattr(existing, "quest_completion_time", None) is None:
                return False
        if not role_filter or role_filter.upper() == "ALL":
            return True
        stored_role = getattr(existing, "player_role", None)
        return (
            stored_role is not None
            and stored_role.upper() == role_filter.upper()
        )

    async def _riot_get(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        max_retries: int = 5,
        default_retry_after: float = 1.5,
    ) -> tuple[int, dict | list | None]:
        """Rate-limited GET. Returns (status_code, json_body). Body is None on failure."""
        limiter = get_riot_rate_limiter()
        retry_after = default_retry_after

        for _ in range(max_retries):
            await limiter.acquire()
            status = 0
            try:
                async with self.semaphore:
                    async with session.get(url, headers=self.headers) as response:
                        status = response.status
                        if response.status == 200:
                            return status, await response.json()
                        if response.status == 429:
                            retry_after = float(
                                response.headers.get("Retry-After", default_retry_after)
                            )
                            if await limiter.pause(retry_after):
                                logger.warning(
                                    f"Riot rate limit — pausing all API calls "
                                    f"for {retry_after:.0f}s"
                                )
                        else:
                            return status, None
            except (aiohttp.ClientError, asyncio.TimeoutError):
                retry_after = default_retry_after
                status = 0

            if status == 429:
                continue
            if status == 0:
                logger.debug(f"Riot GET timeout/error, retrying {url}")
                await asyncio.sleep(retry_after)

        return 429, None

    # ─────────────────────────────────────────────────────────────────────────
    # CUENTA / PUUID
    # ─────────────────────────────────────────────────────────────────────────

    async def get_puuid(
        self, session: aiohttp.ClientSession, game_name: str, tag_line: str
    ) -> str:
        """Obtiene el PUUID a partir del Riot ID (game_name#tag_line)."""
        safe_name = urllib.parse.quote(game_name)
        safe_tag = urllib.parse.quote(tag_line)
        url = f"{self.base_routing}/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"

        for attempt in range(3):
            status, data = await self._riot_get(session, url, default_retry_after=2.0)
            if status == 200 and isinstance(data, dict):
                return data["puuid"]
            if status == 404:
                raise ValueError(f"Player '{game_name}#{tag_line}' not found on Riot.")
            if status not in (429, 0):
                raise ConnectionError(f"Error al obtener PUUID: HTTP {status}")

        raise ConnectionError("Rate limit persistente al obtener PUUID tras 3 intentos.")

    async def fetch_player_rank(
        self, session: aiohttp.ClientSession, player: Player
    ) -> bool:
        if not player.puuid:
            logger.warning(f"Abortando fetch_player_rank: {player.game_name} no tiene PUUID.")
            return False

        url = f"{self.base_platform}/lol/league/v4/entries/by-puuid/{player.puuid}"

        status, data = await self._riot_get(session, url, max_retries=1)
        if status != 200 or not isinstance(data, list):
            logger.error(f"Error Riot API ({status}) al buscar rango de {player.puuid}")
            return False

        entries = data

        if not entries:
            logger.info(f"{player.game_name} has no ranked matches this season.")
            return False

        for entry in entries:
            if entry["queueType"] == "RANKED_SOLO_5x5":
                player.tier   = entry["tier"]
                player.rank   = entry["rank"]
                player.lp     = entry["leaguePoints"]
                player.wins   = entry["wins"]
                player.losses = entry["losses"]
                return True

        return False

    async def fetch_summoner_info(
        self, session: aiohttp.ClientSession, player: Player
    ) -> None:
        """
        Actualiza profile_icon_id directamente sobre el objeto Player.
        summoner_level se eliminó del modelo — no lo almacenamos.
        """
        url = f"{self.base_platform}/lol/summoner/v4/summoners/by-puuid/{player.puuid}"

        status, data = await self._riot_get(session, url, max_retries=1)
        if status == 404:
            raise ValueError(
                f"Player '{player.game_name}' does not exist in region '{player.region}'. "
                "Please verify that the region is correct."
            )
        if status != 200 or not isinstance(data, dict):
            logger.warning(f"No se pudo obtener summoner info para {player.puuid}")
            return
        player.profile_icon_id = data.get("profileIconId", 0)

    # ─────────────────────────────────────────────────────────────────────────
    # PARTIDAS
    # ─────────────────────────────────────────────────────────────────────────

    async def fetch_matches(
        self,
        session: aiohttp.ClientSession,
        player: Player,
        start_t: int | None = None,
        end_t: int | None = None,
        role_filter: str = "ALL",
        max_matches: int | None = None,
        include_timeline: bool = True,
        on_progress=None,
        known_matches: dict[str, Match] | None = None,
        match_ids: list[str] | None = None,
    ) -> list[Match]:
        """
        Orquesta la descarga y parseo de partidas para un jugador.
        known_matches: match_id -> existing DB row; skips Riot API when timeline_enriched.
        """
        known_matches = known_matches or {}
        cached_results: list[Match] = []
        pair_tasks: list[asyncio.Task] = []
        role_skipped = 0

        async def _fetch_pair(match_id: str):
            nonlocal role_skipped
            async with self._pair_semaphore:
                match_data = await self._fetch_single_match(session, match_id)
                if not match_data:
                    return match_id, None, None
                role = self._player_role_in_match(match_data, player.puuid)
                if not self._role_matches_filter(role, role_filter):
                    role_skipped += 1
                    return match_id, None, None
                timeline = (
                    await self._fetch_timeline(session, match_id)
                    if include_timeline
                    else None
                )
            return match_id, match_data, timeline

        def _schedule_fetch(match_id: str) -> None:
            existing = known_matches.get(match_id)
            if include_timeline and existing is not None and self._cached_match_usable(
                existing, role_filter
            ):
                cached_results.append(existing)
                return
            pair_tasks.append(asyncio.create_task(_fetch_pair(match_id)))

        if match_ids is None:
            match_ids = []
            start_index = 0
            # When filtering by role, fetch extra IDs — many games may be off-role.
            id_fetch_limit = max_matches
            if (
                max_matches is not None
                and role_filter
                and role_filter.upper() != "ALL"
                and include_timeline
            ):
                id_fetch_limit = min(max_matches * 3, 100)

            while True:
                page_count = 100
                if id_fetch_limit is not None:
                    remaining = id_fetch_limit - len(match_ids)
                    if remaining <= 0:
                        break
                    page_count = min(100, remaining)

                chunk = await self._fetch_match_ids_page(
                    session,
                    player.puuid,
                    start_t,
                    end_t,
                    start_index,
                    count=page_count,
                )
                if not chunk:
                    break

                to_add = chunk
                if id_fetch_limit is not None:
                    remaining = id_fetch_limit - len(match_ids)
                    to_add = chunk[:remaining]

                match_ids.extend(to_add)
                for mid in to_add:
                    _schedule_fetch(mid)

                start_index += len(chunk)
                if len(chunk) < page_count:
                    break
                if id_fetch_limit is not None and len(match_ids) >= id_fetch_limit:
                    break
        else:
            for mid in match_ids:
                _schedule_fetch(mid)

        if not match_ids and not cached_results:
            logger.info(f"No matches found for {player.game_name}#{player.tag_line}.")
            return []

        total = len(match_ids)
        skipped = len(cached_results)
        logger.info(
            f"[{player.game_name}] {total} matches ({skipped} cached, "
            f"{len(pair_tasks)} to fetch). Processing..."
        )

        parsed_matches: list[Match] = list(cached_results)
        completed = skipped

        if on_progress and completed > 0:
            on_progress(completed, total)

        for future in asyncio.as_completed(pair_tasks):
            match_id, match_data, timeline = await future
            completed += 1

            if on_progress:
                on_progress(completed, total)

            if not match_data or (include_timeline and not timeline):
                continue

            match = self._parse_match(match_data, player.puuid, player.id, role_filter)
            if not match:
                continue

            if include_timeline and timeline and "info" in timeline:
                try:
                    await asyncio.to_thread(
                        self._apply_timeline_to_match,
                        match,
                        match_data,
                        timeline,
                        player.puuid,
                    )
                except Exception as e:
                    logger.warning(f"Error enriching match {match_id}: {e}")

            parsed_matches.append(match)

        logger.info(
            f"[{player.game_name}] Done. {len(parsed_matches)}/{total} valid matches "
            f"({role_skipped} skipped wrong role)."
        )
        parsed_matches.sort(key=lambda m: m.creation_time, reverse=True)
        if max_matches is not None:
            parsed_matches = parsed_matches[:max_matches]
        return parsed_matches

    async def fetch_matches_until_known(
        self,
        session: aiohttp.ClientSession,
        player: Player,
        known_match_ids: set[str],
        role_filter: str = "ALL",
        *,
        include_timeline: bool = False,
        max_new: int = 20,
        max_fetches: int = 30,
    ) -> list[Match]:
        """
        Fetch ranked games newest-first from Riot until a stored match_id is seen.
        Skips off-role games without stopping.
        """
        if not known_match_ids:
            return await self.fetch_matches(
                session=session,
                player=player,
                max_matches=max_new,
                role_filter=role_filter,
                include_timeline=include_timeline,
            )

        new_matches: list[Match] = []
        start_index = 0
        fetches = 0
        hit_known = False

        while len(new_matches) < max_new and fetches < max_fetches:
            chunk = await self._fetch_match_ids_page(
                session, player.puuid, None, None, start_index, count=20
            )
            if not chunk:
                break

            hit_known = False
            for mid in chunk:
                if mid in known_match_ids:
                    hit_known = True
                    break

                fetches += 1
                if fetches > max_fetches:
                    break

                async with self._pair_semaphore:
                    match_data = await self._fetch_single_match(session, mid)
                    if not match_data:
                        continue
                    role = self._player_role_in_match(match_data, player.puuid)
                    if not self._role_matches_filter(role, role_filter):
                        continue
                    timeline = (
                        await self._fetch_timeline(session, mid)
                        if include_timeline
                        else None
                    )

                if include_timeline and not timeline:
                    continue

                match = self._parse_match(
                    match_data, player.puuid, player.id, role_filter
                )
                if match:
                    if include_timeline and timeline and "info" in timeline:
                        try:
                            self._apply_timeline_to_match(
                                match,
                                match_data,
                                timeline,
                                player.puuid,
                            )
                        except Exception as e:
                            logger.warning(f"Error enriching match {mid}: {e}")
                    new_matches.append(match)
                    if len(new_matches) >= max_new:
                        break

            if hit_known or len(new_matches) >= max_new or fetches >= max_fetches:
                break

            start_index += len(chunk)
            if len(chunk) < 20:
                break

        logger.info(
            f"[{player.game_name}] Synced {len(new_matches)} new matches "
            f"({fetches} Riot fetches, stopped at known={hit_known})."
        )
        new_matches.sort(key=lambda m: m.creation_time, reverse=True)
        return new_matches

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS PRIVADOS — REQUESTS
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_match_ids(
        self,
        session: aiohttp.ClientSession,
        puuid: str,
        start_t: int | None,
        end_t: int | None,
        max_matches: int | None,
    ) -> list[str]:
        """Recorre la paginación de la API para obtener todos los IDs de partidas ranked."""
        match_ids: list[str] = []
        start_index = 0

        while True:
            page_count = 100
            if max_matches is not None:
                remaining = max_matches - len(match_ids)
                if remaining <= 0:
                    break
                page_count = min(100, remaining)

            chunk = await self._fetch_match_ids_page(
                session, puuid, start_t, end_t, start_index, count=page_count
            )
            if not chunk:
                break

            to_add = chunk
            if max_matches is not None:
                remaining = max_matches - len(match_ids)
                to_add = chunk[:remaining]

            match_ids.extend(to_add)
            start_index += len(chunk)
            if len(chunk) < page_count:
                break
            if max_matches is not None and len(match_ids) >= max_matches:
                break

        return match_ids

    async def _fetch_match_ids_page(
        self,
        session: aiohttp.ClientSession,
        puuid: str,
        start_t: int | None,
        end_t: int | None,
        start_index: int,
        count: int = 100,
    ) -> list[str]:
        count = max(1, min(100, count))
        url = (
            f"{self.base_routing}/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?queue=420&start={start_index}&count={count}"
        )
        if start_t:
            url += f"&startTime={start_t}"
        if end_t:
            url += f"&endTime={end_t}"

        status, data = await self._riot_get(session, url, default_retry_after=2.0)
        if status == 200 and isinstance(data, list):
            return data
        if status not in (200, 429):
            logger.error(f"Error fetching match IDs: HTTP {status}")
        return []

    async def _fetch_single_match(
        self, session: aiohttp.ClientSession, match_id: str
    ) -> dict | None:
        url = f"{self.base_routing}/lol/match/v5/matches/{match_id}"
        status, data = await self._riot_get(session, url, default_retry_after=1.5)
        return data if status == 200 and isinstance(data, dict) else None

    async def _fetch_timeline(
        self, session: aiohttp.ClientSession, match_id: str
    ) -> dict | None:
        url = f"{self.base_routing}/lol/match/v5/matches/{match_id}/timeline"
        status, data = await self._riot_get(session, url, default_retry_after=2.0)
        return data if status == 200 and isinstance(data, dict) else None

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS PRIVADOS — PARSEO
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_match(
        self, data: dict, puuid: str, player_id: int, role_filter: str
    ) -> Match | None:
        """
        Convierte la respuesta raw de la API en un objeto Match de SQLAlchemy.
        Descarta remakes, aplica filtro de rol y calcula estadísticas de equipo.
        """
        info = data["info"]

        # 1. Descartar remakes (menos de 3.5 minutos)
        if info["gameDuration"] < 210:
            return None

        # 2. Localizar al jugador en la lista de participantes
        try:
            participant = next(p for p in info["participants"] if p["puuid"] == puuid)
        except StopIteration:
            return None

        # 3. Filtrado de rol
        riot_role = participant.get("teamPosition", "").upper()
        translated_role = ROLE_MAPPING.get(riot_role, "UNKNOWN")

        if role_filter and role_filter.upper() != "ALL":
            if translated_role != role_filter.upper():
                return None

        # 4. Estadísticas de equipo
        team_id = participant["teamId"]
        team_participants = [p for p in info["participants"] if p["teamId"] == team_id]
        team_kills  = sum(p["kills"] for p in team_participants)
        team_damage = sum(p["totalDamageDealtToChampions"] for p in team_participants)

        # 5. Objetivos de equipo
        try:
            team_stats = next(t for t in info["teams"] if t["teamId"] == team_id)
        except StopIteration:
            return None

        objectives      = team_stats.get("objectives", {})
        void_grubs_kills = objectives.get("horde", {}).get("kills", 0)

        # Extraer Runas
        primary_rune = 0
        secondary_tree = 0
        perks = participant.get("perks", {})
        styles = perks.get("styles", [])
        for style in styles:
            description = style.get("description")
            if description == "primaryStyle":
                selections = style.get("selections", [])
                if selections:
                    primary_rune = selections[0].get("perk", 0)
            elif description == "subStyle":
                secondary_tree = style.get("style", 0)

        team_gold = sum(p.get("goldEarned", 0) for p in team_participants)
        gold_share = round((participant.get("goldEarned", 0) / team_gold * 100), 1) if team_gold > 0 else 0.0
        damage_structures = participant.get("damageDealtToBuildings", participant.get("damageDealtToTurrets", 0))
        enemy_jg_monsters = participant.get("enemyJungleMonsterKills", 0)
        control_wards = participant.get("visionWardsBoughtInGame", 0)

        # 6. Construcción del objeto Match (SQLAlchemy model)
        return Match(
            match_id       = data["metadata"]["matchId"],
            creation_time  = datetime.fromtimestamp(info["gameCreation"] / 1000 + info["gameDuration"], tz=timezone.utc),
            champion       = _normalize_champion(participant["championName"]),
            win            = participant["win"],
            duration       = info["gameDuration"],
            player_role    = translated_role,
            kills          = participant["kills"],
            deaths         = participant["deaths"],
            assists        = participant["assists"],
            kill_participation = round(
                (participant["kills"] + participant["assists"]) / team_kills * 100, 1
            ) if team_kills > 0 else 0.0,
            vision         = participant["visionScore"],
            damage         = participant["totalDamageDealtToChampions"],
            gold           = participant["goldEarned"],
            total_cs       = participant["totalMinionsKilled"] + participant["neutralMinionsKilled"],
            damage_share   = round(
                participant["totalDamageDealtToChampions"] / team_damage * 100, 1
            ) if team_damage > 0 else 0.0,
            first_dragon   = objectives.get("dragon", {}).get("first", False),
            void_grubs     = void_grubs_kills >= 2,
            herald         = objectives.get("riftHerald", {}).get("kills", 0) > 0,
            summoner1_id   = participant.get("summoner1Id", 0),
            summoner2_id   = participant.get("summoner2Id", 0),
            item0          = participant.get("item0", 0),
            item1          = participant.get("item1", 0),
            item2          = participant.get("item2", 0),
            item3          = participant.get("item3", 0),
            item4          = participant.get("item4", 0),
            item5          = participant.get("item5", 0),
            item6          = participant.get("item6", 0),
            primary_rune   = primary_rune,
            secondary_tree = secondary_tree,
            gold_share     = gold_share,
            damage_structures = damage_structures,
            enemy_jg_monsters = enemy_jg_monsters,
            control_wards  = control_wards,
            role_bound_item = participant.get("roleBoundItem") or 0,
            quest_completed = False,
        )

    def _apply_timeline_to_match(
        self,
        match: Match,
        match_data: dict,
        timeline: dict,
        player_puuid: str,
    ) -> None:
        participant_id = next(
            p["participantId"]
            for p in match_data["info"]["participants"]
            if p["puuid"] == player_puuid
        )
        player_part = next(
            p for p in match_data["info"]["participants"]
            if p["puuid"] == player_puuid
        )
        player_team_id = player_part["teamId"]
        enemy_team_id = 200 if player_team_id == 100 else 100

        enemy_ids = {}
        for p in match_data["info"]["participants"]:
            if p["teamId"] == enemy_team_id:
                pos = p.get("teamPosition", "").upper()
                p_id = p["participantId"]
                if pos == "TOP":
                    enemy_ids["TOP"] = p_id
                elif pos == "JUNGLE":
                    enemy_ids["JUNGLE"] = p_id
                elif pos == "MIDDLE":
                    enemy_ids["MID"] = p_id
                elif pos == "BOTTOM":
                    enemy_ids["ADC"] = p_id
                elif pos == "UTILITY":
                    enemy_ids["SUPPORT"] = p_id

        riot_role = player_part.get("teamPosition", "").upper()
        translated_role = ROLE_MAPPING.get(riot_role, "UNKNOWN")
        match.role_bound_item = player_part.get("roleBoundItem") or 0

        self._enrich_with_timeline(
            match,
            timeline,
            participant_id,
            enemy_ids=enemy_ids,
            player_role=translated_role,
            player_team_id=player_team_id,
            participants=match_data["info"]["participants"],
        )

    def _enrich_with_timeline(
        self,
        match: Match,
        timeline: dict,
        participant_id: int,
        enemy_jg_id: int = None,
        enemy_sup_id: int = None,
        player_role: str = None,
        enemy_ids: dict = None,
        player_team_id: int = None,
        participants: list[dict] | None = None,
    ) -> None:
        """
        Rellena los campos de timeline (diffs de oro, XP, CS y eventos de muerte)
        directamente sobre el objeto Match recibido.
        """
        match.xp_diff_8    = self._get_timeline_diff(timeline, participant_id, 8,  "xp")
        match.xp_diff_14   = self._get_timeline_diff(timeline, participant_id, 14, "xp")
        match.gold_diff_8  = self._get_timeline_diff(timeline, participant_id, 8,  "totalGold")
        match.gold_diff_14 = self._get_timeline_diff(timeline, participant_id, 14, "totalGold")
        match.gold_diff_25 = self._get_timeline_diff(timeline, participant_id, 25, "totalGold")

        cs_8  = self._get_cs_diff_at_minute(timeline, participant_id, 8)
        cs_14 = self._get_cs_diff_at_minute(timeline, participant_id, 14)
        cs_25 = self._get_cs_diff_at_minute(timeline, participant_id, 25)

        match.cs_8      = cs_8["player"]
        match.cs_diff_8 = cs_8["diff"]
        match.cs_14      = cs_14["player"]
        match.cs_diff_14 = cs_14["diff"]
        match.cs_25      = cs_25["player"]
        match.cs_diff_25 = cs_25["diff"]

        # 1. Extraer eventos de muerte y wardeo
        match.death_events = self._extract_death_events(timeline, participant_id)
        match.ward_events = self._extract_ward_events(timeline, participant_id)

        # 2. Extraer métricas avanzadas basadas en eventos del timeline
        frames = timeline.get("info", {}).get("frames", [])

        # Solo Kills (Kills del jugador donde la lista de asistentes está vacía)
        solo_kills = 0
        for frame in frames:
            for event in frame.get("events", []):
                if (
                    event.get("type") == "CHAMPION_KILL"
                    and event.get("killerId") == participant_id
                    and not event.get("assistingParticipantIds")
                ):
                    solo_kills += 1
        match.solo_kills = solo_kills

        # Roaming Proactivity (Kills/Assists pre-minuto 14 fuera de la línea de MID)
        def _is_mid_lane(x: float, y: float) -> bool:
            if x < 3000 and y < 3000:  # Base azul
                return False
            if x > 12000 and y > 12000:  # Base roja
                return False
            # La diagonal principal va de (0,0) a (15000, 15000), MID está cerca de x = y
            return abs(x - y) < 2500

        roaming_proactivity = 0
        for frame in frames:
            for event in frame.get("events", []):
                if event.get("type") == "CHAMPION_KILL":
                    # Pre-14 minutos (14 * 60 * 1000 = 840000 ms)
                    if event.get("timestamp", 0) < 840000:
                        is_killer = event.get("killerId") == participant_id
                        is_assisting = participant_id in event.get("assistingParticipantIds", [])
                        if is_killer or is_assisting:
                            pos = event.get("position", {})
                            if pos:
                                x = pos.get("x", 0)
                                y = pos.get("y", 0)
                                if not _is_mid_lane(x, y):
                                    roaming_proactivity += 1
        match.roaming_proactivity = roaming_proactivity

        # Objective Vision Score — wards placed within 2500 units of Baron/Dragon
        # in the 90 seconds before the objective dies.
        match.objective_vision_score = compute_objective_vision_score(
            match.ward_events,
            timeline=timeline,
        )

        if player_role == "JUNGLE" and player_team_id is not None:
            match.dragon_setups = extract_dragon_setups(
                timeline, participant_id, player_team_id
            )
        else:
            match.dragon_setups = []

        # Early Gank Deaths (Muertes previas al minuto 10 en su carril por gank enemigo)
        early_gank_deaths = 0
        if player_role in ("TOP", "MID", "ADC"):
            # Para compatibilidad con tests anteriores
            if enemy_ids is None:
                enemy_ids = {}
            if enemy_jg_id is not None and "JUNGLE" not in enemy_ids:
                enemy_ids["JUNGLE"] = enemy_jg_id
            if enemy_sup_id is not None and "SUPPORT" not in enemy_ids:
                enemy_ids["SUPPORT"] = enemy_sup_id

            enemy_top_id = enemy_ids.get("TOP")
            enemy_jg_id = enemy_ids.get("JUNGLE")
            enemy_mid_id = enemy_ids.get("MID")
            enemy_adc_id = enemy_ids.get("ADC")
            enemy_sup_id = enemy_ids.get("SUPPORT")

            def _is_top_lane(x: float, y: float) -> bool:
                if x < 3000 and y < 3000:  # Base azul
                    return False
                if x > 12000 and y > 12000:  # Base roja
                    return False
                return (x <= 3200 and y >= 3000) or (y >= 11800 and x <= 12000)

            def _is_bot_lane(x: float, y: float) -> bool:
                if x < 3000 and y < 3000:  # Base azul
                    return False
                if x > 12000 and y > 12000:  # Base roja
                    return False
                return (y <= 3200 and x >= 3000) or (x >= 11800 and y <= 12000)

            for frame in frames:
                for event in frame.get("events", []):
                    if (
                        event.get("type") == "CHAMPION_KILL"
                        and event.get("victimId") == participant_id
                    ):
                        # Previa al minuto 10 (10 * 60 * 1000 = 600000 ms)
                        if event.get("timestamp", 0) < 600000:
                            pos = event.get("position", {})
                            if pos:
                                x = pos.get("x", 0)
                                y = pos.get("y", 0)
                                
                                # Verificar que sea en su respectivo carril
                                in_lane = False
                                if player_role == "TOP" and _is_top_lane(x, y):
                                    in_lane = True
                                elif player_role == "MID" and _is_mid_lane(x, y):
                                    in_lane = True
                                elif player_role == "ADC" and _is_bot_lane(x, y):
                                    in_lane = True
                                    
                                if in_lane:
                                    killer_id = event.get("killerId")
                                    assisting_ids = event.get("assistingParticipantIds", [])
                                    
                                    # Todos los participantes de la muerte en el equipo enemigo
                                    all_killers = [killer_id] + assisting_ids
                                    
                                    jg_participated = enemy_jg_id is not None and enemy_jg_id in all_killers
                                    sup_participated = enemy_sup_id is not None and enemy_sup_id in all_killers
                                    
                                    if player_role == "TOP":
                                        # Gank en TOP: participa el JG o el SUP enemigo, Y ADEMÁS el TOP enemigo
                                        gank_helper = jg_participated or sup_participated
                                        rival_laner = enemy_top_id is not None and enemy_top_id in all_killers
                                        if gank_helper and rival_laner:
                                            early_gank_deaths += 1
                                            
                                    elif player_role == "MID":
                                        # Gank en MID: participa el JG o el SUP enemigo, Y ADEMÁS el MID enemigo
                                        gank_helper = jg_participated or sup_participated
                                        rival_laner = enemy_mid_id is not None and enemy_mid_id in all_killers
                                        if gank_helper and rival_laner:
                                            early_gank_deaths += 1
                                            
                                    elif player_role == "ADC":
                                        # Gank en ADC: participa el JG enemigo, Y ADEMÁS al menos uno de los botlaners rivales (ADC o SUP)
                                        gank_helper = jg_participated
                                        rival_laner = (enemy_adc_id is not None and enemy_adc_id in all_killers) or (enemy_sup_id is not None and enemy_sup_id in all_killers)
                                        if gank_helper and rival_laner:
                                            early_gank_deaths += 1
        match.early_gank_deaths = early_gank_deaths

        if player_role == "JUNGLE":
            match.fullclear_time = self._extract_fullclear_time(timeline, participant_id)
        else:
            match.fullclear_time = None

        if participants:
            apply_role_quest_stats(
                match,
                timeline,
                participant_id,
                player_role=player_role,
                participants=participants,
            )

        match.timeline_enriched = True

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS PRIVADOS — HELPERS DE TIMELINE
    # ─────────────────────────────────────────────────────────────────────────

    def _get_timeline_diff(
        self, timeline: dict, participant_id: int, minute: int, stat: str
    ) -> int:
        """Diferencia de una stat entre el jugador y su oponente en el minuto indicado."""
        frames = timeline.get("info", {}).get("frames", [])
        if not frames:
            return 0

        frame    = frames[minute] if len(frames) > minute else frames[-1]
        p_frames = frame.get("participantFrames", {})

        player_val   = p_frames.get(str(participant_id), {}).get(stat, 0)
        opponent_id  = participant_id + 5 if participant_id <= 5 else participant_id - 5
        opponent_val = p_frames.get(str(opponent_id), {}).get(stat, 0)

        return player_val - opponent_val

    def _get_cs_diff_at_minute(
        self, timeline: dict, participant_id: int, minute: int
    ) -> dict:
        """CS del jugador, del oponente y diferencia en el minuto indicado."""
        frames = timeline.get("info", {}).get("frames", [])
        if not frames:
            return {"player": 0, "opponent": 0, "diff": 0}

        frame    = frames[minute] if len(frames) > minute else frames[-1]
        p_frames = frame.get("participantFrames", {})

        def _cs(frame_data: dict) -> int:
            return (
                frame_data.get("minionsKilled", 0)
                + frame_data.get("jungleMinionsKilled", 0)
            )

        player_cs   = _cs(p_frames.get(str(participant_id), {}))
        opponent_id = participant_id + 5 if participant_id <= 5 else participant_id - 5
        opponent_cs = _cs(p_frames.get(str(opponent_id), {}))

        return {"player": player_cs, "opponent": opponent_cs, "diff": player_cs - opponent_cs}

    def _extract_fullclear_time(
        self, timeline: dict, participant_id: int
    ) -> int | None:
        """Return the first second when the jungler hits 24 farm or reaches level 4."""
        frames = timeline.get("info", {}).get("frames", [])
        for frame in frames:
            p_frame = frame.get("participantFrames", {}).get(str(participant_id), {})
            if not p_frame:
                continue

            total_cs = p_frame.get("minionsKilled", 0) + p_frame.get("jungleMinionsKilled", 0)
            level = p_frame.get("level", 0)
            if total_cs >= 24 or level >= 4:
                return frame.get("timestamp", 0) // 1000
        return None

    def _extract_death_events(
        self, timeline: dict, participant_id: int
    ) -> list[dict]:
        """Extrae las coordenadas (x, y) y el timestamp en segundos de cada muerte del jugador."""
        death_positions = []
        frames = timeline.get("info", {}).get("frames", [])

        for frame in frames:
            for event in frame.get("events", []):
                if (
                    event.get("type") == "CHAMPION_KILL"
                    and event.get("victimId") == participant_id
                ):
                    pos = event.get("position", {})
                    if pos:
                        death_positions.append({
                            "x": pos.get("x", 0),
                            "y": pos.get("y", 0),
                            "time": event.get("timestamp", 0) // 1000,
                            "assistingParticipantIds": event.get("assistingParticipantIds", []),
                        })

        return death_positions

    def _extract_ward_events(
        self, timeline: dict, participant_id: int
    ) -> list[dict]:
        """Extract ward coordinates, timestamp and type for each ward placed by the player."""
        ward_events = []
        frames = timeline.get("info", {}).get("frames", [])
        pid_key = str(participant_id)

        for frame in frames:
            participant_frames = frame.get("participantFrames", {})
            for event in frame.get("events", []):
                if (
                    event.get("type") != "WARD_PLACED"
                    or event.get("creatorId") != participant_id
                ):
                    continue

                # Match v5 WARD_PLACED events usually omit `position`; use the
                # participant's location in the same timeline frame as fallback.
                pos = event.get("position")
                if not pos:
                    pf = participant_frames.get(pid_key) or {}
                    pos = pf.get("position")
                if not pos:
                    continue

                ward_events.append({
                    "x": pos.get("x", 0),
                    "y": pos.get("y", 0),
                    "time": event.get("timestamp", 0) // 1000,
                    "type": event.get("wardType", "UNKNOWN"),
                })

        return ward_events