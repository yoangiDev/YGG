"""Los datos del esquema antiguo sobreviven a la migración a match_participants.

Se crea una base de datos temporal, se lleva hasta la última revisión con el
esquema antiguo, se siembran datos con el bug P1 y se migra hasta head.
"""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.pool import NullPool

from app.core.config import settings

API_ROOT = Path(__file__).resolve().parents[1]
LEGACY_REVISION = "7b2e4c9d1a3f"

LEGACY_DATA = """
INSERT INTO users (id, email, username, hashed_password, role, is_active)
VALUES (1, 'legacy@example.com', 'legacy', 'x', 'user', true);

INSERT INTO players (id, user_id, puuid, game_name, tag_line, region, role) VALUES
    (1, 1, 'puuid-a', 'Alpha', 'EUW', 'euw', 'MID'),
    (2, 1, 'puuid-b', 'Bravo', 'EUW', 'euw', 'TOP');

INSERT INTO snapshots (id, player_id, date_from, date_to, description) VALUES
    (1, 1, '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z', 'A'),
    (2, 2, '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z', 'B');

INSERT INTO match_data (id, match_id, creation_time, champion, win, duration, kills, player_role,
                        timeline_enriched, role_bound_item, quest_completed, death_events, gold_diff_14) VALUES
    -- Compartida: la creó el snapshot de A y la reutilizó el de B (bug P1).
    (1, 'EUW1_1', '2026-01-10T10:00:00Z', 'Ahri', true, 1800, 7, 'MID', true, 0, false, '{}', 250),
    (2, 'EUW1_2', '2026-01-11T10:00:00Z', 'Garen', false, 1700, 2, 'TOP', true, 0, false,
        '[{"x": 1, "y": 2, "time": 300}]', NULL),
    -- Solo en historiales; la primera entrada es de A.
    (3, 'EUW1_3', '2026-01-12T10:00:00Z', 'Zed', true, 1600, 9, NULL, false, 0, false, NULL, 0),
    -- Huérfana.
    (4, 'EUW1_4', '2026-01-13T10:00:00Z', 'Lux', true, 1500, 1, 'SUPPORT', false, 0, false, NULL, 0);

INSERT INTO match_snapshots (id, snapshot_id, match_id) VALUES (1, 1, 1), (2, 2, 1), (3, 2, 2);
INSERT INTO player_match_history (id, player_id, match_id) VALUES (1, 1, 3), (2, 2, 3);
"""


@pytest.fixture
def migration_engine(monkeypatch):
    url = make_url(settings.database_url)
    name = f"ygg_migration_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool)
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))

    target_url = url.set(database=name).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", target_url)
    engine = create_engine(target_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _alembic() -> Config:
    config = Config()  # sin alembic.ini: no reconfigura el logging de pytest
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    return config


def _rows(engine, sql):
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text(sql))]


def test_legacy_data_survives_the_split(migration_engine):
    config = _alembic()
    command.upgrade(config, LEGACY_REVISION)
    with migration_engine.begin() as connection:
        connection.execute(text(LEGACY_DATA))

    command.upgrade(config, "head")

    assert _rows(migration_engine, "SELECT match_id, puuid, champion, kills, player_role FROM match_participants ORDER BY match_id") == [
        ("EUW1_1", "puuid-a", "Ahri", 7, "MID"),
        ("EUW1_2", "puuid-b", "Garen", 2, "TOP"),
        ("EUW1_3", "puuid-a", "Zed", 9, "UNKNOWN"),
    ]
    assert _rows(migration_engine, "SELECT death_events, gold_diff_14 FROM match_participants ORDER BY match_id") == [
        ([], 250),  # JSON legado {} → []
        ([{"x": 1, "y": 2, "time": 300}], 0),  # NULL → 0
        ([], 0),
    ]
    assert _rows(migration_engine, "SELECT match_id, duration FROM matches ORDER BY match_id") == [
        ("EUW1_1", 1800), ("EUW1_2", 1700), ("EUW1_3", 1600),
    ]
    assert _rows(migration_engine, """
        SELECT sp.snapshot_id, mp.match_id FROM snapshot_participants sp
        JOIN match_participants mp ON mp.id = sp.match_participant_id ORDER BY 1, 2
    """) == [(1, "EUW1_1"), (2, "EUW1_2")]
    assert _rows(migration_engine, """
        SELECT h.player_id, mp.match_id FROM player_history_entries h
        JOIN match_participants mp ON mp.id = h.match_participant_id
    """) == [(1, "EUW1_3")]
    # Los enlaces de B a estadísticas de A no se copian: quedan pendientes de recalcular.
    assert _rows(migration_engine, "SELECT kind, snapshot_id, player_id, match_id FROM legacy_unresolved_links ORDER BY kind") == [
        ("history", None, 2, "EUW1_3"),
        ("snapshot", 2, 2, "EUW1_1"),
    ]
    assert _rows(migration_engine, "SELECT to_regclass('match_data'), to_regclass('match_snapshots')") == [(None, None)]


def test_split_can_be_rolled_back(migration_engine):
    config = _alembic()
    command.upgrade(config, LEGACY_REVISION)
    with migration_engine.begin() as connection:
        connection.execute(text(LEGACY_DATA))
    command.upgrade(config, "head")

    command.downgrade(config, LEGACY_REVISION)

    assert _rows(migration_engine, "SELECT match_id, champion FROM match_data ORDER BY match_id") == [
        ("EUW1_1", "Ahri"), ("EUW1_2", "Garen"), ("EUW1_3", "Zed"),
    ]
    assert _rows(migration_engine, "SELECT count(*) FROM match_snapshots") == [(2,)]
    assert _rows(migration_engine, "SELECT count(*) FROM player_match_history") == [(1,)]
    assert _rows(migration_engine, "SELECT to_regclass('match_participants')") == [(None,)]
