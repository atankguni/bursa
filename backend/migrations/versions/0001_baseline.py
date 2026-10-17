"""Baseline: the schema as it was when Alembic was introduced.

Creates only tables that don't exist yet, so a database made earlier by
`create_all` (see db/migrate.py) converges on this schema instead of failing.
Later migrations are ordinary Alembic scripts.

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import SchemaItem

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Parents before children (foreign keys); dropped in reverse.
TABLES = [
    "index_bars",
    "index_quotes",
    "preferences",
    "stocks",
    "alerts",
    "dividends",
    "fundamentals",
    "rating_state",
    "splits",
    "stock_indices",
    "stock_prices",
    "stock_profiles",
    "transactions",
    "watchlist",
    "alert_events",
]

_existing: set[str] = set()


def _create_table(
    name: str,
    *elements: SchemaItem,
    indexes: Sequence[tuple[str, list[str], bool]] = (),
) -> None:
    if name in _existing:
        return
    op.create_table(name, *elements)
    for index_name, columns, unique in indexes:
        op.create_index(index_name, name, columns, unique=unique)


def upgrade() -> None:
    _existing.update(sa.inspect(op.get_bind()).get_table_names())

    _create_table(
        "index_bars",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('open', sa.Double(), nullable=True),
        sa.Column('high', sa.Double(), nullable=True),
        sa.Column('low', sa.Double(), nullable=True),
        sa.Column('close', sa.Double(), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'day', name='uq_index_bar'),
        indexes=[
            ("ix_index_bars_code", ["code"], False),
        ],
    )

    _create_table(
        "index_quotes",
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('last', sa.Double(), nullable=False),
        sa.Column('previous_close', sa.Double(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('full_history_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('code'),
    )

    _create_table(
        "preferences",
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )

    _create_table(
        "stocks",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('tracked', sa.Boolean(), nullable=False),
        sa.Column('full_history_at', sa.DateTime(), nullable=True),
        sa.Column('listing_board', sa.String(length=24), nullable=True),
        sa.Column('listed_on', sa.Date(), nullable=True),
        sa.Column('idx_shares', sa.Double(), nullable=True),
        sa.Column('idx_synced_at', sa.DateTime(), nullable=True),
        sa.Column('splits_checked_at', sa.DateTime(), nullable=True),
        sa.Column('fundamentals_checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        indexes=[
            ("ix_stocks_ticker", ["ticker"], True),
        ],
    )

    _create_table(
        "alerts",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('threshold', sa.Double(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        indexes=[
            ("ix_alerts_ticker", ["ticker"], False),
        ],
    )

    _create_table(
        "dividends",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('ex_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Double(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'ex_date', name='uq_dividend'),
        indexes=[
            ("ix_dividends_ex_date", ["ex_date"], False),
            ("ix_dividends_ticker", ["ticker"], False),
        ],
    )

    _create_table(
        "fundamentals",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('financial_currency', sa.String(length=8), nullable=True),
        sa.Column('total_shares', sa.Double(), nullable=True),
        sa.Column('revenue', sa.Double(), nullable=True),
        sa.Column('net_income', sa.Double(), nullable=True),
        sa.Column('total_assets', sa.Double(), nullable=True),
        sa.Column('total_liabilities', sa.Double(), nullable=True),
        sa.Column('equity', sa.Double(), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'fiscal_year', name='uq_fundamental_year'),
        indexes=[
            ("ix_fundamentals_fiscal_year", ["fiscal_year"], False),
            ("ix_fundamentals_ticker", ["ticker"], False),
        ],
    )

    _create_table(
        "rating_state",
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('rating', sa.String(length=16), nullable=False),
        sa.Column('strength', sa.String(length=16), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('ticker'),
    )

    _create_table(
        "splits",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('ex_date', sa.Date(), nullable=False),
        sa.Column('ratio', sa.Double(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'ex_date', name='uq_split'),
        indexes=[
            ("ix_splits_ticker", ["ticker"], False),
        ],
    )

    _create_table(
        "stock_indices",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('index_name', sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'index_name', name='uq_ticker_index'),
        indexes=[
            ("ix_stock_indices_index_name", ["index_name"], False),
            ("ix_stock_indices_ticker", ["ticker"], False),
        ],
    )

    _create_table(
        "stock_prices",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('interval', sa.String(length=8), nullable=False),
        sa.Column('open', sa.Double(), nullable=False),
        sa.Column('high', sa.Double(), nullable=False),
        sa.Column('low', sa.Double(), nullable=False),
        sa.Column('close', sa.Double(), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'timestamp', 'interval', name='uq_price_bar'),
        indexes=[
            ("ix_price_ticker_interval_ts", ["ticker", "interval", "timestamp"], False),
            ("ix_stock_prices_ticker", ["ticker"], False),
            ("ix_stock_prices_timestamp", ["timestamp"], False),
        ],
    )

    _create_table(
        "stock_profiles",
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('sector', sa.String(length=64), nullable=True),
        sa.Column('industry', sa.String(length=96), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('employees', sa.Integer(), nullable=True),
        sa.Column('website', sa.String(length=160), nullable=True),
        sa.Column('country', sa.String(length=64), nullable=True),
        sa.Column('city', sa.String(length=64), nullable=True),
        sa.Column('address', sa.String(length=200), nullable=True),
        sa.Column('phone', sa.String(length=48), nullable=True),
        sa.Column('officers', sa.JSON(), nullable=True),
        sa.Column('trailing_pe', sa.Double(), nullable=True),
        sa.Column('profit_margin', sa.Double(), nullable=True),
        sa.Column('revenue_growth', sa.Double(), nullable=True),
        sa.Column('earnings_growth', sa.Double(), nullable=True),
        sa.Column('dividend_yield', sa.Double(), nullable=True),
        sa.Column('beta', sa.Double(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('ticker'),
    )

    _create_table(
        "transactions",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('side', sa.String(length=4), nullable=False),
        sa.Column('quantity', sa.Double(), nullable=False),
        sa.Column('price', sa.Double(), nullable=False),
        sa.Column('fees', sa.Double(), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        indexes=[
            ("ix_transactions_ticker", ["ticker"], False),
            ("ix_transactions_trade_date", ["trade_date"], False),
        ],
    )

    _create_table(
        "watchlist",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        indexes=[
            ("ix_watchlist_ticker", ["ticker"], True),
        ],
    )

    _create_table(
        "alert_events",
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('triggered_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('value', sa.Double(), nullable=True),
        sa.Column('message', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        indexes=[
            ("ix_alert_events_alert_id", ["alert_id"], False),
            ("ix_alert_events_triggered_at", ["triggered_at"], False),
        ],
    )


def downgrade() -> None:
    for name in reversed(TABLES):
        op.drop_table(name)
