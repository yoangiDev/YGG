"""Partir match_data (2/3): copiar los datos

Cada fila de `match_data` se atribuye a un único jugador: el del primer enlace
que la creó (snapshots antes que historial; dentro de cada uno, el id de enlace
más bajo). Es el jugador cuyo análisis insertó la fila; los análisis de otros
jugadores la reutilizaron con estadísticas ajenas (bug P1).

- Los enlaces del dueño se copian a snapshot_participants / player_history_entries.
- Los enlaces de otros jugadores NO se copian (apuntarían a datos incorrectos):
  quedan en legacy_unresolved_links para recalcularlos con la Riot API.
- Las filas sin ningún enlace (huérfanas) no se copian.
- JSON legado `{}` o NULL pasa a `[]` y los NULL numéricos, a 0.

Revision ID: 4d2e9f6a8b31
Revises: 3c1d8e5f7a20
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4d2e9f6a8b31"
down_revision: Union[str, None] = "3c1d8e5f7a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columnas que existían en match_data (participant_id y team_id no).
INT_COLUMNS = (
    "kills", "deaths", "assists", "vision", "damage", "gold", "total_cs",
    "summoner1_id", "summoner2_id",
    "item0", "item1", "item2", "item3", "item4", "item5", "item6",
    "primary_rune", "secondary_tree",
    "solo_kills", "damage_structures", "enemy_jg_monsters", "control_wards",
    "roaming_proactivity", "objective_vision_score", "early_gank_deaths",
    "cs_8", "cs_14", "cs_25", "cs_diff_8", "cs_diff_14", "cs_diff_25",
    "gold_diff_8", "gold_diff_14", "gold_diff_25", "xp_diff_8", "xp_diff_14",
    "role_bound_item",
)
FLOAT_COLUMNS = ("kill_participation", "damage_share", "gold_share")
BOOL_COLUMNS = ("first_dragon", "void_grubs", "herald", "timeline_enriched", "quest_completed")
NULLABLE_INT_COLUMNS = (
    "fullclear_time", "quest_completion_time", "enemy_quest_completion_time", "quest_completion_time_diff",
)
JSON_COLUMNS = ("death_events", "ward_events", "dragon_setups")

LINKS_CTE = """
WITH links AS (
    SELECT ms.match_id AS row_id, p.puuid, 0 AS source, ms.id AS link_id
    FROM match_snapshots ms
    JOIN snapshots s ON s.id = ms.snapshot_id
    JOIN players p ON p.id = s.player_id
    UNION ALL
    SELECT h.match_id, p.puuid, 1, h.id
    FROM player_match_history h
    JOIN players p ON p.id = h.player_id
),
owners AS (
    SELECT DISTINCT ON (row_id) row_id, puuid
    FROM links
    ORDER BY row_id, source, link_id
)
"""


def _copy_participants_sql() -> str:
    target = ["match_id", "puuid", "creation_time", "player_role", "champion", "win"]
    source = ["md.match_id", "o.puuid", "md.creation_time", "COALESCE(md.player_role, 'UNKNOWN')", "md.champion", "md.win"]
    for name in INT_COLUMNS:
        target.append(name)
        source.append(f"COALESCE(md.{name}, 0)")
    for name in FLOAT_COLUMNS:
        target.append(name)
        source.append(f"COALESCE(md.{name}, 0)")
    for name in BOOL_COLUMNS:
        target.append(name)
        source.append(f"COALESCE(md.{name}, false)")
    for name in NULLABLE_INT_COLUMNS:
        target.append(name)
        source.append(f"md.{name}")
    for name in JSON_COLUMNS:
        target.append(name)
        source.append(
            f"CASE WHEN jsonb_typeof(md.{name}::jsonb) = 'array' THEN md.{name}::jsonb ELSE '[]'::jsonb END"
        )
    return (
        LINKS_CTE
        + f"INSERT INTO match_participants ({', '.join(target)})\n"
        + f"SELECT {', '.join(source)}\n"
        + "FROM match_data md JOIN owners o ON o.row_id = md.id"
    )


def upgrade() -> None:
    op.execute(
        LINKS_CTE
        + """
        INSERT INTO matches (match_id, creation_time, duration)
        SELECT md.match_id, md.creation_time, md.duration
        FROM match_data md JOIN owners o ON o.row_id = md.id
        """
    )
    op.execute(_copy_participants_sql())

    op.execute(
        """
        INSERT INTO snapshot_participants (snapshot_id, match_participant_id)
        SELECT ms.snapshot_id, mp.id
        FROM match_snapshots ms
        JOIN snapshots s ON s.id = ms.snapshot_id
        JOIN players p ON p.id = s.player_id
        JOIN match_data md ON md.id = ms.match_id
        JOIN match_participants mp ON mp.match_id = md.match_id AND mp.puuid = p.puuid
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO legacy_unresolved_links (kind, snapshot_id, player_id, match_id)
        SELECT 'snapshot', ms.snapshot_id, s.player_id, md.match_id
        FROM match_snapshots ms
        JOIN snapshots s ON s.id = ms.snapshot_id
        JOIN players p ON p.id = s.player_id
        JOIN match_data md ON md.id = ms.match_id
        WHERE NOT EXISTS (
            SELECT 1 FROM match_participants mp WHERE mp.match_id = md.match_id AND mp.puuid = p.puuid
        )
        """
    )

    op.execute(
        """
        INSERT INTO player_history_entries (player_id, match_participant_id)
        SELECT h.player_id, mp.id
        FROM player_match_history h
        JOIN players p ON p.id = h.player_id
        JOIN match_data md ON md.id = h.match_id
        JOIN match_participants mp ON mp.match_id = md.match_id AND mp.puuid = p.puuid
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO legacy_unresolved_links (kind, snapshot_id, player_id, match_id)
        SELECT 'history', NULL, h.player_id, md.match_id
        FROM player_match_history h
        JOIN players p ON p.id = h.player_id
        JOIN match_data md ON md.id = h.match_id
        WHERE NOT EXISTS (
            SELECT 1 FROM match_participants mp WHERE mp.match_id = md.match_id AND mp.puuid = p.puuid
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM legacy_unresolved_links")
    op.execute("DELETE FROM player_history_entries")
    op.execute("DELETE FROM snapshot_participants")
    op.execute("DELETE FROM match_participants")
    op.execute("DELETE FROM matches")
