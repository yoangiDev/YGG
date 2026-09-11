import pytest

pytest.importorskip("duckdb")

from factories import MATCH_ID, enriched, make_match, make_timeline, puuid
from ygg_core.store import MatchStore, rebuild_participants


@pytest.fixture
def store(tmp_path):
    with MatchStore(tmp_path / "ygg.duckdb") as opened:
        yield opened


def test_roundtrip_preserves_every_field(store):
    original = enriched(1)
    store.upsert_participants([original])
    assert store.participants(puuid=puuid(1)) == [original]


def test_upsert_replaces_same_match_and_player(store):
    stats = enriched(1)
    store.upsert_participants([stats])
    stats.kills = 99
    store.upsert_participants([stats])
    [loaded] = store.participants()
    assert loaded.kills == 99


def test_two_players_in_the_same_match_are_separate_rows(store):
    store.upsert_participants([enriched(1), enriched(6)])
    rows = store.participants()
    assert {(r.match_id, r.puuid, r.champion) for r in rows} == {
        (MATCH_ID, puuid(1), "Gnar"),
        (MATCH_ID, puuid(6), "Renekton"),
    }


def test_raw_payload_cache(store):
    assert store.get_payload("match", MATCH_ID) is None
    store.put_payload("match", MATCH_ID, make_match())
    assert store.get_payload("match", MATCH_ID) == make_match()
    assert [match_id for match_id, _ in store.iter_payloads("match")] == [MATCH_ID]


def test_role_summary(store):
    store.upsert_participants([enriched(pid) for pid in range(1, 11)])
    summary = store.role_summary()
    assert {row["role"]: row["games"] for row in summary} == {
        "TOP": 2, "JUNGLE": 2, "MID": 2, "ADC": 2, "SUPPORT": 2,
    }
    [top] = store.role_summary(puuid(1))
    assert (top["role"], top["games"], top["win_rate"], top["kda"]) == ("TOP", 1, 100.0, 1.75)


def test_filters_and_known_participants(store):
    store.upsert_participants([enriched(1), enriched(2, match_id="EUW1_OTHER")])
    assert [p.player_role for p in store.participants(role="jungle")] == ["JUNGLE"]
    assert set(store.known_participants(puuid(2))) == {"EUW1_OTHER"}


def test_parquet_roundtrip(store, tmp_path):
    rows = [enriched(pid) for pid in (1, 2, 3)]
    store.upsert_participants(rows)
    path = tmp_path / "export" / "participants.parquet"
    assert store.export_parquet(path) == 3

    with MatchStore() as other:
        assert other.import_parquet(path) == 3
        assert sorted(other.participants(), key=lambda p: p.puuid) == rows


def test_rebuild_from_raw_payloads(store):
    store.put_payload("match", MATCH_ID, make_match())
    store.put_payload("timeline", MATCH_ID, make_timeline())
    assert rebuild_participants(store, puuid(3)) == 1
    [mid] = store.participants(puuid=puuid(3))
    assert (mid.solo_kills, mid.roaming_proactivity, mid.timeline_enriched) == (1, 1, True)


def test_ad_hoc_sql(store):
    store.upsert_participants([enriched(pid) for pid in range(1, 6)])
    rows = store.query("select champion from participants where kills >= ? order by champion", [5])
    # kills = pid % 5 + 2 → Ahri (3) tiene 5 y Jinx (4) tiene 6.
    assert [row["champion"] for row in rows] == ["Ahri", "Jinx"]
