"""players: one account per user (plan 16.20, B.5)

Riot only lets you download the replays of your own matches, so each user links their account and nothing else. The
old constraint, (user_id, puuid), allowed having several different accounts.

Revision ID: d4a9e6c2f8b1
Revises: c2e8f4a1d6b3
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d4a9e6c2f8b1"
down_revision: Union[str, None] = "c2e8f4a1d6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # fails if someone has two accounts: that is on purpose, better to stop than to delete anyone's accounts without looking
    op.drop_constraint("uq_players_user_puuid", "players", type_="unique")
    op.create_unique_constraint("uq_players_user", "players", ["user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_players_user", "players", type_="unique")
    op.create_unique_constraint("uq_players_user_puuid", "players", ["user_id", "puuid"])
