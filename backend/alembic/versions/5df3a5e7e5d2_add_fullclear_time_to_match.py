"""add_fullclear_time_to_match

Revision ID: 5df3a5e7e5d2
Revises: dba87524cbc7
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5df3a5e7e5d2'
down_revision: Union[str, None] = 'dba87524cbc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('match_data', sa.Column('fullclear_time', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('match_data', 'fullclear_time')
