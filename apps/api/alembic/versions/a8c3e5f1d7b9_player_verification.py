"""Account verification: the profile icon requested and when it was checked

Revision ID: a8c3e5f1d7b9
Revises: e7c1a9d3b5f2
Create Date: 2026-10-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8c3e5f1d7b9"
down_revision: Union[str, None] = "e7c1a9d3b5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # accounts already linked are left unverified: they are asked for the icon the next time they sign in
    op.add_column("players", sa.Column("verify_icon", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE players SET verify_icon = 1 + floor(random() * 28)::int WHERE verify_icon IS NULL")


def downgrade() -> None:
    op.drop_column("players", "verified_at")
    op.drop_column("players", "verify_icon")
