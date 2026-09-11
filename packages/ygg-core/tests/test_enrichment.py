from factories import blank_stats, enriched
from ygg_core.timeline.enrichment import enrich_with_timeline
from ygg_core.timeline.objectives import compute_objective_vision_score, extract_dragon_setups

ENEMY_IDS = {"TOP": 6, "JUNGLE": 2, "MID": 3, "ADC": 4, "SUPPORT": 5}


def _timeline(*events, participant_frames=None, timestamp=None):
    frame = {"events": list(events)}
    if participant_frames is not None:
        frame["participantFrames"] = participant_frames
    if timestamp is not None:
        frame["timestamp"] = timestamp
    return {"info": {"frames": [frame]}}


def _kill(ts, killer, assists, x, y, victim=1):
    return {
        "type": "CHAMPION_KILL",
        "victimId": victim,
        "killerId": killer,
        "assistingParticipantIds": assists,
        "timestamp": ts,
        "position": {"x": x, "y": y},
    }


class TestFullMatch:
    """Métricas calculadas sobre la partida sintética completa (ver factories.py)."""

    def test_top_laner(self):
        stats = enriched(1)
        assert stats.timeline_enriched is True
        assert (stats.gold_diff_14, stats.gold_diff_25, stats.xp_diff_8) == (-350, -625, -160)
        assert (stats.cs_14, stats.cs_diff_14) == (98, 14)
        assert stats.early_gank_deaths == 1
        assert stats.death_events == [
            {"x": 1500, "y": 9000, "time": 290, "assistingParticipantIds": [7]}
        ]
        assert (stats.quest_completed, stats.quest_completion_time) == (True, 690)
        assert (stats.enemy_quest_completion_time, stats.quest_completion_time_diff) == (740, -50)
        assert stats.fullclear_time is None
        assert stats.dragon_setups == []

    def test_jungler(self):
        stats = enriched(2)
        assert stats.fullclear_time == 300
        assert stats.dragon_setups == [
            {
                "dragon_time": 560,
                "dragon_type": "FIRE_DRAGON",
                "team_dragon": True,
                "in_prep_zone": True,
                "at_kill_zone": True,
                "secured_by_jg": True,
                "contested": False,
            }
        ]
        # WARD_PLACED sin posición: se usa la del participante en ese frame.
        assert stats.ward_events == [{"x": 7500, "y": 7500, "time": 170, "type": "YELLOW_TRINKET"}]
        assert stats.objective_vision_score == 0
        assert stats.quest_completion_time is None

    def test_mid_laner(self):
        stats = enriched(3)
        assert stats.solo_kills == 1
        assert stats.roaming_proactivity == 1
        assert [d["time"] for d in stats.death_events] == [1200]
        assert stats.early_gank_deaths == 0

    def test_support_objective_vision(self):
        assert enriched(5).objective_vision_score == 1


class TestEarlyGankDeaths:
    def test_mid_requires_helper_and_rival_laner(self):
        stats = blank_stats()
        timeline = _timeline(
            _kill(180_000, killer=3, assists=[], x=7500, y=7500),  # solo death
            _kill(300_000, killer=2, assists=[5], x=7500, y=7500),  # sin el mid rival
            _kill(420_000, killer=2, assists=[3], x=7500, y=7500),  # jungla + mid rival
        )
        enrich_with_timeline(stats, timeline, 1, enemy_ids=ENEMY_IDS, player_role="MID")
        assert stats.early_gank_deaths == 1

    def test_adc_requires_jungler_and_a_botlaner(self):
        stats = blank_stats()
        timeline = _timeline(
            _kill(180_000, killer=4, assists=[5], x=13000, y=2500),  # 2v2 de línea
            _kill(300_000, killer=2, assists=[], x=13500, y=2000),  # jungla solo
            _kill(420_000, killer=2, assists=[4], x=13500, y=2000),  # jungla + ADC rival
        )
        enrich_with_timeline(stats, timeline, 1, enemy_ids=ENEMY_IDS, player_role="ADC")
        assert stats.early_gank_deaths == 1

    def test_deaths_after_minute_ten_do_not_count(self):
        stats = blank_stats()
        timeline = _timeline(_kill(610_000, killer=2, assists=[3], x=7500, y=7500))
        enrich_with_timeline(stats, timeline, 1, enemy_ids=ENEMY_IDS, player_role="MID")
        assert stats.early_gank_deaths == 0


