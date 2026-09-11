"""Cola de trabajos: parámetros, intentos, heartbeat e idempotencia

Los análisis dejan de correr con asyncio.create_task dentro de la API (P3):
el job guarda lo necesario para que un worker lo ejecute y un heartbeat para
detectar los que se quedan huérfanos.

Los jobs que seguían en "processing" venían de ese modelo antiguo y no van a
terminar nunca: se marcan como error.

Revision ID: 8b62d3ae0f75
Revises: 7a51c29dbe64
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8b62d3ae0f75"
down_revision: Union[str, None] = "7a51c29dbe64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("player_id", sa.Integer(), nullable=True))
    op.create_foreign_key("jobs_player_id_fkey", "jobs", "players", ["player_id"], ["id"], ondelete="CASCADE")
    op.add_column("jobs", sa.Column("date_from", sa.BigInteger(), nullable=True))
    op.add_column("jobs", sa.Column("date_to", sa.BigInteger(), nullable=True))
    op.add_column("jobs", sa.Column("description", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        "UPDATE jobs SET status = 'error', "
        "error = coalesce(error, 'Interrupted: this analysis ran inside the API process before the job queue existed.') "
        "WHERE status = 'processing'"
    )

    op.create_index(
        "uq_jobs_active_request",
        "jobs",
        ["user_id", "player_id", "date_from", "date_to"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )
    op.create_index("ix_jobs_status_heartbeat_at", "jobs", ["status", "heartbeat_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_status_heartbeat_at", table_name="jobs")
    op.drop_index("uq_jobs_active_request", table_name="jobs")
    op.execute("UPDATE jobs SET status = 'error' WHERE status = 'queued'")
    for column in ("finished_at", "started_at", "heartbeat_at", "attempts", "description", "date_to", "date_from"):
        op.drop_column("jobs", column)
    op.drop_constraint("jobs_player_id_fkey", "jobs", type_="foreignkey")
    op.drop_column("jobs", "player_id")
