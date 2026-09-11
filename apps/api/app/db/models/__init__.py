"""Registro de todos los modelos ORM.

Importar este paquete garantiza que las relaciones declaradas por nombre se
resuelvan y que Alembic vea el metadata completo.
"""

from app.db.models.job import Job
from app.db.models.legacy_link import LegacyUnresolvedLink
from app.db.models.match import Match
from app.db.models.match_detail import MatchDetail
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.db.models.player_history import PlayerHistoryEntry
from app.db.models.rank_cutoff import RankCutoff
from app.db.models.refresh_token import RefreshToken
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from app.db.models.user import User

__all__ = [
    "Job",
    "LegacyUnresolvedLink",
    "Match",
    "MatchDetail",
    "MatchParticipant",
    "Player",
    "PlayerHistoryEntry",
    "RankCutoff",
    "RefreshToken",
    "Snapshot",
    "SnapshotParticipant",
    "User",
]
