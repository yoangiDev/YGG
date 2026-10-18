"""Match details: the 10 participants, stored when queried

Until now only the stats of the followed players were stored. When
a history match is expanded, the full payload is requested from Riot and
a summary is stored (ygg_core MatchSummary) so it isn't requested again.

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
