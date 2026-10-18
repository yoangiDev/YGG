"""What comes out of the replays: the comparison with the league and why one wasn't decoded."""

import json
from types import SimpleNamespace
from unittest.mock import patch


from app.core.config import settings
from app.service import replays, review


def _game(match_id: str, win: bool, suboptimal: int, role: str = "BOTTOM") -> dict:
    flash = {"id": 0, "t": 900.0, "clock": "15:00", "kind": "flash", "tone": "bad", "severity": 1, "title": "Flash",
             "text": "…"}
    return {"match_id": match_id, "champion": "Jinx", "role": role, "win": win, "duration": 1800,
            "stats": {"flash_suboptimal": suboptimal, "kills": 5}, "flashes": [], "wp": None,
            "moments": [flash] * suboptimal, "numbers": {}}


def test_summarize_measures_the_player_against_their_tier_and_role():
    reference = {"leagues": {"GOLD": {"BOTTOM": {"games": 100, "columns": {
        # p10, p25, p50, p75, p90, mean, winners, losers, n
        "flash_suboptimal": [0.0, 1.0, 2.0, 3.0, 4.0, 2.0, 1.5, 2.5, 100],
    }}}}}
    games = [_game("EUW1_1", True, 1), _game("EUW1_2", False, 3), _game("EUW1_3", True, 2, role="UTILITY")]
    with patch.object(replays, "_reference", lambda: reference):
        # without a reference for their league (Silver), they are compared with Gold; the role is the most played
        summary = replays.summarize(games, "SILVER")
    assert (summary["tier"], summary["role"], summary["games"], summary["wins"]) == ("GOLD", "BOTTOM", 3, 2)
    metric = summary["metrics"]["flash_suboptimal"]
    assert metric == {"value": 2.0, "percentile": 50, "median": 2.0, "winners": 1.5, "losers": 2.5}  # only the BOTTOM ones
    assert "kills" not in summary["metrics"]  # without a reference, there is nothing to compare it with
    flash = next(p for p in summary["patterns"] if p["kind"] == "flash")  # the patterns, from those of their role
    assert flash["reference"] == {"median": 2.0, "winners": 1.5, "losers": 2.5}


def test_a_game_the_decoder_cannot_read_says_why():
    # what cosecha.py writes when a new build arrives within the same patch (a hotfix)
    output = ("9 replays · 0 ya hechas · 9 por hacer\n"
              "  ERROR  EUW1-7999587853: ValueError: no hay tabla de tipos para la build 16.19.823.0722 (hay de 16.19.821.7343)\n"
              "  ERROR  EUW1-7999518676: RuntimeError: the emulator went off the rails\n")
    because = replays._why(output)
    assert because["EUW1-7999587853"] == "This game was played on build 16.19.823.0722, which the decoder doesn't read yet."
    assert because["EUW1-7999518676"] == "The replay could not be decoded (the emulator went off the rails)."


REVIEW = {"headline": "Solid laner", "coach_summary": "s", "lessons": [], "strengths": [], "game_notes": [],
          "moment_notes": [], "next_game": ["ward"]}


class _FakeClaude:
    """What the worker uses from anthropic.AsyncAnthropic: `async with` and beta.messages.stream(...).get_final_message()."""

    sent: dict = {}

    def __init__(self, *_args, **_kwargs):
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def _stream(self, **kwargs):
        _FakeClaude.sent = kwargs
        final = SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5",
                                content=[SimpleNamespace(type="thinking", thinking=""),
                                         SimpleNamespace(type="text", text=json.dumps(REVIEW))])

        class _Stream:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_exc):
                return False

            async def get_final_message(self):
                return final

        return _Stream()


async def test_the_review_is_claudes_json_with_its_model(monkeypatch):
    summary = {"tier": "GOLD", "role": "BOTTOM", "games": 1, "wins": 1, "metrics": {}, "patterns": []}
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert await review.write_review(summary, [_game("EUW1_1", True, 1)]) is None  # without a key, no review

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    with patch.object(review.anthropic, "AsyncAnthropic", _FakeClaude):
        result = await review.write_review(summary, [_game("EUW1_1", True, 1)])
    assert result == REVIEW | {"model": "claude-opus-5-5"}
    # Claude receives each match's moments with their id, which is what the review cites them by
    sent_payload = json.loads(_FakeClaude.sent["messages"][0]["content"])
    assert sent_payload["games"][0]["moments"][0]["id"] == "EUW1_1:0"
