from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.db.models.rank_cutoff import RankCutoff
from app.service.league_service import is_stale
from main import app

client = TestClient(app)


class TestCors:
    def _preflight(self, origin: str):
        return client.options(
            "/players/",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )

    def test_allowed_origin_is_echoed_not_wildcard(self):
        origin = settings.cors_origin_list[0]
        response = self._preflight(origin)
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_unknown_origin_is_rejected(self):
        response = self._preflight("https://evil.example")
        assert "access-control-allow-origin" not in response.headers

    def test_origin_list_parsing(self):
        parsed = Settings(
            database_url="postgresql://x", secret_key="x", cors_origins=" https://a.dev, ,https://b.dev "
        )
        assert parsed.cors_origin_list == ["https://a.dev", "https://b.dev"]


class TestRankCutoffStaleness:
    def _cutoff(self, fetched_at: datetime) -> RankCutoff:
        return RankCutoff(
            platform="euw1", grandmaster_cutoff_lp=500, challenger_cutoff_lp=900, fetched_at=fetched_at
        )

    def test_fresh_aware_record(self):
        assert is_stale(self._cutoff(datetime.now(timezone.utc) - timedelta(hours=1))) is False

    def test_stale_aware_record(self):
        assert is_stale(self._cutoff(datetime.now(timezone.utc) - timedelta(hours=5))) is True

    def test_legacy_naive_record_is_treated_as_utc(self):
        naive_utc = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        assert is_stale(self._cutoff(naive_utc)) is False
