"""game_analyses: status, error and review (the match is requested on the web and the agent uploads it)

Revision ID: e7c1a9d3b5f2
Revises: d4a9e6c2f8b1
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e7c1a9d3b5f2"
down_revision: Union[str, None] = "d4a9e6c2f8b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # the ones that already exist were uploaded analysed: done
    op.add_column("game_analyses", sa.Column("status", sa.String(20), nullable=False, server_default="done"))
    op.alter_column("game_analyses", "status", server_default="requested")
    op.add_column("game_analyses", sa.Column("error", sa.Text(), nullable=True))
    op.add_column("game_analyses", sa.Column("review", JSONB, nullable=True))
    op.alter_column("game_analyses", "result", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM game_analyses WHERE result IS NULL")
    op.alter_column("game_analyses", "result", nullable=False)
    op.drop_column("game_analyses", "review")
    op.drop_column("game_analyses", "error")
    op.drop_column("game_analyses", "status")
