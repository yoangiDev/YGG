"""Incremental match history sync from Riot into the latest player snapshot."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.crud.snapshot import (
    get_latest_snapshot_for_player,
    get_recent_matches_for_player,
    get_stored_match_ids_for_player,
    persist_matches_to_snapshot,
)
from app.db.models.match import Match
from app.db.models.player import Player
from app.service.http_client import create_secure_session
from app.service.role_quest_parser import is_s26_match
from app.service.riot_client import RiotAPIClient

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_RIOT_FAILURES = 2


def needs_quest_reenrich(matches: list[Match]) -> bool:
    """True if any S26 match is missing Role Quest data or reward item id."""
    for match in matches:
        if not is_s26_match(match.creation_time):
            continue
        if match.quest_completion_time is None:
            return True
        if (match.role_bound_item or 0) == 0:
            return True
    return False


def get_stored_player_matches(
    db: Session,
    player_id: int,
    user_id: int,
    *,
    limit: int = 20,
    role_filter: str | None = None,
) -> list[Match]:
    """Latest matches from DB snapshot (no Riot calls)."""
    return get_recent_matches_for_player(
        db, player_id, user_id, limit=limit, role_filter=role_filter
    )


async def backfill_role_bound_items(
    db: Session,
    player: Player,
    matches: list[Match],
    *,
    limit: int = 10,
) -> int:
    """Fetch match info only (no timeline) to populate role_bound_item."""
    candidates = [
        m for m in matches
        if is_s26_match(m.creation_time) and (m.role_bound_item or 0) == 0
    ][:limit]
    if not candidates:
        return 0

    client = RiotAPIClient(region=player.region)
    updated = 0
    failures = 0
    async with create_secure_session() as session:
        for match in candidates:
            match_data = await client._fetch_single_match(session, match.match_id)
            if not match_data:
                failures += 1
                if failures >= _MAX_CONSECUTIVE_RIOT_FAILURES:
                    break
                continue
            failures = 0
            try:
                part = next(
                    p for p in match_data["info"]["participants"]
                    if p["puuid"] == player.puuid
                )
                match.role_bound_item = part.get("roleBoundItem") or 0
                db.add(match)
                updated += 1
            except StopIteration:
                continue

    if updated:
        db.commit()
        logger.info(
            "[%s] Backfilled role_bound_item for %d matches.",
            player.game_name,
            updated,
        )
    return updated


async def re_enrich_missing_quest_stats(
    db: Session,
    player: Player,
    matches: list[Match],
    *,
    limit: int = 20,
) -> int:
    """Re-fetch timeline for S26 matches missing quest fields."""
    candidates = [
        m for m in matches
        if is_s26_match(m.creation_time)
        and (
            m.quest_completion_time is None
            or (m.role_bound_item or 0) == 0
        )
    ][:limit]
    if not candidates:
        return 0

    client = RiotAPIClient(region=player.region)
    updated = 0
    consecutive_failures = 0
    async with create_secure_session() as session:
        for match in candidates:
            timeline = await client._fetch_timeline(session, match.match_id)
            match_data = await client._fetch_single_match(session, match.match_id)
            if not timeline or not match_data:
                consecutive_failures += 1
                logger.warning(
                    "[%s] Quest re-enrich skipped %s",
                    player.game_name,
                    match.match_id,
                )
                if consecutive_failures >= _MAX_CONSECUTIVE_RIOT_FAILURES:
                    logger.warning(
                        "[%s] Stopping quest re-enrich (Riot unavailable / rate limit).",
                        player.game_name,
                    )
                    break
                continue
            consecutive_failures = 0
            try:
                client._apply_timeline_to_match(
                    match, match_data, timeline, player.puuid
                )
                db.add(match)
                updated += 1
            except Exception as exc:
                logger.warning(
                    "[%s] Quest re-enrich failed %s: %s",
                    player.game_name,
                    match.match_id,
                    exc,
                )

    if updated:
        db.commit()
        logger.info(
            "[%s] Re-enriched quest data for %d matches.",
            player.game_name,
            updated,
        )
    return updated


def _role_filter_for_player(player: Player) -> str:
    role = player.role.value if player.role else "ALL"
    if role == "BOTTOM":
        return "ADC"
    return role


async def sync_player_recent_matches(
    db: Session,
    player: Player,
    user_id: int,
    limit: int = 20,
) -> list[Match]:
    """Sync new ranked games from Riot and return stored matches."""
    role_filter = _role_filter_for_player(player)
    latest = get_latest_snapshot_for_player(db, player.id, user_id)
    client = RiotAPIClient(region=player.region)
    new_matches: list[Match] = []

    try:
        async with create_secure_session() as session:
            if latest is None:
                logger.info(
                    "[%s] No snapshot — fetching up to %d live matches.",
                    player.game_name,
                    limit,
                )
                new_matches = await client.fetch_matches(
                    session=session,
                    player=player,
                    max_matches=limit,
                    role_filter=role_filter,
                    include_timeline=False,
                )
            else:
                known_ids = get_stored_match_ids_for_player(db, player.id, user_id)
                new_matches = await client.fetch_matches_until_known(
                    session,
                    player,
                    known_ids,
                    role_filter,
                    include_timeline=True,
                    max_new=limit,
                )
    except Exception as exc:
        logger.warning(
            "[%s] Riot sync failed (%s); using stored matches.",
            player.game_name,
            exc,
        )
        new_matches = []

    if new_matches and latest is not None:
        persist_matches_to_snapshot(db, latest, new_matches)
        logger.info(
            "[%s] Added %d matches to snapshot %d.",
            player.game_name,
            len(new_matches),
            latest.id,
        )

    stored = get_stored_player_matches(
        db, player.id, user_id, limit=limit, role_filter=role_filter
    )
    if stored:
        try:
            await backfill_role_bound_items(db, player, stored, limit=limit)
        except Exception as exc:
            logger.warning(
                "[%s] role_bound_item backfill aborted (%s).",
                player.game_name,
                exc,
            )
    if stored and needs_quest_reenrich(stored):
        try:
            await re_enrich_missing_quest_stats(db, player, stored, limit=limit)
        except Exception as exc:
            logger.warning(
                "[%s] Quest re-enrich aborted (%s); returning cache.",
                player.game_name,
                exc,
            )

    return get_stored_player_matches(
        db, player.id, user_id, limit=limit, role_filter=role_filter
    )
