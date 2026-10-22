"""Daily rating snapshots for the live track record.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rating_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("style", sa.String(8), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("liquid", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("style", "day", "ticker", name="uq_rating_snapshot"),
    )


def downgrade() -> None:
    op.drop_table("rating_snapshots")
