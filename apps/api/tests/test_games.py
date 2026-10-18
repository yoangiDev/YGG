"""Analysing individual matches after 16.20: you upload the .rofl on the web and the API checks it, decodes it and analyses it.
The file has to be that match and your account must have played it, before spending quota; the quota
is FREE_LIMIT per rolling 24 hours (failed ones don't count); accounts with replay access have none."""

import json
import struct

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models.game_analysis import GameAnalysis
from app.db.models.user import User
from app.routers import games
from app.service import replays
from main import app
from tests.helpers import create_player, unique

client = TestClient(app)

PLAYERS = [(f"Player {i}", "EUW") for i in range(10)]


def _rofl(players=PLAYERS, build: str = "16.20.824.8524", declared: int = 16, size: int = 100) -> bytes:
    """A minimal replay with the structure that `replays.rofl_info` reads: header with the build, a zstd block (its
    17-byte header and a frame that declares `declared` bytes) and, at the end, the metadata with its length."""
    stats = json.dumps([{"RIOT_ID_GAME_NAME": n, "RIOT_ID_TAG_LINE": t, "SKIN": "Jinx"} for n, t in players])
    meta = json.dumps({"gameLength": 1800000, "statsJson": stats}).encode()
    frame = b"\x28\xb5\x2f\xfd" + bytes([0x20, declared]) + b"x" * 8  # a single segment, size in 1 byte
    block = struct.pack("<IIBII", 0, 0, 1, size, len(frame))
    return (b"RIOT\x02\x00" + b"\x00" * 8 + bytes([len(build)]) + build.encode() + block + frame
            + meta + struct.pack("<I", len(meta)))


@pytest.fixture
def mine(monkeypatch, tmp_path):
    """Fake Riot, decoder, analysis and review: the match is played by `puuid` (the first of PLAYERS)."""
    state = {"puuid": unique("puuid"), "analysed": [], "decode": {}, "rofls": {}}

    async def records(player, match_ids):
        return {m: {"participants": [{"puuid": state["puuid"] if i == 0 else f"other{i}", "championName": "Jinx",
                                      "riotIdGameName": n.upper(), "riotIdTagline": t}  # case-insensitive
                                     for i, (n, t) in enumerate(PLAYERS)]} for m in match_ids}

    def decode(versions, rofls):
        state["decoded"] = versions
        state["rofls"] |= rofls  # accumulates: each upload calls decode with its own, and the tests look at the earlier ones
        return {m: state["decode"][m] for m in versions if m in state["decode"]}

    def analyse(match_id, champion, record):
        assert state["rofls"][match_id].exists()  # the file is still there while it is analysed
        state["analysed"].append((match_id, champion))
        return {"match_id": match_id, "champion": champion}

    async def review(summary, analysed):
        return None

    monkeypatch.setattr(replays, "records", records)
    monkeypatch.setattr(replays, "decode", decode)
    monkeypatch.setattr(replays, "matches_riot", lambda match_id, record: state.get("matches", True))
    monkeypatch.setattr(replays, "analyse", analyse)
    monkeypatch.setattr(replays, "rate", lambda game, tier: game | {"rating": {"score": 50}})
    monkeypatch.setattr(replays, "summarize", lambda analysed, tier: {"games": len(analysed), "patterns": []})
    monkeypatch.setattr(games, "write_review", review)
    monkeypatch.setattr(replays, "_uploads", lambda: tmp_path / "uploads")
    monkeypatch.setattr(replays, "_decoded", lambda: tmp_path / "decoded")
    return state


