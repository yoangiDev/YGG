"""Endpoints de snapshots y cableado de los schemas del dashboard.

Las métricas de timeline (gank deaths, visión de objetivos, dragon setups)
se testean en packages/ygg-core, que es donde viven.
"""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.schemas.dashboard import RadarChartData, RadarDataset, SnapshotDashboardResponse
from app.schemas.match import MatchResponse
from main import app

client = TestClient(app)


class TestSnapshotsAuth:
    def test_list_snapshots_requires_auth(self):
        response = client.get("/snapshots/player/1")
        assert response.status_code == 403

    def test_get_snapshot_requires_auth(self):
        response = client.get("/snapshots/99999")
        assert response.status_code == 403

    def test_job_status_requires_auth(self):
        response = client.get("/snapshots/jobs/some-job-id")
        assert response.status_code == 403


class TestSnapshotsCRUD:
    def test_get_snapshot_not_found(self, auth_headers):
        response = client.get("/snapshots/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_list_snapshots_player_not_found(self, auth_headers):
        response = client.get("/snapshots/player/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_job_not_found(self, auth_headers):
        response = client.get("/snapshots/jobs/nonexistent-job-id", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_snapshot_not_found(self, auth_headers):
        response = client.delete("/snapshots/99999", headers=auth_headers)
        assert response.status_code == 404


def _match(match_id: str, **overrides) -> MatchResponse:
    values = dict(
        match_id=match_id, creation_time=datetime.now(), champion="Garen", win=True, duration=1500,
        kills=5, deaths=6, assists=5, kill_participation=50.0, vision=20, damage=15000, gold=10000,
        total_cs=150, damage_share=25.0, first_dragon=True, void_grubs=False, herald=True,
    )
    values.update(overrides)
    return MatchResponse(**values)


def _dashboard(matches: list[MatchResponse], role: str = "MID") -> SnapshotDashboardResponse:
    return SnapshotDashboardResponse(
        snapshot_id=1, player_id=1, player_name="Test#EUW", date_from=datetime.now(),
        date_to=datetime.now(), description="Test", notes="", active_role=role,
        role_averages=[], played_champions=[], matches=matches,
        radar_data=RadarChartData(
            axes=[], player_dataset=RadarDataset(label="", values={}, normalized_values={}),
            rank_datasets={}, pro_datasets={},
        ),
    )


class TestDashboardSchemas:
    def test_match_response_deaths_by_phase(self):
        deaths = [{"time": t, "x": 1000, "y": 1000} for t in (100, 479, 480, 800, 840, 1200)]
        assert _match("EUW_123", death_events=deaths).deaths_by_phase == {
            "early_deaths": 2, "mid_deaths": 2, "late_deaths": 2,
        }

    def test_dashboard_aggregates_deaths_by_phase(self):
        first = _match("EUW_1", deaths=2, death_events=[{"time": 300}, {"time": 600}])
        second = _match("EUW_2", deaths=3, death_events=[{"time": 1000}, {"time": 1200}, {"time": 200}])
        assert _dashboard([first, second]).deaths_by_phase == {
            "early_deaths": 2, "mid_deaths": 1, "late_deaths": 2,
        }

    def test_match_response_coordinates_normalization(self):
        match = _match(
            "EUW_SCALE",
            death_events=[{"time": 100, "x": 0, "y": 0}, {"time": 200, "x": 15000, "y": 15000}],
            ward_events=[{"time": 50, "x": 3000, "y": 12000, "type": "yellow"}],
        )
        assert [(d["norm_x"], d["norm_y"]) for d in match.death_events_normalized] == [(0.0, 1.0), (1.0, 0.0)]
        assert (match.ward_events_normalized[0]["norm_x"], match.ward_events_normalized[0]["norm_y"]) == (0.2, 0.2)

    def test_dragon_setups_summary(self):
        match = _match("EUW1_TEST", dragon_setups=[
            {"team_dragon": True, "in_prep_zone": True, "at_kill_zone": True, "secured_by_jg": True},
            {"team_dragon": True, "in_prep_zone": False, "at_kill_zone": False, "secured_by_jg": False},
        ])
        assert match.dragon_setups_summary["setup_rate"] == 50.0

    def test_performance_trends_are_chronological_with_moving_average(self):
        now = datetime.now()
        # KDA 2 y 4, desordenadas a propósito.
        older = _match("EUW_T1", kills=2, deaths=2, assists=2, creation_time=now - timedelta(days=2))
        newer = _match("EUW_T2", kills=4, deaths=2, assists=4, creation_time=now - timedelta(days=1))
        trends = _dashboard([newer, older], role="ADC").performance_trends
        assert [(t.match_id, t.game_num, t.kda, t.kda_moving_avg) for t in trends] == [
            ("EUW_T1", 1, 2.0, 2.0),
            ("EUW_T2", 2, 4.0, 3.0),
        ]
