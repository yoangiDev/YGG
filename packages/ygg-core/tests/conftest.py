import pytest
from factories import MATCH_ID, load_json
from ygg_core.riot.rate_limiter import reset_riot_rate_limiter


@pytest.fixture
def match_payload() -> dict:
    return load_json(f"match_v5/{MATCH_ID}.json")


@pytest.fixture
def timeline_payload() -> dict:
    return load_json(f"match_v5/{MATCH_ID}_timeline.json")


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    reset_riot_rate_limiter()
    yield
    reset_riot_rate_limiter()