class TestObjectiveVisionScore:
    def test_counts_ward_near_dragon_when_kill_has_no_position(self):
        stats = blank_stats()
        timeline = _timeline(
            {"type": "WARD_PLACED", "creatorId": 1, "timestamp": 600_000,
             "position": {"x": 9800, "y": 4500}, "wardType": "YELLOW_TRINKET"},
            {"type": "ELITE_MONSTER_KILL", "monsterType": "DRAGON", "timestamp": 660_000},
        )
        enrich_with_timeline(stats, timeline, 1)
        assert stats.objective_vision_score == 1

    def test_counts_ward_near_baron_pit_anchor(self):
        stats = blank_stats()
        timeline = _timeline(
            {"type": "WARD_PLACED", "creatorId": 1, "timestamp": 1_200_000,
             "position": {"x": 5100, "y": 10400}, "wardType": "CONTROL_WARD"},
            {"type": "ELITE_MONSTER_KILL", "monsterType": "BARON_NASHOR", "timestamp": 1_260_000},
        )
        enrich_with_timeline(stats, timeline, 1)
        assert stats.objective_vision_score == 1

    def test_ignores_ward_outside_prep_window_or_radius(self):
        stats = blank_stats()
        timeline = _timeline(
            {"type": "WARD_PLACED", "creatorId": 1, "timestamp": 100_000,
             "position": {"x": 2000, "y": 2000}, "wardType": "YELLOW_TRINKET"},
            {"type": "WARD_PLACED", "creatorId": 1, "timestamp": 400_000,
             "position": {"x": 9800, "y": 4500}, "wardType": "YELLOW_TRINKET"},
            {"type": "ELITE_MONSTER_KILL", "monsterType": "DRAGON", "timestamp": 660_000},
        )
        enrich_with_timeline(stats, timeline, 1)
        assert stats.objective_vision_score == 0

    def test_helper(self):
        wards = [{"x": 9800, "y": 4500, "time": 600}]
        timeline = _timeline({"type": "ELITE_MONSTER_KILL", "monsterType": "DRAGON", "timestamp": 660_000})
        assert compute_objective_vision_score(wards, timeline=timeline) == 1
        assert compute_objective_vision_score([], timeline=timeline) == 0

    def test_ward_uses_participant_frame_when_event_has_no_position(self):
        stats = blank_stats()
        timeline = _timeline(
            {"type": "WARD_PLACED", "creatorId": 1, "timestamp": 600_000, "wardType": "SIGHT_WARD"},
            {"type": "ELITE_MONSTER_KILL", "monsterType": "DRAGON", "timestamp": 660_000},
            participant_frames={"1": {"position": {"x": 9800, "y": 4500}}},
            timestamp=600_000,
        )
        enrich_with_timeline(stats, timeline, 1)
        assert stats.ward_events[0]["x"] == 9800
        assert stats.objective_vision_score == 1


class TestDragonSetups:
    def _frame(self, ts, x, y, events=()):
        return {
            "timestamp": ts,
            "participantFrames": {"1": {"position": {"x": x, "y": y}}},
            "events": list(events),
        }

    def _dragon(self, killer=1, **extra):
        return {"type": "ELITE_MONSTER_KILL", "monsterType": "DRAGON", "timestamp": 570_000,
                "killerId": killer, "killerTeamId": 100, **extra}

    def test_setup_with_prep_presence(self):
        timeline = {"info": {"frames": [
            self._frame(480_000, 9800, 4500),
            self._frame(540_000, 9800, 4500),
            self._frame(600_000, 9800, 4500, [self._dragon(monsterSubType="FIRE_DRAGON")]),
        ]}}
        [setup] = extract_dragon_setups(timeline, participant_id=1, player_team_id=100)
        assert setup == {
            "dragon_time": 570, "dragon_type": "FIRE_DRAGON", "team_dragon": True,
            "in_prep_zone": True, "at_kill_zone": True, "secured_by_jg": True, "contested": False,
        }

    def test_missed_team_dragon(self):
        timeline = {"info": {"frames": [self._frame(540_000, 2000, 2000, [self._dragon(killer=2)])]}}
        [setup] = extract_dragon_setups(timeline, participant_id=1, player_team_id=100)
        assert (setup["team_dragon"], setup["in_prep_zone"], setup["secured_by_jg"]) == (True, False, False)

    def test_contested_when_a_fight_happens_at_the_pit(self):
        fight = {"type": "CHAMPION_KILL", "timestamp": 560_000, "position": {"x": 9900, "y": 4400}}
        timeline = {"info": {"frames": [self._frame(540_000, 9800, 4500, [fight, self._dragon()])]}}
        [setup] = extract_dragon_setups(timeline, participant_id=1, player_team_id=100)
        assert setup["contested"] is True

    def test_only_junglers_get_dragon_setups(self):
        timeline = {"info": {"frames": [self._frame(540_000, 9800, 4500, [self._dragon()])]}}
        jungle, top = blank_stats(), blank_stats()
        enrich_with_timeline(jungle, timeline, 1, player_role="JUNGLE", player_team_id=100)
        enrich_with_timeline(top, timeline, 1, player_role="TOP", player_team_id=100)
        assert len(jungle.dragon_setups) == 1
        assert top.dragon_setups == []


class TestFullclear:
    def test_first_frame_with_24_farm_or_level_4(self):
        timeline = {"info": {"frames": [
            {"timestamp": 0, "participantFrames": {"1": {"level": 3, "minionsKilled": 10, "jungleMinionsKilled": 5}}},
            {"timestamp": 60_000, "participantFrames": {"1": {"level": 3, "minionsKilled": 12, "jungleMinionsKilled": 8}}},
            {"timestamp": 120_000, "participantFrames": {"1": {"level": 4, "minionsKilled": 15, "jungleMinionsKilled": 10}}},
        ]}}
        stats = blank_stats()
        enrich_with_timeline(stats, timeline, 1, player_role="JUNGLE")
        assert stats.fullclear_time == 120
        assert stats.timeline_enriched is True
