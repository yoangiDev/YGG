"""game_analyses: the analysis of each match the agent uploads (16.20)

Revision ID: c2e8f4a1d6b3
Revises: a7c3e9f1b5d2
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c2e8f4a1d6b3"
down_revision: Union[str, None] = "a7c3e9f1b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_id", sa.String(30), nullable=False),
        sa.Column("result", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "match_id", name="uq_game_analyses_user_match"),
    )
    op.create_index("ix_game_analyses_user_id", "game_analyses", ["user_id"])
    op.create_index("ix_game_analyses_created_at", "game_analyses", ["created_at"])


def downgrade() -> None:
    op.drop_table("game_analyses")
