from factories import champion_kill, enriched, make_match, make_timeline
from ygg_core.domain.participant import TIMELINE_VERSION
from ygg_core.timeline.role_impact import (
    count_turret_plates,
    count_wards_killed,
    early_kill_counts,
    extract_lane_visits,
    extract_objective_setups,
)

# Participants 1-5 blue and 6-10 red, in the order TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY.
PARTICIPANTS = make_match()["info"]["participants"]
JUNGLE_CAMP = {"x": 4000, "y": 7000}  # blue jungler: no lane


def timeline(events=None):
    """Timeline with all ten players in the jungle, away from the lanes."""
    data = make_timeline(events=events or {})
    for frame in data["info"]["frames"]:
        for participant in frame["participantFrames"].values():
            participant["position"] = dict(JUNGLE_CAMP)
    return data


def place(data, minute, pid, x, y):
    data["info"]["frames"][minute]["participantFrames"][str(pid)]["position"] = {"x": x, "y": y}


def test_a_gank_that_ends_in_a_kill_and_a_plate():
    data = timeline(
        {
            5: [champion_kill(290_000, killer=1, victim=6, assists=[2], x=1500, y=9000)],
            6: [{"type": "TURRET_PLATE_DESTROYED", "timestamp": 330_000, "killerId": 1, "laneType": "TOP_LANE", "teamId": 200}],
        }
    )
    data["info"]["frames"][6]["participantFrames"]["1"]["totalGold"] += 1000

    [visit] = extract_lane_visits(data, PARTICIPANTS, participant_id=2)

    assert (visit["lane"], visit["time"]) == ("TOP", 290)
    assert (visit["takedowns"], visit["deaths"], visit["structures"]) == (1, 0, 1)
    # In the factory the enemy top gains 45 more gold + experience per minute: from minute 4 to 6.
    assert visit["swing"] == 1000 - 2 * 45


def test_standing_in_a_lane_next_to_the_rival_is_a_visit():
    data = timeline()
    for minute in (4, 5):
        place(data, minute, 2, 1500, 8000)  # the blue jungler in top...
        place(data, minute, 6, 1800, 8500)  # ...next to the enemy top

    [visit] = extract_lane_visits(data, PARTICIPANTS, participant_id=2)

    assert (visit["lane"], visit["time"], visit["takedowns"], visit["deaths"], visit["structures"]) == ("TOP", 240, 0, 0, 0)
    assert visit["swing"] == -3 * 45  # from minute 4 to 7


def test_laners_only_visit_other_lanes():
    data = timeline({5: [champion_kill(290_000, killer=1, victim=6, assists=[], x=1500, y=9000)]})
    place(data, 8, 1, 7400, 7600)  # the blue top in mid...
    place(data, 8, 8, 7300, 7300)  # ...next to the enemy mid

    [roam] = extract_lane_visits(data, PARTICIPANTS, participant_id=1)

    assert (roam["lane"], roam["time"]) == ("MID", 480)


def test_objective_setups_group_the_grubs_and_count_the_vision():
    data = timeline(
        {
            9: [
                {"type": "WARD_PLACED", "timestamp": 500_000, "creatorId": 5, "wardType": "CONTROL_WARD", "position": {"x": 9700, "y": 4600}},
                {"type": "WARD_PLACED", "timestamp": 510_000, "creatorId": 2, "wardType": "YELLOW_TRINKET"},
            ],
            10: [
                {"type": "ELITE_MONSTER_KILL", "timestamp": 560_000, "killerId": 2, "killerTeamId": 100, "monsterType": "DRAGON"},
            ],
            12: [
                {"type": "ELITE_MONSTER_KILL", "timestamp": 700_000, "killerId": 7, "killerTeamId": 200, "monsterType": "HORDE"},
                {"type": "ELITE_MONSTER_KILL", "timestamp": 715_000, "killerId": 7, "killerTeamId": 200, "monsterType": "HORDE"},
            ],
        }
    )
    place(data, 9, 2, 9800, 4500)  # the blue jungler sets up the dragon (and places a ward there)

    dragon, grubs = extract_objective_setups(data, PARTICIPANTS, participant_id=2)

    assert dragon == {
        "objective": "DRAGON",
        "time": 560,
        "team_objective": True,
        "in_prep_zone": True,
        "contested": False,
        "player_wards": 1,
        "team_wards": 2,
    }
    assert (grubs["objective"], grubs["team_objective"], grubs["in_prep_zone"], grubs["team_wards"]) == ("HORDE", False, False, 0)


def test_plates_ward_kills_and_early_kills():
    data = timeline(
        {
            6: [{"type": "TURRET_PLATE_DESTROYED", "timestamp": 330_000, "killerId": 1, "laneType": "TOP_LANE", "teamId": 200}],
            7: [
                {"type": "TURRET_PLATE_DESTROYED", "timestamp": 400_000, "killerId": 1, "laneType": "TOP_LANE", "teamId": 200},
                {"type": "WARD_KILL", "timestamp": 410_000, "killerId": 5, "wardType": "YELLOW_TRINKET"},
            ],
            11: [champion_kill(650_000, killer=3, victim=8, assists=[], x=7400, y=7600)],
            12: [champion_kill(700_000, killer=3, victim=9, assists=[4], x=12000, y=2000)],
            20: [champion_kill(1_200_000, killer=4, victim=9, assists=[], x=12000, y=2000)],
        }
    )
    assert (count_turret_plates(data, 1), count_wards_killed(data, 5)) == (2, 1)
    assert early_kill_counts(data, PARTICIPANTS, participant_id=4) == (1, 2)  # the kill at minute 20 doesn't count


def test_enrichment_stores_the_role_metrics_with_the_current_version():
    stats = enriched(2)
    assert stats.timeline_version == TIMELINE_VERSION
    assert stats.objective_setups[0]["objective"] == "DRAGON"
    assert stats.objective_setups[0]["in_prep_zone"]
