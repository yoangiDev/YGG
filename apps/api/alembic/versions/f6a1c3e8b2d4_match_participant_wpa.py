"""match_participants: events with WPA, WP curve and grade (timeline version 4)

Revision ID: f6a1c3e8b2d4
Revises: e5b9c2d7a3f1
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f6a1c3e8b2d4"
down_revision: Union[str, None] = "e5b9c2d7a3f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("match_participants", sa.Column("wpa_events", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("match_participants", sa.Column("wp_curve", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("match_participants", sa.Column("wpa_total", sa.Float(), nullable=True))
    op.add_column("match_participants", sa.Column("wpa_grade", sa.Integer(), nullable=True))


def downgrade() -> None:
    for column in ("wpa_grade", "wpa_total", "wp_curve", "wpa_events"):
        op.drop_column("match_participants", column)
