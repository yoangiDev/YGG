import json

import pytest
from factories import MATCH_ID, enriched, make_match, make_timeline, puuid
from ygg_core.cli import main


@pytest.fixture
def participants_file(tmp_path):
    path = tmp_path / "partidas.json"
    path.write_text(json.dumps([enriched(3).to_dict()]), encoding="utf-8")
    return path


def test_stats_infers_most_played_role(participants_file, capsys):
    assert main(["stats", str(participants_file)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["active_role"] == "MID"
    assert [m["key"] for m in output["role_averages"]][:2] == ["gold_diff_14", "cs_diff_14"]
    assert output["radar"]["player_dataset"]["label"] == "partidas"


def test_stats_role_override_and_output_file(participants_file, tmp_path):
    out = tmp_path / "dashboard.json"
    assert main(["stats", str(participants_file), "--role", "BOTTOM", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["active_role"] == "ADC"


def test_fetch_requires_api_key(monkeypatch, capsys):
    monkeypatch.delenv("RIOT_API_KEY", raising=False)
    assert main(["fetch", "Jugador#EUW"]) == 2
    assert "RIOT_API_KEY" in capsys.readouterr().err


def test_invalid_riot_id_is_rejected():
    with pytest.raises(SystemExit):
        main(["fetch", "sin-tag"])


def test_reparse_and_store_commands(tmp_path, capsys):
    pytest.importorskip("duckdb")
    from ygg_core.store import MatchStore

    db = tmp_path / "ygg.duckdb"
    with MatchStore(db) as store:
        store.put_payload("match", MATCH_ID, make_match())
        store.put_payload("timeline", MATCH_ID, make_timeline())

    assert main(["reparse", puuid(4), "--store", str(db)]) == 0
    assert main(["store", "--store", str(db), "roles"]) == 0
    [row] = json.loads(capsys.readouterr().out)
    assert (row["role"], row["games"]) == ("ADC", 1)

    parquet = tmp_path / "out.parquet"
    assert main(["store", "--store", str(db), "export", str(parquet)]) == 0
    assert parquet.exists()
