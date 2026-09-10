"""Registro de todos los modelos ORM.

Importar este paquete garantiza que las relaciones declaradas por nombre
("Snapshot", "Match"…) se resuelvan y que Alembic vea el metadata completo.
"""

from app.db.models.job import Job
from app.db.models.match import Match
from app.db.models.match_snapshot import MatchSnapshot
from app.db.models.player import Player
from app.db.models.player_match_history import PlayerMatchHistory
from app.db.models.rank_cutoff import RankCutoff
from app.db.models.snapshot import Snapshot
from app.db.models.user import User

__all__ = [
    "Job",
    "Match",
    "MatchSnapshot",
    "Player",
    "PlayerMatchHistory",
    "RankCutoff",
    "Snapshot",
    "User",
]
