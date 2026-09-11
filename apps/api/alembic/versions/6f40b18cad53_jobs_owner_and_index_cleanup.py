"""Dueño de los jobs y limpieza de índices redundantes

- jobs.user_id: el estado de un job solo lo puede consultar quien lo lanzó (P2).
- Los índices ix_<tabla>_id duplicaban el índice de la clave primaria.

Revision ID: 6f40b18cad53
Revises: 5e3fa07b9c42
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6f40b18cad53"
down_revision: Union[str, None] = "5e3fa07b9c42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REDUNDANT_INDEXES = (
    ("ix_users_id", "users", "id"),
    ("ix_players_id", "players", "id"),
    ("ix_snapshots_id", "snapshots", "id"),
    ("ix_jobs_job_id", "jobs", "job_id"),
)


def upgrade() -> None:
    op.add_column("jobs", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("jobs_user_id_fkey", "jobs", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"], unique=False)

    for index, table, _ in REDUNDANT_INDEXES:
        op.drop_index(index, table_name=table)


def downgrade() -> None:
    for index, table, column in REDUNDANT_INDEXES:
        op.create_index(index, table, [column], unique=False)

    op.drop_index(op.f("ix_jobs_user_id"), table_name="jobs")
    op.drop_constraint("jobs_user_id_fkey", "jobs", type_="foreignkey")
    op.drop_column("jobs", "user_id")
