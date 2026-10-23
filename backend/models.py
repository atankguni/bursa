"""
models.py
---------
SQLAlchemy 2.0 ORM models.

Market data
  `Stock`        -> every listed IDX company, keyed by its IDX code ("BBCA").
                    Providers' own symbols ("BBCA.JK") stay inside the provider.
  `MarketIndex`  -> an IDX index (LQ45, COMPOSITE, ...) and its latest quote.
  `StockIndex`   -> which index a stock belongs to (many-to-many).
  `DailyBar`     -> one row per stock per trading day.
  `IntradayBar`  -> 1-minute bars, kept for `intraday_retention_days`.
  `StockQuote`   -> latest close + previous close per stock, written by the sync,
                    so list pages don't search a million bars per request.
  `Fundamental`, `StockProfile`, `Dividend`, `Split`, `IndexBar`.
  `SyncState`    -> when per-stock background work last ran (job bookkeeping,
                    kept out of the stock's own data).

Users
  `User` (+ `UserSession`, `Invite`, `PasswordReset`, 2FA tables),
  `UserSettings`, `Watchlist`, `Transaction`, `Alert`, `AlertEvent`,
  `RatingState`, `AssistantChat`, `ChatMessage`.

Conventions
  * Stocks are referenced by code with ON UPDATE CASCADE: when IDX renames a
    code, updating `stocks.ticker` updates every table.
  * Points in time are `UTCDateTime` (aware UTC in Python); market days are `Date`.
  * Value sets are CHECK constraints generated from the `Literal`s in `schemas.py`.
  * Numbers use `Double` (8-byte): a 4-byte float would round large IDR figures.
    Doubles are exact for whole rupiah up to 9e15.
  * Composite natural keys instead of surrogate ids where rows are identified by
    them (bars, dividends, splits, memberships); `WITHOUT ROWID` on SQLite for the
    big bar tables, so rows are stored in key order with no extra index.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from clock import utcnow
from database import Base
from db.types import UTCDateTime, one_of
from schemas import (
    AlertType,
    ChatRole,
    FundamentalSource,
    InvestingStyle,
    MfaPurpose,
    Rating,
    Role,
    Strength,
    SyncJob,
    TradeSide,
)


def _stock_fk(*, primary_key: bool = False, index: bool = False) -> Mapped[str]:
    """A stock code column referencing `stocks.ticker` (follows renames, deleted with it)."""
    return mapped_column(
        String(12),
        ForeignKey("stocks.ticker", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=primary_key,
        index=index,
        nullable=False,
    )


def _user_fk(*, primary_key: bool = False, index: bool = False) -> Mapped[int]:
    return mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=primary_key,
        index=index,
        nullable=False,
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, default=utcnow, nullable=False)


def _updated_at() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)


# --------------------------------------------------------------------------- #
# Users and sign-in
# --------------------------------------------------------------------------- #
class User(Base):
    """An account. Invite-only: created by accepting an Invite."""

    __tablename__ = "users"
    __table_args__ = (one_of("role", Role),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Stored lower-cased (services/auth.normalize_email).
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(String(8), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Two-factor authentication (services/two_factor.py). Either or both methods.
    mfa_email: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Authenticator-app secret, encrypted (services/crypto.py). Pending = shown
    # as a QR code but not confirmed with a code yet.
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_pending: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Last accepted time step: each authenticator code works only once.
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # The password failed today's policy (too guessable or leaked) when last
    # checked: at sign-in, the only time the plain password is seen. Cleared by
    # changing it.
    password_weak: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    @property
    def has_2fa(self) -> bool:
        return self.mfa_email or self.totp_secret is not None

    @property
    def mfa_setup_required(self) -> bool:
        """2FA is required for admins: until set up, they can only reach the setup."""
        return self.role == "admin" and not self.has_2fa

    @property
    def password_change_required(self) -> bool:
        """Admins with a weak password must change it before anything else."""
        return self.role == "admin" and self.password_weak

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.email} ({self.role})>"


class UserSettings(Base):
    """
    One row per user (created on first save; missing = all defaults). Background
    work (alerts, digest) reads the same settings as the user's pages.
    """

    __tablename__ = "user_settings"
    __table_args__ = (one_of("investing_style", InvestingStyle),)

    user_id: Mapped[int] = _user_fk(primary_key=True)
    investing_style: Mapped[InvestingStyle] = mapped_column(
        String(8), default="investor", server_default="investor", nullable=False
    )
    # NULL = not chosen yet: the `assistant_personal_data` server setting applies.
    assistant_personal_data: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assistant_save_chats: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    daily_digest: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Newest alert event the user has seen (only ever moves forward).
    alerts_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Documents validated by their Pydantic models (schemas.DisplaySettings,
    # schemas.TradingCosts); NULL = never saved (defaults apply).
    display: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trading_costs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = _updated_at()


class RecoveryCode(Base):
    """A single-use backup code for 2FA (keyed hash only: services/crypto.py)."""

    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = _user_fk(index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created_at()
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class MfaChallenge(Base):
    """
    A pending second step: after the password at sign-in (`purpose="login"`,
    found by its token), or confirming email as a 2FA method ("enroll_email").
    Holds the emailed code's keyed hash and counts wrong attempts.
    """

    __tablename__ = "mfa_challenges"
    __table_args__ = (one_of("purpose", MfaPurpose),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    user_id: Mapped[int] = _user_fk(index=True)
    purpose: Mapped[MfaPurpose] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class TrustedDevice(Base):
    """A browser that skips the 2FA step for a while (cookie token, hash stored)."""

    __tablename__ = "trusted_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = _user_fk(index=True)
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class UserSession(Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = _user_fk(index=True)
    created_at: Mapped[datetime] = _created_at()
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


class Invite(Base):
    """A one-time sign-up link for an email address (only the token's hash is stored)."""

    __tablename__ = "invites"
    __table_args__ = (one_of("role", Role),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    role: Mapped[Role] = mapped_column(String(8), default="user", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class PasswordReset(Base):
    """A one-time password-reset link (only the token's hash is stored)."""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = _user_fk(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


# --------------------------------------------------------------------------- #
# Market data
# --------------------------------------------------------------------------- #
class Stock(Base):
    """A listed company. `ticker` is the IDX code ("BBCA"), the key every table uses."""

    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # User-pinned symbols added to the high-frequency (intraday) sync set.
    tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # From the IDX listing (services/idx_listing): board ("Main", "Development",
    # "Acceleration", "Watchlist" = special monitoring), listing date, official shares.
    listing_board: Mapped[str | None] = mapped_column(String(24), nullable=True)
    listed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    idx_shares: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[datetime] = _created_at()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Stock {self.ticker}>"


class SyncState(Base):
    """
    When a per-stock background job last handled a stock: `listing` (seen in the
    IDX listing), `history_backfill` (DAILY_HISTORY_YEARS of bars stored),
    `full_history` (whole history fetched for a chart), `splits` (split history
    checked), `fundamentals` (last "sync missing" attempt, so tickers without
    statements rotate to the back of the queue). No row = never done.
    """

    __tablename__ = "sync_state"
    __table_args__ = (one_of("job", SyncJob),)

    ticker: Mapped[str] = _stock_fk(primary_key=True)
    job: Mapped[SyncJob] = mapped_column(String(20), primary_key=True)
    done_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class MarketIndex(Base):
    """An IDX index (the catalog: market/indices.py) and its latest value."""

    __tablename__ = "indices"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    last: Mapped[float | None] = mapped_column(Double, nullable=True)
    previous_close: Mapped[float | None] = mapped_column(Double, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # When the provider's full history was fetched (indices that have one).
    full_history_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<MarketIndex {self.code} {self.last}>"


class StockIndex(Base):
    """A stock's membership of an index (a stock can be in several)."""

    __tablename__ = "stock_indices"

    index_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("indices.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    ticker: Mapped[str] = _stock_fk(primary_key=True, index=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<StockIndex {self.ticker} @ {self.index_code}>"


class DailyBar(Base):
    """
    One trading day of a stock: the provider's official bar, or during the
    session a provisional one rolled up from today's 1-minute bars (market/sync).
    """

    __tablename__ = "daily_bars"
    __table_args__ = (
        # Every stock on/after a day (freshness checks, data health).
        Index("ix_daily_bars_day", "day"),
        {"sqlite_with_rowid": False},
    )

    ticker: Mapped[str] = _stock_fk(primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Double, nullable=False)
    high: Mapped[float] = mapped_column(Double, nullable=False)
    low: Mapped[float] = mapped_column(Double, nullable=False)
    close: Mapped[float] = mapped_column(Double, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<DailyBar {self.ticker} {self.day} {self.close}>"


class IntradayBar(Base):
    """A 1-minute bar; older than `intraday_retention_days` is pruned daily."""

    __tablename__ = "intraday_bars"
    __table_args__ = (
        Index("ix_intraday_bars_timestamp", "timestamp"),
        {"sqlite_with_rowid": False},
    )

    ticker: Mapped[str] = _stock_fk(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    open: Mapped[float] = mapped_column(Double, nullable=False)
    high: Mapped[float] = mapped_column(Double, nullable=False)
    low: Mapped[float] = mapped_column(Double, nullable=False)
    close: Mapped[float] = mapped_column(Double, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<IntradayBar {self.ticker} {self.timestamp} {self.close}>"


class StockQuote(Base):
    """
    A stock's latest daily close and the one before, kept current by the price
    sync (market/quotes.py). Derived from `daily_bars` and rebuilt on startup.
    """

    __tablename__ = "stock_quotes"

    ticker: Mapped[str] = _stock_fk(primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[float] = mapped_column(Double, nullable=False)
    prev_close: Mapped[float | None] = mapped_column(Double, nullable=True)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Fundamental(Base):
    """
    One row per (ticker, fiscal year). Monetary values are stored converted to
    IDR (`financial_currency` records what the statements reported in), in raw
    units. Ratios (PBV, RoE) are computed at read time from the latest price.
    """

    __tablename__ = "fundamentals"
    __table_args__ = (
        UniqueConstraint("ticker", "fiscal_year"),
        one_of("source", FundamentalSource),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = _stock_fk()
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    financial_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    total_shares: Mapped[float | None] = mapped_column(Double, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Double, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_liabilities: Mapped[float | None] = mapped_column(Double, nullable=True)
    equity: Mapped[float | None] = mapped_column(Double, nullable=True)
    source: Mapped[FundamentalSource] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = _updated_at()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Fundamental {self.ticker} {self.fiscal_year}>"


class StockProfile(Base):
    """
    Company profile and point-in-time metrics from the provider (one row per
    stock); fallbacks for the recommendation engine and for display.
    """

    __tablename__ = "stock_profiles"

    ticker: Mapped[str] = _stock_fk(primary_key=True)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(96), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website: Mapped[str | None] = mapped_column(String(160), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(48), nullable=True)
    # Board / management: [{name, title}, ...] from the provider profile.
    officers: Mapped[list[dict[str, str | None]] | None] = mapped_column(JSON, nullable=True)
    trailing_pe: Mapped[float | None] = mapped_column(Double, nullable=True)
    profit_margin: Mapped[float | None] = mapped_column(Double, nullable=True)
    revenue_growth: Mapped[float | None] = mapped_column(Double, nullable=True)
    earnings_growth: Mapped[float | None] = mapped_column(Double, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Double, nullable=True)
    beta: Mapped[float | None] = mapped_column(Double, nullable=True)
    updated_at: Mapped[datetime] = _updated_at()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<StockProfile {self.ticker} ({self.sector})>"


class Dividend(Base):
    """A historical cash dividend (ex-date + amount per share)."""

    __tablename__ = "dividends"
    __table_args__ = (CheckConstraint("amount >= 0", name="amount_not_negative"),)

    ticker: Mapped[str] = _stock_fk(primary_key=True)
    ex_date: Mapped[date] = mapped_column(Date, primary_key=True)
    amount: Mapped[float] = mapped_column(Double, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Dividend {self.ticker} {self.ex_date} {self.amount}>"


class Split(Base):
    """A stock split. `ratio` = new shares per old share (5.0 means 5-for-1)."""

    __tablename__ = "splits"
    __table_args__ = (CheckConstraint("ratio > 0", name="ratio_positive"),)

    ticker: Mapped[str] = _stock_fk(primary_key=True)
    ex_date: Mapped[date] = mapped_column(Date, primary_key=True)
    ratio: Mapped[float] = mapped_column(Double, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Split {self.ticker} {self.ex_date} x{self.ratio}>"


class IndexBar(Base):
    """Daily bar of an IDX index: provider history, or the app's own daily closes."""

    __tablename__ = "index_bars"

    code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("indices.code", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Double, nullable=True)
    high: Mapped[float | None] = mapped_column(Double, nullable=True)
    low: Mapped[float | None] = mapped_column(Double, nullable=True)
    close: Mapped[float] = mapped_column(Double, nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<IndexBar {self.code} {self.day} {self.close}>"


class RatingSnapshot(Base):
    """
    The rating each stock had at a day's close, per investing style: the live
    track record (services/track_record.py) compares it with what the price did
    next. Written once per trading day; shared market data, not per user.
    """

    __tablename__ = "rating_snapshots"
    __table_args__ = (one_of("style", InvestingStyle), one_of("rating", Rating))

    style: Mapped[InvestingStyle] = mapped_column(String(8), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    ticker: Mapped[str] = _stock_fk(primary_key=True)
    rating: Mapped[Rating] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Double, nullable=False)
    # Traded >= recommendation_min_traded_value then (the backtest's "liquid").
    liquid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RatingSnapshot {self.day} {self.style} {self.ticker} {self.rating}>"


# --------------------------------------------------------------------------- #
# Per-user data
# --------------------------------------------------------------------------- #
class Watchlist(Base):
    """A ticker the user chose to follow."""

    __tablename__ = "watchlist"

    user_id: Mapped[int] = _user_fk(primary_key=True)
    ticker: Mapped[str] = _stock_fk(primary_key=True, index=True)
    added_at: Mapped[datetime] = _created_at()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Watchlist {self.user_id} {self.ticker}>"


class Transaction(Base):
    """A buy/sell of a stock, used to derive the portfolio. Quantities are whole
    shares as traded; splits are applied when reading (services/corporate_actions)."""

    __tablename__ = "transactions"
    __table_args__ = (
        one_of("side", TradeSide),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("fees >= 0", name="fees_not_negative"),
        Index("ix_transactions_user_id_trade_date", "user_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = _user_fk()
    ticker: Mapped[str] = _stock_fk(index=True)
    side: Mapped[TradeSide] = mapped_column(String(4), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price: Mapped[float] = mapped_column(Double, nullable=False)
    fees: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = _created_at()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Transaction {self.side} {self.quantity} {self.ticker}@{self.price}>"


class Alert(Base):
    """A user-defined alert rule on a ticker."""

    __tablename__ = "alerts"
    __table_args__ = (one_of("type", AlertType),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = _user_fk(index=True)
    ticker: Mapped[str] = _stock_fk(index=True)
    type: Mapped[AlertType] = mapped_column(String(16), nullable=False)
    threshold: Mapped[float | None] = mapped_column(Double, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = _created_at()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Alert {self.ticker} {self.type} {self.threshold}>"


class AlertEvent(Base):
    """A triggered alert (kept for the in-app notification list)."""

    __tablename__ = "alert_events"
    __table_args__ = (Index("ix_alert_events_user_id_triggered_at", "user_id", "triggered_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = _user_fk()
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = _stock_fk(index=True)
    triggered_at: Mapped[datetime] = _created_at()
    value: Mapped[float | None] = mapped_column(Double, nullable=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AlertEvent {self.ticker} {self.triggered_at}>"


class RatingState(Base):
    """
    Last-seen rating per (user, ticker), for rating-change alerts. Per user
    because ratings depend on each user's investing style. Derived data: missing
    rows are rebuilt (as a baseline, without alerting) on the next evaluation.
    """

    __tablename__ = "rating_state"
    __table_args__ = (one_of("rating", Rating), one_of("strength", Strength))

    user_id: Mapped[int] = _user_fk(primary_key=True)
    ticker: Mapped[str] = _stock_fk(primary_key=True, index=True)
    rating: Mapped[Rating] = mapped_column(String(16), nullable=False)
    strength: Mapped[Strength | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = _updated_at()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RatingState {self.user_id} {self.ticker} {self.rating}>"


class AssistantChat(Base):
    """A saved assistant conversation. Deleted ASSISTANT_CHAT_DAYS after its last
    message, or right away when the user turns saving off
    (services/assistant_chats.py)."""

    __tablename__ = "assistant_chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = _user_fk(index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)  # the first question
    created_at: Mapped[datetime] = _created_at()
    # Time of the last message: what the list sorts by and what expiry counts from.
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)


class ChatMessage(Base):
    """One turn of a saved assistant chat."""

    __tablename__ = "assistant_chat_messages"
    __table_args__ = (one_of("role", ChatRole),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_chats.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[ChatRole] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tools_used: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = _created_at()
