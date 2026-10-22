"""Flag accounts whose password fails the strength / leaked-password policy.

Revision ID: 20261018_065300
Revises: 20261018_064200
Create Date: 2026-10-18 06:53
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_065300"
down_revision: str | None = "20261018_064200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("password_weak", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_weak")
