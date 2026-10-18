"""Daily elo tracking: players.track_elo and the elo_history table

Revision ID: d4e8a1c6f2b7
Revises: c7e1a9d3f5b2
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e8a1c6f2b7"
down_revision: Union[str, None] = "c7e1a9d3f5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("track_elo", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_table(
        "elo_history",
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("division", sa.String(5), nullable=False),
        sa.Column("lp", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("elo_history")
    op.drop_column("players", "track_elo")
