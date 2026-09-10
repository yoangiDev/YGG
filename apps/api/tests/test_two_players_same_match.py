"""Regresión del bug P1.

Antes, `match_data.match_id` era único y la fila guardaba las estadísticas del
primer jugador analizado. Si otro jugador registrado estaba en la misma
partida, su snapshot reutilizaba esa fila y mostraba el campeón, el KDA y los
diferenciales del primero.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import func, select

from app.crud.snapshot import get_matches_by_snapshot
from app.db.models.participant import MatchParticipant
from app.db.models.player import RoleEnum
from app.db.models.snapshot import Snapshot
from app.service.dashboard import build_snapshot_dashboard
from app.service.stats_runner import run_stats_extraction
from tests.helpers import create_player, make_stats, unique


class FakeRiotClient:
    """Devuelve para cada jugador sus estadísticas en una única partida compartida."""

    def __init__(self, match_id, stats_by_puuid):
        self.match_id = match_id
        self.stats_by_puuid = stats_by_puuid
        self.known_by_puuid = {}

    async def fetch_match_ids(self, session, puuid, start_t, end_t, max_matches=None):
        return [self.match_id]

    async def fetch_participants(self, session, player, **kwargs):
        self.known_by_puuid[player.puuid] = dict(kwargs.get("known") or {})
        return [self.stats_by_puuid[player.puuid]]


async def _analyse(db, fake, *players) -> list[int]:
    with patch("app.service.stats_runner.riot_client", return_value=fake), patch(
        "app.service.stats_runner.create_secure_session", MagicMock()
    ):
        return [await run_stats_extraction(db, player, 1_748_000_000, 1_749_000_000) for player in players]


async def test_each_player_sees_their_own_stats_in_a_shared_match(db_session):
    match_id = unique("EUW1")
    top = create_player(db_session, role=RoleEnum.TOP)
    jungle = create_player(db_session, role=RoleEnum.JUNGLE)
    fake = FakeRiotClient(
        match_id,
        {
            top.puuid: make_stats(match_id, top.puuid, champion="Gnar", player_role="TOP", kills=3, gold_diff_14=-350),
            jungle.puuid: make_stats(match_id, jungle.puuid, champion="LeeSin", player_role="JUNGLE", kills=8, gold_diff_14=420),
        },
    )

    top_snapshot, jungle_snapshot = await _analyse(db_session, fake, top, jungle)

    # El segundo análisis no recibe como caché la fila del primer jugador.
    assert fake.known_by_puuid[jungle.puuid] == {}

    [top_row] = get_matches_by_snapshot(db_session, top_snapshot, top.user_id)
    [jungle_row] = get_matches_by_snapshot(db_session, jungle_snapshot, jungle.user_id)
    assert (top_row.champion, top_row.kills, top_row.gold_diff_14) == ("Gnar", 3, -350)
    assert (jungle_row.champion, jungle_row.kills, jungle_row.gold_diff_14) == ("LeeSin", 8, 420)
    assert top_row.match_id == jungle_row.match_id
    assert db_session.scalar(
        select(func.count()).select_from(MatchParticipant).where(MatchParticipant.match_id == match_id)
    ) == 2

    ddragon = MagicMock(version="16.10.1")
    ddragon.champion_icon_url.side_effect = lambda version, champion: f"{champion}.png"
    with patch("app.service.dashboard.get_ddragon_client", AsyncMock(return_value=ddragon)):
        top_dashboard = await build_snapshot_dashboard(db_session, db_session.get(Snapshot, top_snapshot))
        jungle_dashboard = await build_snapshot_dashboard(db_session, db_session.get(Snapshot, jungle_snapshot))

    assert (top_dashboard.active_role, [c.champion_name for c in top_dashboard.played_champions]) == ("TOP", ["Gnar"])
    assert (jungle_dashboard.active_role, [c.champion_name for c in jungle_dashboard.played_champions]) == ("JUNGLE", ["LeeSin"])


async def test_a_player_reuses_their_own_cached_row(db_session):
    match_id = unique("EUW1")
    player = create_player(db_session, role=RoleEnum.MID)
    fake = FakeRiotClient(match_id, {player.puuid: make_stats(match_id, player.puuid)})

    await _analyse(db_session, fake, player)
    await _analyse(db_session, fake, player)

    assert set(fake.known_by_puuid[player.puuid]) == {match_id}