async def _headers(db, puuid: str, role: str = "user") -> dict[str, str]:
    name = unique("games")
    token = client.post("/auth/register", json={"email": f"{name}@example.com", "username": name,
                                                "password": "password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user = await db.get(User, client.get("/auth/me", headers=headers).json()["id"])
    user.role = role
    await db.commit()
    await create_player(db, user=user, puuid=puuid)
    return headers


def _ids(n: int, base: int = 900_000_000) -> list[str]:
    return [f"EUW1_{base + i}" for i in range(n)]


def _up(match_id: str, headers, data: bytes | None = None):
    return client.post(f"/games/{match_id}/replay", content=_rofl() if data is None else data, headers=headers)


async def test_upload_a_replay_and_it_gets_analysed(db, mine):
    headers = await _headers(db, mine["puuid"])
    match_id = _ids(1)[0]
    up = _up(match_id, headers)
    assert (up.status_code, up.json()["status"]) == (202, "processing")
    # the analysis runs in the background (the TestClient waits for it): with the exe of its build, and the .rofl isn't left behind
    assert mine["decoded"] == {match_id: "16.20.824.8524"} and mine["analysed"] == [(match_id, "Jinx")]
    assert not mine["rofls"][match_id].parent.exists()  # neither the .rofl nor its folder remain
    item = client.get("/games/analyses", headers=headers).json()["items"][0]
    assert (item["status"], item["result"]["games"][0]["rating"]["score"]) == ("done", 50)
    assert _up(match_id, headers).json()["status"] == "done"  # again: the same one, without analysing it anew
    assert len(mine["analysed"]) == 1


async def test_the_file_must_be_that_game_and_yours_before_it_costs_anything(db, mine):
    headers = await _headers(db, mine["puuid"])
    match_id = _ids(1, 900_000_100)[0]
    bad = _up(match_id, headers, b"PK\x03\x04 not a replay")
    assert (bad.status_code, bad.json()["detail"]) == (400, "This is not a League of Legends replay (.rofl).")
    other = _up(match_id, headers, _rofl(players=[("Someone", "KR1")] + PLAYERS[1:]))
    assert (other.status_code, other.json()["detail"]) == (400, f"This file is not the replay of {match_id}.")

    mine["puuid"] = "someone-else"  # the match is real, but your account isn't in it
    assert _up(match_id, headers).status_code == 403
    analyses = client.get("/games/analyses", headers=headers).json()
    assert analyses["items"] == [] and analyses["quota"]["used"] == 0


async def test_three_a_day_for_free_and_failures_do_not_count(db, mine):
    headers = await _headers(db, mine["puuid"])
    ids = _ids(5, 900_000_200)
    mine["decode"][ids[0]] = "Patch 16.21 can't be read yet: it arrives a few days after the patch."
    for match_id in ids[:3]:
        assert _up(match_id, headers).status_code == 202
    first = next(i for i in client.get("/games/analyses", headers=headers).json()["items"] if i["match_id"] == ids[0])
    assert (first["status"], first["error"]) == ("error", mine["decode"][ids[0]])
    assert not mine["rofls"][ids[0]].parent.exists()

    assert _up(ids[3], headers).status_code == 202  # the one that failed didn't spend
    over = _up(ids[4], headers)
    assert (over.status_code, over.json()["detail"]) == (429, "daily_limit")
    quota = client.get("/games/analyses", headers=headers).json()["quota"]
    assert (quota["limit"], quota["used"]) == (3, 3) and quota["next_at"]
    del mine["decode"][ids[0]]
    retry = _up(ids[0], headers)  # the one that failed didn't spend, but retrying it doesn't skip the limit either
    assert (retry.status_code, retry.json()["detail"]) == (429, "daily_limit")


async def test_a_replay_that_is_not_the_game_riot_has_is_rejected_and_not_kept(db, mine):
    headers = await _headers(db, mine["puuid"])
    match_id = _ids(1, 900_000_300)[0]
    mine["matches"] = False
    row = _up(match_id, headers).json()
    assert client.get("/games/analyses", headers=headers).json()["items"][0]["status"] == "error"
    assert mine["analysed"] == [] and row["match_id"] == match_id


async def test_only_a_finished_analysis_spends_the_free_quota(db, mine):
    headers = await _headers(db, mine["puuid"])
    me = client.get("/auth/me", headers=headers).json()["id"]
    ids = _ids(5, 900_000_400)
    for match_id, status in zip(ids, ("done", "done", "processing", "error", "requested"), strict=True):
        db.add(GameAnalysis(user_id=me, match_id=match_id, status=status))
    await db.commit()
    assert client.get("/games/analyses", headers=headers).json()["quota"]["used"] == 2  # only the finished ones spend
    over = _up(_ids(1, 900_000_410)[0], headers)  # 2 spent + 1 in progress reserve the 3
    assert (over.status_code, over.json()["detail"]) == (429, "daily_limit")


async def test_premium_has_no_limit(db, mine):
    headers = await _headers(db, mine["puuid"], role="premium")
    for match_id in _ids(5, 900_000_300):
        assert _up(match_id, headers).status_code == 202
    assert client.get("/games/analyses", headers=headers).json()["quota"]["limit"] is None


async def test_a_restart_fails_what_was_half_done(db, mine):
    headers = await _headers(db, mine["puuid"])
    match_id = _ids(1, 900_000_400)[0]
    _up(match_id, headers)
    row = await db.scalar(select(GameAnalysis).where(GameAnalysis.match_id == match_id,
                                                     GameAnalysis.status == "done").order_by(GameAnalysis.id.desc()))
    assert row is not None
    row.status = "processing"
    await db.commit()
    await games.recover_processing()
    await db.refresh(row)
    assert row.status == "error" and "upload it again" in (row.error or "")


async def test_an_unverified_account_cannot_upload(db, mine):
    from app.db.models.player import Player

    headers = await _headers(db, mine["puuid"])
    player = await db.scalar(select(Player).where(Player.puuid == mine["puuid"]))
    player.verified_at = None
    await db.commit()
    r = _up(_ids(1, 900_000_500)[0], headers)
    assert (r.status_code, r.json()["detail"]) == (403, "Verify your League account first, in Account.")


def test_rofl_info_reads_the_structure_and_refuses_what_would_blow_up_the_decoder():
    build, ids = replays.rofl_info(_rofl())
    assert build == "16.20.824.8524" and ids == {replays.riot_id(n, t) for n, t in PLAYERS}
    refused = [
        _rofl(declared=200),  # a frame that declares more than its block: the decompressor would reserve that memory
        _rofl(size=replays.MAX_BLOCK + 1),  # a block larger than any match
        _rofl(players=PLAYERS[:9]),
        _rofl(build="../../etc"),
        b"", b"RIOT", _rofl()[:-1], _rofl()[:40], b"RIOT" + b"\xff" * 100,
    ]
    for data in refused:
        with pytest.raises(ValueError):
            replays.rofl_info(data)


async def test_a_body_over_the_limit_is_cut_even_without_content_length(db, mine, monkeypatch):
    monkeypatch.setattr(games, "MAX_ROFL", 100)
    headers = await _headers(db, mine["puuid"])
    declared = _up(_ids(1, 900_000_600)[0], headers, b"x" * 101)
    chunked = client.post(f"/games/{_ids(1, 900_000_601)[0]}/replay", content=iter([b"x" * 60, b"x" * 60]),
                          headers=headers)
    assert (declared.status_code, chunked.status_code) == (413, 413)
    assert mine["rofls"] == {}  # it never touched the decoder


async def test_uploads_in_flight_are_capped_per_user_and_the_id_cannot_climb_out(db, mine):
    headers = await _headers(db, mine["puuid"])
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    for match_id in _ids(games.MAX_PER_USER, 900_000_700):
        db.add(GameAnalysis(user_id=user_id, match_id=match_id, status="processing"))
    await db.commit()
    busy = _up(_ids(1, 900_000_710)[0], headers)
    assert (busy.status_code, busy.json()["detail"]) == (429, "Wait for your other analyses to finish.")
    # off route, digits from another alphabet, and short
    for bad in ("..%2F..%2Fetc%2Fpasswd", "EUW1_%D9%A1%D9%A2%D9%A3%D9%A4%D9%A5%D9%A6", "EUW1_12345"):
        assert client.post(f"/games/{bad}/replay", content=_rofl(), headers=headers).status_code in (404, 422)
