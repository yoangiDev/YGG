"""players.target_rank: target rank their snapshots are compared against

Revision ID: e5b9c2d7a3f1
Revises: d4e8a1c6f2b7
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5b9c2d7a3f1"
down_revision: Union[str, None] = "d4e8a1c6f2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("players", sa.Column("target_rank", sa.String(20), server_default="CHALLENGER", nullable=False))


def downgrade() -> None:
    op.drop_column("players", "target_rank")
