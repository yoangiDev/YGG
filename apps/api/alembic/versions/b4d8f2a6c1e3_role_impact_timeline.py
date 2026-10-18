"""Impact by role: ganks and roams, objective setup, plates and destroyed wards

They come from the timeline that is already downloaded in every analysis. `timeline_version` marks
which computation each row was stored with: earlier ones are downloaded again.

Revision ID: b4d8f2a6c1e3
Revises: 9c73e4bf1a86
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4d8f2a6c1e3"
down_revision: Union[str, None] = "9c73e4bf1a86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INT_COLUMNS = ("timeline_version", "turret_plates", "wards_killed", "early_takedowns", "early_team_kills")
EVENT_COLUMNS = ("objective_setups", "lane_visits")


def upgrade() -> None:
    for name in INT_COLUMNS:
        op.add_column(
            "match_participants", sa.Column(name, sa.Integer(), server_default=sa.text("0"), nullable=False)
        )
    for name in EVENT_COLUMNS:
        op.add_column(
            "match_participants",
            sa.Column(
                name, postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
            ),
        )


def downgrade() -> None:
    for name in (*EVENT_COLUMNS, *INT_COLUMNS):
        op.drop_column("match_participants", name)
