"""Investor style no longer has a Strong Buy rating: move remembered ratings
down, so rating-change alerts don't fire for the rename.

Revision ID: 20261022_213600
Revises: 20261022_205700
Create Date: 2026-10-22 21:36
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_213600"
down_revision: str | None = "20261022_205700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Users without a saved style are investors (the default).
    op.execute(
        "UPDATE rating_state SET rating = 'Buy' WHERE rating = 'Strong Buy' "
        "AND user_id NOT IN (SELECT user_id FROM user_preferences "
        "WHERE key = 'investing_style' AND value = 'trader' AND user_id IS NOT NULL)"
    )
    op.execute(
        "UPDATE rating_snapshots SET rating = 'Buy' "
        "WHERE style = 'investor' AND rating = 'Strong Buy'"
    )


def downgrade() -> None:
    pass  # the old top rating can't be told apart from Buy any more
