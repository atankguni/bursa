"""Preference values can hold a JSON document (synced display settings).

user_preferences.value: VARCHAR(255) -> TEXT.

Revision ID: 20261017_222700
Revises: 20261017_220600
Create Date: 2026-10-17 22:27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_222700"
down_revision: str | None = "20261017_220600"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.alter_column(
            "value", existing_type=sa.String(255), type_=sa.Text(), existing_nullable=False
        )


def downgrade() -> None:
    # Values longer than 255 characters (display settings) can't be kept.
    op.execute(sa.text("DELETE FROM user_preferences WHERE LENGTH(value) > 255"))
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.alter_column(
            "value", existing_type=sa.Text(), type_=sa.String(255), existing_nullable=False
        )
