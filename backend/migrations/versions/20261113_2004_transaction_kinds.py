"""Transaction kinds: exercised rights issues (at the exercise price) and bonus
shares / stock dividends (price 0), besides trades.

Revision ID: 20261113_200439
Revises: 20261023_214739
Create Date: 2026-11-13 20:04:39.358737+07:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261113_200439"
down_revision: str | None = "20261023_214739"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Short names: the naming convention adds the ck_transactions_ prefix.
PRICE_BY_KIND = (
    "(kind = 'bonus' AND price = 0 AND fees = 0 AND side = 'buy') "
    "OR (kind != 'bonus' AND price > 0)"
)


def upgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(length=6), server_default="trade", nullable=False)
        )
        batch_op.drop_constraint("price_positive", type_="check")
        batch_op.create_check_constraint("kind_values", "kind IN ('trade', 'rights', 'bonus')")
        batch_op.create_check_constraint("price_by_kind", PRICE_BY_KIND)
        batch_op.create_check_constraint("received_is_buy", "kind = 'trade' OR side = 'buy'")


def downgrade() -> None:
    # Bonus shares (price 0) can't satisfy the old price > 0 rule.
    op.execute("DELETE FROM transactions WHERE kind = 'bonus'")
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_constraint("received_is_buy", type_="check")
        batch_op.drop_constraint("price_by_kind", type_="check")
        batch_op.drop_constraint("kind_values", type_="check")
        batch_op.create_check_constraint("price_positive", "price > 0")
        batch_op.drop_column("kind")
