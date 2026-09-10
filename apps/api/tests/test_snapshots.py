from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.schemas.dashboard import RadarChartData, RadarDataset, SnapshotDashboardResponse
from app.schemas.match import MatchResponse
from main import app

client = TestClient(app)


class TestSnapshotsAuth:
    def test_list_snapshots_requires_auth(self):
        response = client.get("/snapshots/player/1")
        assert response.status_code == 403

    def test_get_snapshot_requires_auth(self):
        response = client.get("/snapshots/99999")
        assert response.status_code == 403

    def test_job_status_requires_auth(self):
        response = client.get("/snapshots/jobs/some-job-id")
        assert response.status_code == 403


class TestSnapshotsCRUD:
    def test_get_snapshot_not_found(self, auth_headers):
        response = client.get("/snapshots/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_list_snapshots_player_not_found(self, auth_headers):
        response = client.get("/snapshots/player/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_job_not_found(self, auth_headers):
        response = client.get("/snapshots/jobs/nonexistent-job-id", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_snapshot_not_found(self, auth_headers):
        response = client.delete("/snapshots/99999", headers=auth_headers)
        assert response.status_code == 404


class TestDeathsByPhaseSchema:
    def test_match_response_deaths_by_phase(self):
        # Crear un MatchResponse mock con eventos de muerte
        # min 1-8: time < 480
        # min 8-14: 480 <= time < 840
        # min 14+: time >= 840
        death_events = [
            {"time": 100, "x": 1000, "y": 1000},  # early
            {"time": 479, "x": 1000, "y": 1000},  # early
            {"time": 480, "x": 1000, "y": 1000},  # mid
            {"time": 800, "x": 1000, "y": 1000},  # mid
            {"time": 840, "x": 1000, "y": 1000},  # late
            {"time": 1200, "x": 1000, "y": 1000}, # late
        ]
        match = MatchResponse(
            match_id="EUW_123",
            creation_time=datetime.now(),
            champion="Garen",
            win=True,
            duration=1500,
            kills=5,
            deaths=6,
            assists=5,
            kill_participation=50.0,
            vision=20,
            damage=15000,
            gold=10000,
            total_cs=150,
            damage_share=25.0,
            first_dragon=True,
            void_grubs=False,
            herald=True,
            death_events=death_events
        )
        assert match.deaths_by_phase == {
            "early_deaths": 2,
            "mid_deaths": 2,
            "late_deaths": 2
        }

    def test_snapshot_dashboard_response_deaths_by_phase(self):
        # Crear dos matches con muertes
        match1 = MatchResponse(
            match_id="EUW_1", champion="Garen", win=True, duration=1000, kills=0, deaths=2, assists=0,
            kill_participation=0.0, vision=0, damage=0, gold=0, total_cs=0, damage_share=0.0,
            first_dragon=False, void_grubs=False, herald=False, creation_time=datetime.now(),
            death_events=[{"time": 300}, {"time": 600}] # 1 early, 1 mid
        )
        match2 = MatchResponse(
            match_id="EUW_2", champion="Teemo", win=False, duration=2000, kills=0, deaths=3, assists=0,
            kill_participation=0.0, vision=0, damage=0, gold=0, total_cs=0, damage_share=0.0,
            first_dragon=False, void_grubs=False, herald=False, creation_time=datetime.now(),
            death_events=[{"time": 1000}, {"time": 1200}, {"time": 200}] # 1 early, 2 late
        )
        
        radar_data = RadarChartData(
            axes=[],
            player_dataset=RadarDataset(label="", values={}, normalized_values={}),
            rank_datasets={},
            pro_datasets={}
        )
        
        dashboard = SnapshotDashboardResponse(
            snapshot_id=1,
            player_id=1,
            player_name="Test#EUW",
            date_from=datetime.now(),
            date_to=datetime.now(),
            description="Test Description",
            notes="Some Notes",
            active_role="MID",
            role_averages=[],
            played_champions=[],
            matches=[match1, match2],
            radar_data=radar_data
        )
        
        assert dashboard.deaths_by_phase == {
            "early_deaths": 2,
            "mid_deaths": 1,
            "late_deaths": 2
        }

    def test_match_response_coordinates_normalization(self):
        death_events = [
            {"time": 100, "x": 0, "y": 0},      # Bottom-left in game -> (0, 1) in normalized screen
            {"time": 200, "x": 15000, "y": 15000},  # Top-right in game -> (1, 0) in normalized screen
            {"time": 300, "x": 7500, "y": 7500},   # Middle in game -> (0.5, 0.5) in normalized screen
        ]
        ward_events = [
            {"time": 50, "x": 3000, "y": 12000, "type": "yellow"},
        ]
        match = MatchResponse(
            match_id="EUW_SCALE", creation_time=datetime.now(), champion="Lux", win=True, duration=1500,
            kills=5, deaths=6, assists=5, kill_participation=50.0, vision=20, damage=15000, gold=10000,
            total_cs=150, damage_share=25.0, first_dragon=True, void_grubs=False, herald=True,
            death_events=death_events, ward_events=ward_events
        )
        # Verify normalized death positions
        deaths = match.death_events_normalized
        assert len(deaths) == 3
        assert deaths[0]["norm_x"] == 0.0
        assert deaths[0]["norm_y"] == 1.0
        assert deaths[1]["norm_x"] == 1.0
        assert deaths[1]["norm_y"] == 0.0
        assert deaths[2]["norm_x"] == 0.5
        assert deaths[2]["norm_y"] == 0.5

        # Verify normalized ward positions
        wards = match.ward_events_normalized
        assert len(wards) == 1
        assert wards[0]["norm_x"] == 0.2
        assert wards[0]["norm_y"] == 0.2

    def test_snapshot_dashboard_response_performance_trends(self):
        from datetime import timedelta
        base_time = datetime.now()
        
        # Partida 1 (KDA=2, CS/Min=6, Gold/Min=400)
        match1 = MatchResponse(
            match_id="EUW_T1", champion="Ezreal", win=True, duration=1000, kills=2, deaths=2, assists=2,
            kill_participation=0.0, vision=0, damage=0, gold=6667, total_cs=100, damage_share=0.0,
            first_dragon=False, void_grubs=False, herald=False, creation_time=base_time - timedelta(days=2),
            death_events=[], ward_events=[]
        )
        # Partida 2 (KDA=4, CS/Min=8, Gold/Min=500)
        match2 = MatchResponse(
            match_id="EUW_T2", champion="Ezreal", win=False, duration=1000, kills=4, deaths=2, assists=4,
            kill_participation=0.0, vision=0, damage=0, gold=8333, total_cs=133, damage_share=0.0,
            first_dragon=False, void_grubs=False, herald=False, creation_time=base_time - timedelta(days=1),
            death_events=[], ward_events=[]
        )
        
        radar_data = RadarChartData(
            axes=[], player_dataset=RadarDataset(label="", values={}, normalized_values={}),
            rank_datasets={}, pro_datasets={}
        )
        dashboard = SnapshotDashboardResponse(
            snapshot_id=1, player_id=1, player_name="Test#EUW", date_from=datetime.now(),
            date_to=datetime.now(), description="Test", notes="", active_role="ADC",
            role_averages=[], played_champions=[], matches=[match2, match1], # Al revés para probar ordenación cronológica
            radar_data=radar_data
        )
        
        trends = dashboard.performance_trends
        assert len(trends) == 2
        # El primero cronológicamente debe ser match1
        assert trends[0].match_id == "EUW_T1"
        assert trends[0].game_num == 1
        assert trends[0].kda == 2.0
        assert trends[0].kda_moving_avg == 2.0
        
        # El segundo cronológicamente debe ser match2
        assert trends[1].match_id == "EUW_T2"
        assert trends[1].game_num == 2
        assert trends[1].kda == 4.0
        # Media móvil entre 1 y 2: (2 + 4) / 2 = 3
        assert trends[1].kda_moving_avg == 3.0


class TestEarlyGankDeaths:
    def test_early_gank_deaths_parsing_mid(self):
        from app.service.riot_client import RiotAPIClient
        from app.db.models.match import Match
        from datetime import datetime

        client = RiotAPIClient()
        match = Match(
            match_id="TEST_GANK_MID",
            creation_time=datetime.now(),
            champion="Ahri",
            win=True,
            duration=1200,
        )

        # Mock timeline:
        # Event 1: At 3 min, death in MID lane, only MID (ID 3) participates (solo death, not a gank).
        # Event 2: At 5 min, death in MID lane, Jungler (ID 2) and Support (ID 5) participate, but rival MID doesn't (no rival laner, e.g. executed or caught by other lanes).
        # Event 3: At 7 min, death in MID lane, Jungler (ID 2) and rival MID (ID 3) participate (both helper and rival laner!).
        timeline = {
            "info": {
                "frames": [
                    {
                        "events": [
                            {
                                "type": "CHAMPION_KILL",
                                "victimId": 1,
                                "killerId": 3,  # rival MID
                                "assistingParticipantIds": [],  # solo death
                                "timestamp": 180000,
                                "position": {"x": 7500, "y": 7500}  # MID lane
                            },
                            {
                                "type": "CHAMPION_KILL",
                                "victimId": 1,
                                "killerId": 2,  # Jungler
                                "assistingParticipantIds": [5],  # Support (no rival MID)
                                "timestamp": 300000,
                                "position": {"x": 7500, "y": 7500}  # MID lane
                            },
                            {
                                "type": "CHAMPION_KILL",
                                "victimId": 1,
                                "killerId": 2,  # Jungler
                                "assistingParticipantIds": [3],  # rival MID
                                "timestamp": 420000,
                                "position": {"x": 7500, "y": 7500}  # MID lane
                            }
                        ]
                    }
                ]
            }
        }

        enemy_ids = {
            "TOP": 6,
            "JUNGLE": 2,
            "MID": 3,
            "ADC": 4,
            "SUPPORT": 5,
        }

        # Call with player role as MID and our enemy_ids dict
        client._enrich_with_timeline(
            match,
            timeline,
            participant_id=1,
            enemy_ids=enemy_ids,
            player_role="MID"
        )

        # Only Event 3 should count because it involves both helper (JG) and rival MID!
        assert match.early_gank_deaths == 1

    def test_early_gank_deaths_parsing_adc(self):
        from app.service.riot_client import RiotAPIClient
        from app.db.models.match import Match
        from datetime import datetime

        client = RiotAPIClient()
        match = Match(
            match_id="TEST_GANK_ADC",
            creation_time=datetime.now(),
            champion="Ezreal",
            win=True,
            duration=1200,
        )

        # Mock timeline:
        # Event 1: At 3 min, death in BOT lane, only Support (ID 5) and enemy ADC (ID 4) participate (2v2 lane kill, not a JG gank).
        # Event 2: At 5 min, death in BOT lane, only Jungler (ID 2) participates without any botlaner (no double participation).
        # Event 3: At 7 min, death in BOT lane, Jungler (ID 2) and enemy ADC (ID 4) participate (JG gank + botlaner!).
        timeline = {
            "info": {
                "frames": [
                    {
                        "events": [
                            {
                                "type": "CHAMPION_KILL",
                                "victimId": 1,
                                "killerId": 4,  # Enemy ADC
                                "assistingParticipantIds": [5],  # Support
                                "timestamp": 180000,
                                "position": {"x": 13000, "y": 2500}  # BOT lane
                            },
                            {
                                "type": "CHAMPION_KILL",
                                "victimId": 1,
                                "killerId": 2,  # Jungler (alone)
                                "assistingParticipantIds": [],
                                "timestamp": 300000,
                                "position": {"x": 13500, "y": 2000}  # BOT lane
                            },
                            {
                                "type": "CHAMPION_KILL",
                                "victimId": 1,
                                "killerId": 2,  # Jungler
                                "assistingParticipantIds": [4],  # Enemy ADC
                                "timestamp": 420000,
                                "position": {"x": 13500, "y": 2000}  # BOT lane
                            }
                        ]
                    }
                ]
            }
        }

        enemy_ids = {
            "TOP": 6,
            "JUNGLE": 2,
            "MID": 3,
            "ADC": 4,
            "SUPPORT": 5,
        }

        # Call with player role as ADC and our enemy_ids dict
        client._enrich_with_timeline(
            match,
            timeline,
            participant_id=1,
            enemy_ids=enemy_ids,
            player_role="ADC"
        )

        # Should only count the gank where Jungler participated along with a rival botlaner (Event 3).
        assert match.early_gank_deaths == 1


class TestObjectiveVisionScore:
    def test_counts_ward_near_dragon_when_kill_has_no_position(self):
        from app.service.riot_client import RiotAPIClient
        from app.db.models.match import Match
        from datetime import datetime

        client = RiotAPIClient()
        match = Match(
            match_id="TEST_OBJ_VISION_DRAGON",
            creation_time=datetime.now(),
            champion="Thresh",
            win=True,
            duration=1800,
        )

        timeline = {
            "info": {
                "frames": [
                    {
                        "events": [
                            {
                                "type": "WARD_PLACED",
                                "creatorId": 1,
                                "timestamp": 600_000,
                                "position": {"x": 9800, "y": 4500},
                                "wardType": "YELLOW_TRINKET",
                            },
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "DRAGON",
                                "timestamp": 660_000,
                            },
                        ]
                    }
                ]
            }
        }

        client._enrich_with_timeline(match, timeline, participant_id=1)
        assert match.objective_vision_score == 1

    def test_counts_ward_near_baron_pit_anchor(self):
        from app.service.riot_client import RiotAPIClient
        from app.db.models.match import Match
        from datetime import datetime

        client = RiotAPIClient()
        match = Match(
            match_id="TEST_OBJ_VISION_BARON",
            creation_time=datetime.now(),
            champion="Thresh",
            win=True,
            duration=1800,
        )

        timeline = {
            "info": {
                "frames": [
                    {
                        "events": [
                            {
                                "type": "WARD_PLACED",
                                "creatorId": 1,
                                "timestamp": 1_200_000,
                                "position": {"x": 5100, "y": 10400},
                                "wardType": "CONTROL_WARD",
                            },
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "BARON_NASHOR",
                                "timestamp": 1_260_000,
                            },
                        ]
                    }
                ]
            }
        }

        client._enrich_with_timeline(match, timeline, participant_id=1)
        assert match.objective_vision_score == 1

    def test_ignores_ward_outside_prep_window_or_radius(self):
        from app.service.riot_client import RiotAPIClient
        from app.db.models.match import Match
        from datetime import datetime

        client = RiotAPIClient()
        match = Match(
            match_id="TEST_OBJ_VISION_MISS",
            creation_time=datetime.now(),
            champion="Thresh",
            win=True,
            duration=1800,
        )

        timeline = {
            "info": {
                "frames": [
                    {
                        "events": [
                            {
                                "type": "WARD_PLACED",
                                "creatorId": 1,
                                "timestamp": 100_000,
                                "position": {"x": 2000, "y": 2000},
                                "wardType": "YELLOW_TRINKET",
                            },
                            {
                                "type": "WARD_PLACED",
                                "creatorId": 1,
                                "timestamp": 400_000,
                                "position": {"x": 9800, "y": 4500},
                                "wardType": "YELLOW_TRINKET",
                            },
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "DRAGON",
                                "timestamp": 660_000,
                            },
                        ]
                    }
                ]
            }
        }

        client._enrich_with_timeline(match, timeline, participant_id=1)
        assert match.objective_vision_score == 0

    def test_compute_objective_vision_score_helper(self):
        from app.service.riot_client import compute_objective_vision_score

        wards = [{"x": 9800, "y": 4500, "time": 600}]
        timeline = {
            "info": {
                "frames": [{
                    "events": [{
                        "type": "ELITE_MONSTER_KILL",
                        "monsterType": "DRAGON",
                        "timestamp": 660_000,
                    }]
                }]
            }
        }
        assert compute_objective_vision_score(wards, timeline=timeline) == 1
        assert compute_objective_vision_score([], timeline=timeline) == 0

    def test_ward_events_use_participant_frame_when_event_has_no_position(self):
        from app.service.riot_client import RiotAPIClient
        from app.db.models.match import Match
        from datetime import datetime

        client = RiotAPIClient()
        match = Match(
            match_id="TEST_WARD_FRAME_FALLBACK",
            creation_time=datetime.now(),
            champion="Thresh",
            win=True,
            duration=1800,
        )

        timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 600_000,
                        "participantFrames": {
                            "1": {"position": {"x": 9800, "y": 4500}},
                        },
                        "events": [
                            {
                                "type": "WARD_PLACED",
                                "creatorId": 1,
                                "timestamp": 600_000,
                                "wardType": "SIGHT_WARD",
                            },
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "DRAGON",
                                "timestamp": 660_000,
                            },
                        ],
                    }
                ]
            }
        }

        client._enrich_with_timeline(match, timeline, participant_id=1)
        assert len(match.ward_events) == 1
        assert match.ward_events[0]["x"] == 9800
        assert match.objective_vision_score == 1


