import pytest
from factories import enriched
from ygg_core.domain.participant import ParticipantStats, PlayerRef
from ygg_core.domain.roles import (
    dashboard_role,
    role_filter_for_player,
    role_from_position,
    role_matches_filter,
)


def test_participant_json_roundtrip():
    original = enriched(1)
    assert ParticipantStats.from_dict(original.to_dict()) == original


def test_from_dict_ignores_unknown_keys():
    data = enriched(2).to_dict() | {"campo_de_otra_version": 1}
    assert ParticipantStats.from_dict(data).champion == "LeeSin"


def test_player_label():
    assert PlayerRef("abc", "Faker", "KR1").label == "Faker#KR1"
    assert PlayerRef("0123456789abcdef").label == "0123456789ab"


@pytest.mark.parametrize(
    ("position", "role"),
    [("TOP", "TOP"), ("JUNGLE", "JUNGLE"), ("MIDDLE", "MID"), ("BOTTOM", "ADC"), ("UTILITY", "SUPPORT"), ("", "UNKNOWN"), (None, "UNKNOWN")],
)
def test_role_from_position(position, role):
    assert role_from_position(position) == role


def test_player_roles():
    assert role_filter_for_player("BOTTOM") == "ADC"
    assert role_filter_for_player(None) == "ALL"
    assert dashboard_role("ALL") == "MID"
    assert dashboard_role("BOTTOM") == "ADC"
    assert dashboard_role("SUPPORT") == "SUPPORT"
    assert role_matches_filter("MID", "all") is True
    assert role_matches_filter("MID", "top") is False
