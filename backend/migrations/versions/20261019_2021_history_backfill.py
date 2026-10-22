"""Mark stocks whose multi-year daily history was fetched.

Revision ID: 20261019_202100
Revises: 20261018_065300
Create Date: 2026-10-19 20:21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_202100"
down_revision: str | None = "20261018_065300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("stocks") as batch_op:
        batch_op.add_column(sa.Column("history_backfilled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("stocks") as batch_op:
        batch_op.drop_column("history_backfilled_at")
