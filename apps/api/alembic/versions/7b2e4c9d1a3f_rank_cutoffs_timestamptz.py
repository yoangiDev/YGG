"""rank_cutoffs gestionada por Alembic y con fetched_at timestamptz

La tabla existía en producción solo porque `Base.metadata.create_all` la creaba
al arrancar. Esta migración la crea en bases nuevas y, en las que ya la tienen,
convierte `fetched_at` de timestamp naive (UTC implícito) a timestamptz.

Revision ID: 7b2e4c9d1a3f
Revises: c3f8a2d1e490
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7b2e4c9d1a3f"
down_revision: Union[str, None] = "c3f8a2d1e490"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("rank_cutoffs"):
        op.create_table(
            "rank_cutoffs",
            sa.Column("platform", sa.String(length=10), nullable=False),
            sa.Column("grandmaster_cutoff_lp", sa.Integer(), nullable=False),
            sa.Column("challenger_cutoff_lp", sa.Integer(), nullable=False),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("platform"),
        )
        return

    op.alter_column(
        "rank_cutoffs",
        "fetched_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="fetched_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "rank_cutoffs",
        "fetched_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="fetched_at AT TIME ZONE 'UTC'",
    )
