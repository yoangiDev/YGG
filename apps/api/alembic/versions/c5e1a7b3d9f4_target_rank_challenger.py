"""All accounts are compared with Challenger: it is no longer chosen

Revision ID: c5e1a7b3d9f4
Revises: b2f7d4a9c1e6
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c5e1a7b3d9f4"
down_revision: Union[str, None] = "b2f7d4a9c1e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE players SET target_rank = 'CHALLENGER' WHERE target_rank <> 'CHALLENGER'")


def downgrade() -> None:
    pass  # what each account had chosen is not stored
