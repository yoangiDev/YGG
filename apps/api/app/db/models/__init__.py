"""Registry of all ORM models.

Importing this package guarantees that relationships declared by name
resolve and that Alembic sees the complete metadata.
"""

from app.db.models.elo_entry import EloEntry
from app.db.models.game_analysis import GameAnalysis
from app.db.models.job import Job
from app.db.models.legacy_link import LegacyUnresolvedLink
from app.db.models.match import Match
from app.db.models.match_detail import MatchDetail
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.player_history import PlayerHistoryEntry
from app.db.models.premium_analysis import PremiumAnalysis
from app.db.models.rank_cutoff import RankCutoff
from app.db.models.refresh_token import RefreshToken
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.db.models.user import User

__all__ = [
    "EloEntry",
    "GameAnalysis",
    "Job",
    "LegacyUnresolvedLink",
    "Match",
    "MatchDetail",
    "MatchParticipant",
    "Player",
    "PlayerHistoryEntry",
    "PremiumAnalysis",
    "RankCutoff",
    "RefreshToken",
    "Snapshot",
    "SnapshotParticipant",
    "User",
]
