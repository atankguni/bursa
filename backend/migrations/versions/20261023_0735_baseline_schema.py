"""Baseline schema (all earlier migrations squashed).

Databases from before the squash are converted with scripts/convert_db.py.

Revision ID: 20261023_073546
Revises:
Create Date: 2026-10-23 07:35:46.731104+07:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import db.types

revision: str = "20261023_073546"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "indices",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("last", sa.Double(), nullable=True),
        sa.Column("previous_close", sa.Double(), nullable=True),
        sa.Column("updated_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("full_history_at", db.types.UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_indices")),
    )
    op.create_table(
        "stocks",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("tracked", sa.Boolean(), nullable=False),
        sa.Column("listing_board", sa.String(length=24), nullable=True),
        sa.Column("listed_on", sa.Date(), nullable=True),
        sa.Column("idx_shares", sa.Double(), nullable=True),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("ticker", name=op.f("pk_stocks")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("last_login_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("mfa_email", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("totp_secret", sa.Text(), nullable=True),
        sa.Column("totp_pending", sa.Text(), nullable=True),
        sa.Column("totp_last_step", sa.BigInteger(), nullable=True),
        sa.Column("password_weak", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name=op.f("ck_users_role_values")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("threshold", sa.Double(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_triggered_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "type IN ('price_above', 'price_below', 'pct_change', 'rating_change', 'dividend_soon')",
            name=op.f("ck_alerts_type_values"),
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_alerts_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_alerts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_alerts_ticker"), ["ticker"], unique=False)
        batch_op.create_index(batch_op.f("ix_alerts_user_id"), ["user_id"], unique=False)

    op.create_table(
        "assistant_chats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assistant_chats_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_chats")),
    )
    with op.batch_alter_table("assistant_chats", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_assistant_chats_updated_at"), ["updated_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_assistant_chats_user_id"), ["user_id"], unique=False)

    op.create_table(
        "daily_bars",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("open", sa.Double(), nullable=False),
        sa.Column("high", sa.Double(), nullable=False),
        sa.Column("low", sa.Double(), nullable=False),
        sa.Column("close", sa.Double(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_daily_bars_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", "day", name=op.f("pk_daily_bars")),
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("daily_bars", schema=None) as batch_op:
        batch_op.create_index("ix_daily_bars_day", ["day"], unique=False)

    op.create_table(
        "dividends",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Double(), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_dividends_amount_not_negative")),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_dividends_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", "ex_date", name=op.f("pk_dividends")),
    )
    op.create_table(
        "fundamentals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("financial_currency", sa.String(length=8), nullable=False),
        sa.Column("total_shares", sa.Double(), nullable=True),
        sa.Column("revenue", sa.Double(), nullable=True),
        sa.Column("net_income", sa.Double(), nullable=True),
        sa.Column("total_assets", sa.Double(), nullable=True),
        sa.Column("total_liabilities", sa.Double(), nullable=True),
        sa.Column("equity", sa.Double(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("updated_at", db.types.UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "source IN ('statements', 'summary')", name=op.f("ck_fundamentals_source_values")
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_fundamentals_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fundamentals")),
        sa.UniqueConstraint(
            "ticker", "fiscal_year", name=op.f("uq_fundamentals_ticker_fiscal_year")
        ),
    )
    op.create_table(
        "index_bars",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("open", sa.Double(), nullable=True),
        sa.Column("high", sa.Double(), nullable=True),
        sa.Column("low", sa.Double(), nullable=True),
        sa.Column("close", sa.Double(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["code"],
            ["indices.code"],
            name=op.f("fk_index_bars_code_indices"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("code", "day", name=op.f("pk_index_bars")),
    )
    op.create_table(
        "intraday_bars",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("timestamp", db.types.UTCDateTime(), nullable=False),
        sa.Column("open", sa.Double(), nullable=False),
        sa.Column("high", sa.Double(), nullable=False),
        sa.Column("low", sa.Double(), nullable=False),
        sa.Column("close", sa.Double(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_intraday_bars_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", "timestamp", name=op.f("pk_intraday_bars")),
        sqlite_with_rowid=False,
    )
    with op.batch_alter_table("intraday_bars", schema=None) as batch_op:
        batch_op.create_index("ix_intraday_bars_timestamp", ["timestamp"], unique=False)

    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=8), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=True),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("accepted_at", db.types.UTCDateTime(), nullable=True),
        sa.CheckConstraint("role IN ('user', 'admin')", name=op.f("ck_invites_role_values")),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name=op.f("fk_invites_invited_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invites_token_hash")),
    )
    with op.batch_alter_table("invites", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_invites_email"), ["email"], unique=False)

    op.create_table(
        "mfa_challenges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("email_code_hash", sa.String(length=64), nullable=True),
        sa.Column("email_sent_at", db.types.UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('login', 'enroll_email')", name=op.f("ck_mfa_challenges_purpose_values")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mfa_challenges_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_challenges")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_mfa_challenges_token_hash")),
    )
    with op.batch_alter_table("mfa_challenges", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_mfa_challenges_expires_at"), ["expires_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_mfa_challenges_user_id"), ["user_id"], unique=False)

    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("used_at", db.types.UTCDateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_resets_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_resets")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_resets_token_hash")),
    )
    with op.batch_alter_table("password_resets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_password_resets_user_id"), ["user_id"], unique=False)

    op.create_table(
        "rating_snapshots",
        sa.Column("style", sa.String(length=8), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("rating", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("liquid", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "rating IN ('Strong Buy', 'Buy', 'Hold', 'Reduce', 'Avoid')",
            name=op.f("ck_rating_snapshots_rating_values"),
        ),
        sa.CheckConstraint(
            "style IN ('investor', 'trader')", name=op.f("ck_rating_snapshots_style_values")
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_rating_snapshots_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("style", "day", "ticker", name=op.f("pk_rating_snapshots")),
    )
    op.create_table(
        "rating_state",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("rating", sa.String(length=16), nullable=False),
        sa.Column("strength", sa.String(length=16), nullable=True),
        sa.Column("updated_at", db.types.UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "rating IN ('Strong Buy', 'Buy', 'Hold', 'Reduce', 'Avoid')",
            name=op.f("ck_rating_state_rating_values"),
        ),
        sa.CheckConstraint(
            "strength IN ('Weak', 'Moderate', 'Strong', 'Very Strong')",
            name=op.f("ck_rating_state_strength_values"),
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_rating_state_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_rating_state_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "ticker", name=op.f("pk_rating_state")),
    )
    with op.batch_alter_table("rating_state", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rating_state_ticker"), ["ticker"], unique=False)

    op.create_table(
        "recovery_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("used_at", db.types.UTCDateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_recovery_codes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_codes")),
    )
    with op.batch_alter_table("recovery_codes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_recovery_codes_user_id"), ["user_id"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("last_seen_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False)

    op.create_table(
        "splits",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("ratio", sa.Double(), nullable=False),
        sa.CheckConstraint("ratio > 0", name=op.f("ck_splits_ratio_positive")),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_splits_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", "ex_date", name=op.f("pk_splits")),
    )
    op.create_table(
        "stock_indices",
        sa.Column("index_code", sa.String(length=20), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.ForeignKeyConstraint(
            ["index_code"],
            ["indices.code"],
            name=op.f("fk_stock_indices_index_code_indices"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_stock_indices_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("index_code", "ticker", name=op.f("pk_stock_indices")),
    )
    with op.batch_alter_table("stock_indices", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stock_indices_ticker"), ["ticker"], unique=False)

    op.create_table(
        "stock_profiles",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("industry", sa.String(length=96), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employees", sa.Integer(), nullable=True),
        sa.Column("website", sa.String(length=160), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=48), nullable=True),
        sa.Column("officers", sa.JSON(), nullable=True),
        sa.Column("trailing_pe", sa.Double(), nullable=True),
        sa.Column("profit_margin", sa.Double(), nullable=True),
        sa.Column("revenue_growth", sa.Double(), nullable=True),
        sa.Column("earnings_growth", sa.Double(), nullable=True),
        sa.Column("dividend_yield", sa.Double(), nullable=True),
        sa.Column("beta", sa.Double(), nullable=True),
        sa.Column("updated_at", db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_stock_profiles_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", name=op.f("pk_stock_profiles")),
    )
    op.create_table(
        "stock_quotes",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("close", sa.Double(), nullable=False),
        sa.Column("prev_close", sa.Double(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_stock_quotes_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", name=op.f("pk_stock_quotes")),
    )
    op.create_table(
        "sync_state",
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("job", sa.String(length=20), nullable=False),
        sa.Column("done_at", db.types.UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "job IN ('listing', 'history_backfill', 'full_history', 'splits', 'fundamentals')",
            name=op.f("ck_sync_state_job_values"),
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_sync_state_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ticker", "job", name=op.f("pk_sync_state")),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Double(), nullable=False),
        sa.Column("fees", sa.Double(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name=op.f("ck_transactions_side_values")),
        sa.CheckConstraint("fees >= 0", name=op.f("ck_transactions_fees_not_negative")),
        sa.CheckConstraint("price > 0", name=op.f("ck_transactions_price_positive")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_transactions_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_transactions_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_transactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_transactions_ticker"), ["ticker"], unique=False)
        batch_op.create_index(
            "ix_transactions_user_id_trade_date", ["user_id", "trade_date"], unique=False
        )

    op.create_table(
        "trusted_devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_trusted_devices_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trusted_devices")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_trusted_devices_token_hash")),
    )
    with op.batch_alter_table("trusted_devices", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_trusted_devices_expires_at"), ["expires_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_trusted_devices_user_id"), ["user_id"], unique=False)

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "investing_style", sa.String(length=8), server_default="investor", nullable=False
        ),
        sa.Column("assistant_personal_data", sa.Boolean(), nullable=True),
        sa.Column("assistant_save_chats", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("daily_digest", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("alerts_seen_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("display", sa.JSON(), nullable=True),
        sa.Column("trading_costs", sa.JSON(), nullable=True),
        sa.Column("updated_at", db.types.UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "investing_style IN ('investor', 'trader')",
            name=op.f("ck_user_settings_investing_style_values"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_settings")),
    )
    op.create_table(
        "watchlist",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("added_at", db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_watchlist_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_watchlist_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "ticker", name=op.f("pk_watchlist")),
    )
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_watchlist_ticker"), ["ticker"], unique=False)

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("triggered_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("value", sa.Double(), nullable=True),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name=op.f("fk_alert_events_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticker"],
            ["stocks.ticker"],
            name=op.f("fk_alert_events_ticker_stocks"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_alert_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_events")),
    )
    with op.batch_alter_table("alert_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_alert_events_alert_id"), ["alert_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_alert_events_ticker"), ["ticker"], unique=False)
        batch_op.create_index(
            "ix_alert_events_user_id_triggered_at", ["user_id", "triggered_at"], unique=False
        )

    op.create_table(
        "assistant_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tools_used", sa.JSON(), nullable=True),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name=op.f("ck_assistant_chat_messages_role_values")
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["assistant_chats.id"],
            name=op.f("fk_assistant_chat_messages_chat_id_assistant_chats"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_chat_messages")),
    )
    with op.batch_alter_table("assistant_chat_messages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_assistant_chat_messages_chat_id"), ["chat_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("assistant_chat_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_assistant_chat_messages_chat_id"))

    op.drop_table("assistant_chat_messages")
    with op.batch_alter_table("alert_events", schema=None) as batch_op:
        batch_op.drop_index("ix_alert_events_user_id_triggered_at")
        batch_op.drop_index(batch_op.f("ix_alert_events_ticker"))
        batch_op.drop_index(batch_op.f("ix_alert_events_alert_id"))

    op.drop_table("alert_events")
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_watchlist_ticker"))

    op.drop_table("watchlist")
    op.drop_table("user_settings")
    with op.batch_alter_table("trusted_devices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_trusted_devices_user_id"))
        batch_op.drop_index(batch_op.f("ix_trusted_devices_expires_at"))

    op.drop_table("trusted_devices")
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_index("ix_transactions_user_id_trade_date")
        batch_op.drop_index(batch_op.f("ix_transactions_ticker"))

    op.drop_table("transactions")
    op.drop_table("sync_state")
    op.drop_table("stock_quotes")
    op.drop_table("stock_profiles")
    with op.batch_alter_table("stock_indices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stock_indices_ticker"))

    op.drop_table("stock_indices")
    op.drop_table("splits")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_user_id"))
        batch_op.drop_index(batch_op.f("ix_sessions_expires_at"))

    op.drop_table("sessions")
    with op.batch_alter_table("recovery_codes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_recovery_codes_user_id"))

    op.drop_table("recovery_codes")
    with op.batch_alter_table("rating_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_rating_state_ticker"))

    op.drop_table("rating_state")
    op.drop_table("rating_snapshots")
    with op.batch_alter_table("password_resets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_password_resets_user_id"))

    op.drop_table("password_resets")
    with op.batch_alter_table("mfa_challenges", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_mfa_challenges_user_id"))
        batch_op.drop_index(batch_op.f("ix_mfa_challenges_expires_at"))

    op.drop_table("mfa_challenges")
    with op.batch_alter_table("invites", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_invites_email"))

    op.drop_table("invites")
    with op.batch_alter_table("intraday_bars", schema=None) as batch_op:
        batch_op.drop_index("ix_intraday_bars_timestamp")

    op.drop_table("intraday_bars")
    op.drop_table("index_bars")
    op.drop_table("fundamentals")
    op.drop_table("dividends")
    with op.batch_alter_table("daily_bars", schema=None) as batch_op:
        batch_op.drop_index("ix_daily_bars_day")

    op.drop_table("daily_bars")
    with op.batch_alter_table("assistant_chats", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_assistant_chats_user_id"))
        batch_op.drop_index(batch_op.f("ix_assistant_chats_updated_at"))

    op.drop_table("assistant_chats")
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_alerts_user_id"))
        batch_op.drop_index(batch_op.f("ix_alerts_ticker"))

    op.drop_table("alerts")
    op.drop_table("users")
    op.drop_table("stocks")
    op.drop_table("indices")
