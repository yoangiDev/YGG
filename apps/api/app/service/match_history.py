import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.match import Match
from app.db.models.player import Player
from app.db.models.player_match_history import PlayerMatchHistory

logger = logging.getLogger(__name__)

_HISTORY_TTL = timedelta(hours=1)
DEFAULT_HISTORY_LIMIT = 100


def is_history_fresh(player: Player) -> bool:
    if not player.match_history_cached_at:
        return False
    return datetime.now(timezone.utc) - player.match_history_cached_at < _HISTORY_TTL


def get_history_from_cache(
    db: Session, player_id: int, limit: int = DEFAULT_HISTORY_LIMIT
) -> list[Match]:
    return (
        db.query(Match)
        .join(PlayerMatchHistory, PlayerMatchHistory.match_id == Match.id)
        .filter(PlayerMatchHistory.player_id == player_id)
        .order_by(Match.creation_time.desc())
        .limit(limit)
        .all()
    )


def update_history_cache(db: Session, player: Player, matches: list[Match]) -> None:
    """Upsert match_data rows, replace history entries for this player, update timestamp."""
    persisted_ids: list[int] = []

    for match in matches:
        existing = db.query(Match).filter(Match.match_id == match.match_id).first()
        if existing:
            target = existing
        else:
            try:
                sp = db.begin_nested()
                db.add(match)
                db.flush()
                target = match
            except IntegrityError:
                sp.rollback()
                target = db.query(Match).filter(Match.match_id == match.match_id).first()
                if not target:
                    continue
        if target.id:
            persisted_ids.append(target.id)

    db.query(PlayerMatchHistory).filter(PlayerMatchHistory.player_id == player.id).delete()

    for match_id in persisted_ids:
        try:
            sp = db.begin_nested()
            db.add(PlayerMatchHistory(player_id=player.id, match_id=match_id))
            sp.commit()
        except IntegrityError:
            sp.rollback()

    player.match_history_cached_at = datetime.now(timezone.utc)
    db.add(player)
    db.commit()

    logger.info("[%s] History cache updated with %d matches.", player.game_name, len(persisted_ids))
