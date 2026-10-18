"""The API only accepts the supported regions: EUW, NA, LAS, LAN, KR, EUNE and BR."""

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.common import Region


def test_regions_are_case_insensitive_and_limited():
    region = TypeAdapter(Region)
    assert region.validate_python("euw") == "EUW"
    with pytest.raises(ValidationError):
        region.validate_python("OCE")


def test_endpoints_reject_other_regions(client, auth_headers):
    player = {"game_name": "Faker", "tag_line": "KR1", "region": "JP"}
    assert client.post("/players/", json=player, headers=auth_headers).status_code == 422
    assert client.get("/league/cutoffs?region=TR", headers=auth_headers).status_code == 422
    assert client.get("/snapshots/1/dashboard?compare_region=RU", headers=auth_headers).status_code == 422