class TestDragonSetups:
    def test_extracts_dragon_setup_with_prep_presence(self):
        from app.service.riot_client import extract_dragon_setups

        timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 480_000,
                        "participantFrames": {
                            "1": {"position": {"x": 9800, "y": 4500}},
                        },
                        "events": [],
                    },
                    {
                        "timestamp": 540_000,
                        "participantFrames": {
                            "1": {"position": {"x": 9800, "y": 4500}},
                        },
                        "events": [],
                    },
                    {
                        "timestamp": 600_000,
                        "participantFrames": {
                            "1": {"position": {"x": 9800, "y": 4500}},
                        },
                        "events": [
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "DRAGON",
                                "monsterSubType": "FIRE_DRAGON",
                                "timestamp": 570_000,
                                "killerId": 1,
                                "killerTeamId": 100,
                            }
                        ],
                    },
                ]
            }
        }

        setups = extract_dragon_setups(timeline, participant_id=1, player_team_id=100)
        assert len(setups) == 1
        assert setups[0]["dragon_time"] == 570
        assert setups[0]["dragon_type"] == "FIRE_DRAGON"
        assert setups[0]["team_dragon"] is True
        assert setups[0]["in_prep_zone"] is True
        assert setups[0]["at_kill_zone"] is True
        assert setups[0]["secured_by_jg"] is True
        assert setups[0]["contested"] is False

    def test_missed_team_dragon_setup(self):
        from app.service.riot_client import extract_dragon_setups

        timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 540_000,
                        "participantFrames": {
                            "1": {"position": {"x": 2000, "y": 2000}},
                        },
                        "events": [
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "DRAGON",
                                "timestamp": 570_000,
                                "killerId": 2,
                                "killerTeamId": 100,
                            }
                        ],
                    }
                ]
            }
        }

        setups = extract_dragon_setups(timeline, participant_id=1, player_team_id=100)
        assert setups[0]["team_dragon"] is True
        assert setups[0]["in_prep_zone"] is False
        assert setups[0]["secured_by_jg"] is False

    def test_contested_dragon_detects_nearby_kill(self):
        from app.service.riot_client import extract_dragon_setups

        timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 540_000,
                        "participantFrames": {
                            "1": {"position": {"x": 9800, "y": 4500}},
                        },
                        "events": [
                            {
                                "type": "CHAMPION_KILL",
                                "timestamp": 560_000,
                                "position": {"x": 9900, "y": 4400},
                            },
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "DRAGON",
                                "timestamp": 570_000,
                                "killerId": 1,
                                "killerTeamId": 100,
                            },
                        ],
                    }
                ]
            }
        }

        setups = extract_dragon_setups(timeline, participant_id=1, player_team_id=100)
        assert setups[0]["contested"] is True

    def test_enrich_sets_dragon_setups_for_jungle_only(self):
        from app.service.riot_client import RiotAPIClient
        from app.db.models.match import Match
        from datetime import datetime

        client = RiotAPIClient()
        match = Match(
            match_id="TEST_DRAGON_SETUP",
            creation_time=datetime.now(),
            champion="LeeSin",
            win=True,
            duration=1800,
        )

        timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 540_000,
                        "participantFrames": {
                            "1": {"position": {"x": 9800, "y": 4500}},
                        },
                        "events": [
                            {
                                "type": "ELITE_MONSTER_KILL",
                                "monsterType": "DRAGON",
                                "timestamp": 570_000,
                                "killerId": 1,
                                "killerTeamId": 100,
                            }
                        ],
                    }
                ]
            }
        }

        client._enrich_with_timeline(
            match, timeline, participant_id=1, player_role="JUNGLE", player_team_id=100
        )
        assert len(match.dragon_setups) == 1
        assert match.dragon_setups[0]["in_prep_zone"] is True

        match2 = Match(
            match_id="TEST_DRAGON_SETUP_TOP",
            creation_time=datetime.now(),
            champion="Gnar",
            win=True,
            duration=1800,
        )
        client._enrich_with_timeline(
            match2, timeline, participant_id=1, player_role="TOP", player_team_id=100
        )
        assert match2.dragon_setups == []

    def test_dragon_setups_summary(self):
        from app.schemas.match import MatchResponse
        from datetime import datetime

        match = MatchResponse(
            match_id="EUW1_TEST",
            creation_time=datetime.now(),
            champion="LeeSin",
            win=True,
            duration=1500,
            kills=2,
            deaths=1,
            assists=5,
            kill_participation=50.0,
            vision=20,
            damage=10000,
            gold=9000,
            total_cs=120,
            damage_share=20.0,
            first_dragon=True,
            void_grubs=False,
            herald=False,
            dragon_setups=[
                {
                    "dragon_time": 900,
                    "team_dragon": True,
                    "in_prep_zone": True,
                    "at_kill_zone": True,
                    "secured_by_jg": True,
                    "contested": False,
                },
                {
                    "dragon_time": 1200,
                    "team_dragon": True,
                    "in_prep_zone": False,
                    "at_kill_zone": False,
                    "secured_by_jg": False,
                    "contested": True,
                },
            ],
        )
        summary = match.dragon_setups_summary
        assert summary["team_dragons"] == 2
        assert summary["setup_rate"] == 50.0
        assert summary["presence_at_kill_rate"] == 50.0
        assert summary["secure_rate"] == 50.0
