"""Drop track_elo: elo is tracked automatically on all verified accounts

Revision ID: b2f7d4a9c1e6
Revises: a8c3e5f1d7b9
Create Date: 2026-10-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2f7d4a9c1e6"
down_revision: Union[str, None] = "a8c3e5f1d7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("players", "track_elo")


def downgrade() -> None:
    op.add_column("players", sa.Column("track_elo", sa.Boolean(), server_default=sa.false(), nullable=False))
