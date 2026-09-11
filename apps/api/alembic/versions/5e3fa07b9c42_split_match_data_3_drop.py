"""Partir match_data (3/3): verificar conteos y borrar el esquema antiguo

Antes de borrar comprueba que cada enlace antiguo acabó copiado o registrado
como no resuelto, y que cada fila enlazada tiene su participante. Si algo no
cuadra la migración aborta y `match_data` sigue intacta.

El downgrade reconstruye las tablas antiguas con una fila por partida (el
esquema viejo no puede representar varios participantes) y pierde los enlaces
no resueltos.

Revision ID: 5e3fa07b9c42
Revises: 4d2e9f6a8b31
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5e3fa07b9c42"
down_revision: Union[str, None] = "4d2e9f6a8b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (descripción, conteo en el esquema antiguo, conteo en el nuevo)
CHECKS = (
    (
        "enlaces de snapshot",
        "SELECT count(*) FROM match_snapshots",
        "SELECT (SELECT count(*) FROM snapshot_participants)"
        " + (SELECT count(*) FROM legacy_unresolved_links WHERE kind = 'snapshot')",
    ),
    (
        "enlaces de historial",
        "SELECT count(*) FROM player_match_history",
        "SELECT (SELECT count(*) FROM player_history_entries)"
        " + (SELECT count(*) FROM legacy_unresolved_links WHERE kind = 'history')",
    ),
    (
        "filas enlazadas → participantes",
        "SELECT count(*) FROM match_data md WHERE"
        " EXISTS (SELECT 1 FROM match_snapshots ms WHERE ms.match_id = md.id)"
        " OR EXISTS (SELECT 1 FROM player_match_history h WHERE h.match_id = md.id)",
        "SELECT count(*) FROM match_participants",
    ),
    (
        "partidas",
        "SELECT count(DISTINCT match_id) FROM match_participants",
        "SELECT count(*) FROM matches",
    ),
)

INT_COLUMNS = (
    "kills", "deaths", "assists", "vision", "damage", "gold", "total_cs",
    "summoner1_id", "summoner2_id",
    "item0", "item1", "item2", "item3", "item4", "item5", "item6",
    "primary_rune", "secondary_tree",
    "solo_kills", "damage_structures", "enemy_jg_monsters", "control_wards",
    "roaming_proactivity", "objective_vision_score", "early_gank_deaths",
    "cs_8", "cs_14", "cs_25", "cs_diff_8", "cs_diff_14", "cs_diff_25",
    "gold_diff_8", "gold_diff_14", "gold_diff_25", "xp_diff_8", "xp_diff_14",
)
FLOAT_COLUMNS = ("kill_participation", "damage_share", "gold_share")
BOOL_COLUMNS = ("first_dragon", "void_grubs", "herald")
JSON_COLUMNS = ("death_events", "ward_events", "dragon_setups")
NULLABLE_INT_COLUMNS = (
    "fullclear_time", "quest_completion_time", "enemy_quest_completion_time", "quest_completion_time_diff",
)


def verify_counts(bind: sa.engine.Connection) -> list[str]:
    problems = []
    for description, old_sql, new_sql in CHECKS:
        old = bind.execute(sa.text(old_sql)).scalar_one()
        new = bind.execute(sa.text(new_sql)).scalar_one()
        if old != new:
            problems.append(f"{description}: {old} ≠ {new}")
    return problems


def upgrade() -> None:
    problems = verify_counts(op.get_bind())
    if problems:
        raise RuntimeError(
            "La verificación de la migración ha fallado; match_data no se borra: " + "; ".join(problems)
        )
    op.drop_table("match_snapshots")
    op.drop_table("player_match_history")
    op.drop_table("match_data")


def downgrade() -> None:
    op.create_table(
        "match_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.String(length=50), nullable=False),
        sa.Column("creation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("champion", sa.String(length=50), nullable=False),
        sa.Column("win", sa.Boolean(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=True) for name in INT_COLUMNS],
        *[sa.Column(name, sa.Float(), nullable=True) for name in FLOAT_COLUMNS],
        *[sa.Column(name, sa.Boolean(), nullable=True) for name in BOOL_COLUMNS],
        *[sa.Column(name, sa.JSON(), nullable=True) for name in JSON_COLUMNS],
        sa.Column("timeline_enriched", sa.Boolean(), nullable=False),
        sa.Column("player_role", sa.String(length=20), nullable=True),
        sa.Column("role_bound_item", sa.Integer(), nullable=False),
        sa.Column("quest_completed", sa.Boolean(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=True) for name in NULLABLE_INT_COLUMNS],
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_match_data_id"), "match_data", ["id"], unique=False)
    op.create_index(op.f("ix_match_data_match_id"), "match_data", ["match_id"], unique=True)

    op.create_table(
        "player_match_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["match_data.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "match_id", name="uq_player_match_history"),
    )
    op.create_index(op.f("ix_player_match_history_id"), "player_match_history", ["id"], unique=False)
    op.create_index(op.f("ix_player_match_history_player_id"), "player_match_history", ["player_id"], unique=False)

    op.create_table(
        "match_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["match_data.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "match_id", name="uq_snapshot_match"),
    )
    op.create_index(op.f("ix_match_snapshots_id"), "match_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_match_snapshots_match_id"), "match_snapshots", ["match_id"], unique=False)
    op.create_index(op.f("ix_match_snapshots_snapshot_id"), "match_snapshots", ["snapshot_id"], unique=False)

    copied = [*INT_COLUMNS, *FLOAT_COLUMNS, *BOOL_COLUMNS, "timeline_enriched", "role_bound_item",
              "quest_completed", *NULLABLE_INT_COLUMNS]
    json_select = [f"mp.{name}::json" for name in JSON_COLUMNS]
    op.execute(
        f"""
        INSERT INTO match_data (match_id, creation_time, champion, win, duration, player_role,
                                {', '.join(copied)}, {', '.join(JSON_COLUMNS)})
        SELECT DISTINCT ON (mp.match_id)
               mp.match_id, m.creation_time, mp.champion, mp.win, m.duration,
               NULLIF(mp.player_role, 'UNKNOWN'),
               {', '.join('mp.' + name for name in copied)}, {', '.join(json_select)}
        FROM match_participants mp
        JOIN matches m ON m.match_id = mp.match_id
        ORDER BY mp.match_id, mp.id
        """
    )
    op.execute(
        """
        INSERT INTO match_snapshots (snapshot_id, match_id)
        SELECT DISTINCT sp.snapshot_id, md.id
        FROM snapshot_participants sp
        JOIN match_participants mp ON mp.id = sp.match_participant_id
        JOIN match_data md ON md.match_id = mp.match_id
        """
    )
    op.execute(
        """
        INSERT INTO player_match_history (player_id, match_id)
        SELECT DISTINCT h.player_id, md.id
        FROM player_history_entries h
        JOIN match_participants mp ON mp.id = h.match_participant_id
        JOIN match_data md ON md.match_id = mp.match_id
        """
    )
