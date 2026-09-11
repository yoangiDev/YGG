"""Detalle de partidas: los 10 participantes, guardados al consultarlos

Hasta ahora solo se guardaban las estadísticas de los jugadores seguidos. Al
desplegar una partida del historial se pide a Riot el payload completo y se
guarda un resumen (ygg_core MatchSummary) para no volver a pedirlo.

Revision ID: 9c73e4bf1a86
Revises: 8b62d3ae0f75
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c73e4bf1a86"
down_revision: Union[str, None] = "8b62d3ae0f75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_details",
        sa.Column("match_id", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id"),
    )


def downgrade() -> None:
    op.drop_table("match_details")
