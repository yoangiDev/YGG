"""Remove dragon_setups: objective_setups already covers each dragon (presence, team and contest)

Revision ID: c7e1a9d3f5b2
Revises: b4d8f2a6c1e3
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7e1a9d3f5b2"
down_revision: Union[str, None] = "b4d8f2a6c1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("match_participants", "dragon_setups")


def downgrade() -> None:
    op.add_column(
        "match_participants",
        sa.Column(
            "dragon_setups",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
