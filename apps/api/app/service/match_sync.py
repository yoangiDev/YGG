"""Incremental match history sync from Riot into the latest player snapshot."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session
from ygg_core.domain.roles import role_filter_for_player
from ygg_core.riot.parsers import role_bound_item_for
from ygg_core.timeline.quests import is_s26_match

from app.crud.snapshot import (
    get_latest_snapshot_for_player,
    get_recent_matches_for_player,
    get_stored_match_ids_for_player,
    persist_participants_to_snapshot,
)
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.service.riot import copy_timeline_fields, create_secure_session, player_ref, riot_client

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_RIOT_FAILURES = 2


def needs_quest_reenrich(matches: list[MatchParticipant]) -> bool:
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
) -> list[MatchParticipant]:
    """Latest matches from DB snapshot (no Riot calls)."""
    return get_recent_matches_for_player(
        db, player_id, user_id, limit=limit, role_filter=role_filter
    )


async def backfill_role_bound_items(
    db: Session,
    player: Player,
    matches: list[MatchParticipant],
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

    client = riot_client(player.region)
    updated = 0
    failures = 0
    async with create_secure_session() as session:
        for match in candidates:
            match_data = await client.fetch_match(session, match.match_id)
            if not match_data:
                failures += 1
                if failures >= _MAX_CONSECUTIVE_RIOT_FAILURES:
                    break
                continue
            failures = 0
            item = role_bound_item_for(match_data, player.puuid)
            if item is None:
                continue
            match.role_bound_item = item
            db.add(match)
            updated += 1

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
    matches: list[MatchParticipant],
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

    client = riot_client(player.region)
    updated = 0
    consecutive_failures = 0
    async with create_secure_session() as session:
        for match in candidates:
            try:
                stats = await client.fetch_participant(session, match.match_id, player.puuid)
            except Exception as exc:
                logger.warning(
                    "[%s] Quest re-enrich failed %s: %s",
                    player.game_name,
                    match.match_id,
                    exc,
                )
                continue
            if stats is None:
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
            copy_timeline_fields(match, stats)
            db.add(match)
            updated += 1

    if updated:
        db.commit()
        logger.info(
            "[%s] Re-enriched quest data for %d matches.",
            player.game_name,
            updated,
        )
    return updated


async def sync_player_recent_matches(
    db: Session,
    player: Player,
    user_id: int,
    limit: int = 20,
) -> list[MatchParticipant]:
    """Sync new ranked games from Riot and return stored matches."""
    role_filter = role_filter_for_player(player.role.value if player.role else None)
    latest = get_latest_snapshot_for_player(db, player.id, user_id)
    participants = []

    try:
        client = riot_client(player.region)
        async with create_secure_session() as session:
            if latest is None:
                logger.info(
                    "[%s] No snapshot — fetching up to %d live matches.",
                    player.game_name,
                    limit,
                )
                participants = await client.fetch_participants(
                    session,
                    player_ref(player),
                    max_matches=limit,
                    role_filter=role_filter,
                    include_timeline=False,
                )
            else:
                known_ids = get_stored_match_ids_for_player(db, player.id, user_id)
                participants = await client.fetch_participants_until_known(
                    session,
                    player_ref(player),
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
        participants = []

    if participants and latest is not None:
        persist_participants_to_snapshot(db, latest, participants)
        logger.info(
            "[%s] Added %d matches to snapshot %d.",
            player.game_name,
            len(participants),
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
