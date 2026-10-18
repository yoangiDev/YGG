"""Several accounts per user: each verified with its icon, so there is no need to limit them to one any more

Revision ID: d1b6f3a8c2e5
Revises: c5e1a7b3d9f4
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d1b6f3a8c2e5"
down_revision: Union[str, None] = "c5e1a7b3d9f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_players_user", "players", type_="unique")
    op.create_unique_constraint("uq_players_user_puuid", "players", ["user_id", "puuid"])


def downgrade() -> None:
    # fails if someone already has two accounts: better to stop than to delete anyone's without looking
    op.drop_constraint("uq_players_user_puuid", "players", type_="unique")
    op.create_unique_constraint("uq_players_user", "players", ["user_id"])
