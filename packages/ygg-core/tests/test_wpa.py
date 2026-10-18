"""Distribution of WPA among a player's events."""

from ygg_core.metrics.wpa import wpa_report
from ygg_core.metrics.wpa_model import MODEL

ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def _match(red_gold_lead: int = 0, shutdown: int = 0) -> tuple[dict, dict]:
    participants = [
        {"participantId": pid, "teamId": 100 if pid <= 5 else 200, "puuid": f"p{pid}",
         "teamPosition": ROLES[(pid - 1) % 5], "championName": f"Champ{pid}"}
        for pid in range(1, 11)
    ]
    frames = [
        {"timestamp": m * 60_000, "events": [],
         "participantFrames": {str(pid): {"totalGold": 500 + 400 * m + (red_gold_lead * m // 15 if pid > 5 else 0),
                                          "xp": 300 * m, "level": 1 + m // 2} for pid in range(1, 11)}}
        for m in range(16)
    ]
    frames[0]["events"] = [
        # The blue top (1) kills the red top (6) with the jungler (2); with the red one dead, the jungler takes the dragon.
        {"type": "CHAMPION_KILL", "timestamp": 300_000, "killerId": 1, "victimId": 6, "assistingParticipantIds": [2]},
        {"type": "ELITE_MONSTER_KILL", "timestamp": 310_000, "killerId": 2, "killerTeamId": 100, "monsterType": "DRAGON",
         "monsterSubType": "FIRE_DRAGON"},
        # The blue top dies and, while dead, their outer turret falls. Not right on a frame (600,000):
        # the kill's gold would already be inside the frame and wouldn't be seen arriving.
        {"type": "CHAMPION_KILL", "timestamp": 590_000, "killerId": 7, "victimId": 1, "assistingParticipantIds": [],
         "bounty": 300, "shutdownBounty": shutdown},
        {"type": "BUILDING_KILL", "timestamp": 610_000, "killerId": 6, "teamId": 100, "buildingType": "TOWER_BUILDING",
         "towerType": "OUTER_TURRET", "laneType": "TOP_LANE"},
    ]
    match_data = {"info": {"participants": participants, "gameDuration": 15 * 60, "teams": []}}
    return match_data, {"info": {"frames": frames}}


def test_events_signs_total_and_grade():
    match_data, timeline = _match()
    report = wpa_report(match_data, timeline, "p1", MODEL)

    assert report is not None
    by_kind = {e["kind"]: e for e in report.events}
    assert set(by_kind) == {"KILL", "OBJECTIVE_AFTER_KILL", "DEATH", "CONCEDED_WHILE_DEAD"}
    assert by_kind["KILL"]["wpa"] > 0 and by_kind["KILL"]["target"] == "Champ6"
    assert by_kind["DEATH"]["wpa"] < 0 and by_kind["DEATH"]["target"] == "Champ7"
    assert by_kind["CONCEDED_WHILE_DEAD"]["wpa"] < 0 and by_kind["CONCEDED_WHILE_DEAD"]["target"] == "TOWER_OUTER_TOP"
    assert report.total == round(sum(e["wpa"] for e in report.events), 2)
    assert report.grade is not None and 0 <= report.grade <= 100
    assert len(report.wp_curve) == 16


def test_each_event_explains_its_value_and_its_share():
    match_data, timeline = _match()
    report = wpa_report(match_data, timeline, "p1", MODEL)
    assert report is not None
    by_kind = {e["kind"]: e for e in report.events}

    kill, death, tower = by_kind["KILL"], by_kind["DEATH"], by_kind["CONCEDED_WHILE_DEAD"]
    assert (kill["shared_with"], kill["share"]) == (2, 0.5)  # killed the red top with the jungler
    assert abs(kill["wpa"] - kill["team_wpa"] * kill["share"]) < 0.02
    assert (death["shared_with"], death["share"]) == (1, 1.0)  # the death is entirely theirs
    for event in (kill, death, tower):  # what each feature explains adds up to the event's value
        assert abs(sum(d["wpa"] for d in event["drivers"]) - event["team_wpa"]) < 0.1
    assert {d["factor"]: d["change"] for d in kill["drivers"]}["dead"] == 1  # one enemy fewer
    # Before 15 an outer turret is worth its gold: the model gives it no weight of its own (it ended up at 0 without negative weights).
    assert [(d["factor"], d["change"]) for d in tower["drivers"]] == [("gold_k", -round(MODEL.event_gold["TOWER_OUTER"], 1))]


def test_an_objective_is_shared_without_counting_it_twice():
    """Half to whoever takes it, half to those who killed the enemy who was still dead: it adds up to its entire value."""
    match_data, timeline = _match()
    top = wpa_report(match_data, timeline, "p1", MODEL)
    jungle = wpa_report(match_data, timeline, "p2", MODEL)
    assert top is not None and jungle is not None

    dragon = next(e for e in top.events if e["target"] == "DRAGON_1")
    shares = [e["wpa"] for report in (top, jungle) for e in report.events if e["target"] == "DRAGON_1"]
    assert sorted(e["kind"] for r in (top, jungle) for e in r.events if e["target"] == "DRAGON_1") == [
        "OBJECTIVE", "OBJECTIVE_AFTER_KILL", "OBJECTIVE_AFTER_KILL",
    ]
    assert abs(sum(shares) - dragon["team_wpa"]) < 0.02


def test_a_play_is_worth_the_same_in_a_lost_game():
    """With 1 k of gold per player behind, the WP is already low, but the death is worth the same as when even."""
    even = wpa_report(*_match(), "p1", MODEL)
    lost = wpa_report(*_match(red_gold_lead=5000), "p1", MODEL)
    assert even is not None and lost is not None
    death_even = next(e for e in even.events if e["kind"] == "DEATH")
    death_lost = next(e for e in lost.events if e["kind"] == "DEATH")
    assert death_lost["wp_before"] < 20 < death_even["wp_before"]
    assert death_lost["wpa"] == death_even["wpa"]
    assert lost.grade is not None and even.grade is not None


def test_giving_a_shutdown_costs_its_gold():
    plain = next(e for e in wpa_report(*_match(), "p1", MODEL).events if e["kind"] == "DEATH")  # type: ignore[union-attr]
    shutdown = next(e for e in wpa_report(*_match(shutdown=1000), "p1", MODEL).events if e["kind"] == "DEATH")  # type: ignore[union-attr]
    assert (shutdown["bounty"], shutdown["shutdown"]) == (300, 1000)
    gold = {d["factor"]: d["change"] for d in shutdown["drivers"]}["gold_k"]
    assert gold == -round(300 * MODEL.event_gold["KILL"] + 1000 * MODEL.event_gold["SHUTDOWN"], 1)
    assert shutdown["wpa"] < 2 * plain["wpa"] < 0


def test_a_death_notes_the_gold_lost_while_dead():
    death = next(e for e in wpa_report(*_match(), "p1", MODEL).events if e["kind"] == "DEATH")  # type: ignore[union-attr]
    low, high = death["gold_lost"]
    assert 0 < low < high  # going back to the lane loses more than the respawn alone
    kill = next(e for e in wpa_report(*_match(), "p1", MODEL).events if e["kind"] == "KILL")  # type: ignore[union-attr]
    assert kill["gold_lost"] == [0, 0]  # the note applies to deaths only
