"""Snapshot endpoints and dashboard aggregates.

The timeline metrics are tested in packages/ygg-core, which is where they live.
"""

from datetime import datetime

from fastapi.testclient import TestClient

from app.schemas.match import MatchResponse
from main import app

client = TestClient(app)


class TestSnapshotsAuth:
    def test_list_snapshots_requires_auth(self):
        assert client.get("/snapshots/player/1").status_code == 401

    def test_get_snapshot_requires_auth(self):
        assert client.get("/snapshots/99999").status_code == 401

    def test_job_status_requires_auth(self):
        assert client.get("/snapshots/jobs/some-job-id").status_code == 401


class TestSnapshotsCRUD:
    def test_get_snapshot_not_found(self, auth_headers):
        assert client.get("/snapshots/99999", headers=auth_headers).status_code == 404

    def test_list_snapshots_player_not_found(self, auth_headers):
        assert client.get("/snapshots/player/99999", headers=auth_headers).status_code == 404

    def test_dashboard_not_found(self, auth_headers):
        assert client.get("/snapshots/99999/dashboard", headers=auth_headers).status_code == 404

    def test_matches_of_unknown_snapshot_not_found(self, auth_headers):
        assert client.get("/matches/snapshot/99999", headers=auth_headers).status_code == 404

    def test_job_not_found(self, auth_headers):
        assert client.get("/snapshots/jobs/nonexistent-job-id", headers=auth_headers).status_code == 404

    def test_delete_snapshot_not_found(self, auth_headers):
        assert client.delete("/snapshots/99999", headers=auth_headers).status_code == 404


def _match(match_id: str, **overrides) -> MatchResponse:
    values = dict(
        match_id=match_id, creation_time=datetime.now(), champion="Garen", win=True, duration=1500,
        kills=5, deaths=6, assists=5, kill_participation=50.0, vision=20, damage=15000, gold=10000,
        total_cs=150, damage_share=25.0, first_dragon=True, void_grubs=False, herald=True,
    )
    values.update(overrides)
    return MatchResponse(**values)


class TestMatchResponse:
    def test_death_coordinates_are_normalized_for_the_heatmap(self):
        match = _match("EUW_SCALE", death_events=[{"time": 100, "x": 0, "y": 0}, {"time": 200, "x": 15000, "y": 15000}])
        assert [(d["norm_x"], d["norm_y"]) for d in match.death_events_normalized] == [(0.0, 1.0), (1.0, 0.0)]
