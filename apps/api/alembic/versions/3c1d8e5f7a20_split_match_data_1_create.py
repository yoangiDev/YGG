"""Partir match_data (1/3): crear las tablas nuevas

`match_data` guardaba las estadísticas de UN participante con `match_id`
único, así que dos jugadores registrados en la misma partida compartían fila
(bug P1). El modelo nuevo separa la partida (`matches`) del participante
(`match_participants`, único por (match_id, puuid)); snapshots e historial
enlazan participantes, no partidas:

    match_snapshots       → snapshot_participants
    player_match_history  → player_history_entries

Paso 2 copia los datos y paso 3 verifica los conteos y borra lo antiguo.

Revision ID: 3c1d8e5f7a20
Revises: 7b2e4c9d1a3f
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3c1d8e5f7a20"
down_revision: Union[str, None] = "7b2e4c9d1a3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INT_COLUMNS = (
    "participant_id", "team_id",
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


def _stat_columns() -> list[sa.Column]:
    columns = [sa.Column(name, sa.Integer(), server_default=sa.text("0"), nullable=False) for name in INT_COLUMNS]
    columns += [sa.Column(name, sa.Float(), server_default=sa.text("0"), nullable=False) for name in FLOAT_COLUMNS]
    columns += [sa.Column(name, sa.Boolean(), server_default=sa.text("false"), nullable=False) for name in BOOL_COLUMNS]
    columns += [sa.Column(name, sa.Integer(), nullable=True) for name in NULLABLE_INT_COLUMNS]
    columns += [
        sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False)
        for name in JSON_COLUMNS
    ]
    return columns


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("match_id", sa.String(length=50), nullable=False),
        sa.Column("creation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("queue_id", sa.Integer(), server_default=sa.text("420"), nullable=False),
        sa.Column("game_version", sa.String(length=32), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("match_id"),
    )

    op.create_table(
        "match_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.String(length=50), nullable=False),
        sa.Column("puuid", sa.String(length=100), nullable=False),
        sa.Column("creation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("player_role", sa.String(length=20), server_default="UNKNOWN", nullable=False),
        sa.Column("champion", sa.String(length=50), nullable=False),
        sa.Column("win", sa.Boolean(), nullable=False),
        *_stat_columns(),
        sa.ForeignKeyConstraint(["match_id"], ["matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "puuid", name="uq_match_participants_match_puuid"),
    )
    op.create_index(
        "ix_match_participants_puuid_creation_time", "match_participants", ["puuid", "creation_time"]
    )

    op.create_table(
        "snapshot_participants",
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("match_participant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["match_participant_id"], ["match_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("snapshot_id", "match_participant_id"),
    )
    op.create_index(
        op.f("ix_snapshot_participants_match_participant_id"), "snapshot_participants", ["match_participant_id"]
    )

    op.create_table(
        "player_history_entries",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("match_participant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["match_participant_id"], ["match_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "match_participant_id"),
    )
    op.create_index(
        op.f("ix_player_history_entries_match_participant_id"), "player_history_entries", ["match_participant_id"]
    )

    op.create_table(
        "legacy_unresolved_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.String(length=50), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_legacy_unresolved_links_player_id"), "legacy_unresolved_links", ["player_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_legacy_unresolved_links_player_id"), table_name="legacy_unresolved_links")
    op.drop_table("legacy_unresolved_links")
    op.drop_index(op.f("ix_player_history_entries_match_participant_id"), table_name="player_history_entries")
    op.drop_table("player_history_entries")
    op.drop_index(op.f("ix_snapshot_participants_match_participant_id"), table_name="snapshot_participants")
    op.drop_table("snapshot_participants")
    op.drop_index("ix_match_participants_puuid_creation_time", table_name="match_participants")
    op.drop_table("match_participants")
    op.drop_table("matches")
