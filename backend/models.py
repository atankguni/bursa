"""
models.py
---------
SQLAlchemy 2.0 ORM models.

`Stock`       -> static metadata for every tracked IDX ticker.
`StockIndex`  -> many-to-many membership: which index a ticker belongs to
                 (a stock can be in several indices at once).
`StockPrice`  -> OHLCV rows (both daily and intraday bars).
`User`        -> accounts (+ UserSession, Invite, PasswordReset for auth).
`Watchlist`   -> a user's hand-picked tickers to follow.
`Fundamental` -> yearly financial statement figures per ticker.

Numbers use `Double` (8-byte), not `Float`: MySQL maps Float to a 4-byte FLOAT,
which would round large IDR figures (assets, revenue) to ~7 significant digits.

The `interval` column ("1d" for daily, "1m" for intraday) keeps the two series
separate so a chart never mixes a daily close with a minute close. It is not in
the original field list but is required for correct charting.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class User(Base):
    """An account. Invite-only: created by accepting an Invite."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Stored lower-cased (services/auth.normalize_email).
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(8), default="user", nullable=False)  # user|admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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

    @property
    def has_2fa(self) -> bool:
        return self.mfa_email or self.totp_secret is not None

    @property
    def mfa_setup_required(self) -> bool:
        """2FA is required for admins: until set up, they can only reach the setup."""
        return self.role == "admin" and not self.has_2fa

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.email} ({self.role})>"


class RecoveryCode(Base):
    """A single-use backup code for 2FA (keyed hash only: services/crypto.py)."""

    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MfaChallenge(Base):
    """
    A pending second step: after the password at sign-in (`purpose="login"`,
    found by its token), or confirming email as a 2FA method ("enroll_email").
    Holds the emailed code's keyed hash and counts wrong attempts.
    """

    __tablename__ = "mfa_challenges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TrustedDevice(Base):
    """A browser that skips the 2FA step for a while (cookie token, hash stored)."""

    __tablename__ = "trusted_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class UserSession(Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


class Invite(Base):
    """A one-time sign-up link for an email address (only the token's hash is stored)."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(8), default="user", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PasswordReset(Base):
    """A one-time password-reset link (only the token's hash is stored)."""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # User-pinned symbols added to the high-frequency (intraday) sync set.
    tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # When the full daily history (since listing) was fetched on demand; the
    # regular sync only keeps ~1 year for the whole catalog.
    full_history_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # From the IDX listing (services/idx_listing): board ("Main", "Development",
    # "Acceleration", "Watchlist" = special monitoring), listing date, official shares.
    listing_board: Mapped[str | None] = mapped_column(String(24), nullable=True)
    listed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    idx_shares: Mapped[float | None] = mapped_column(Double, nullable=True)
    idx_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Last time this stock's split history was checked (services/corporate_actions).
    splits_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Last screener "sync missing" attempt, so tickers the provider has no
    # statements for rotate to the back of the queue instead of blocking it.
    fundamentals_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Stock {self.ticker}>"


class StockIndex(Base):
    """Association row linking a ticker to an index (LQ45, IDX30, JII, ...)."""

    __tablename__ = "stock_indices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    index_name: Mapped[str] = mapped_column(String(40), index=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "index_name", name="uq_ticker_index"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<StockIndex {self.ticker} @ {self.index_name}>"


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    interval: Mapped[str] = mapped_column(String(8), default="1d", nullable=False)
    open: Mapped[float] = mapped_column(Double, nullable=False)
    high: Mapped[float] = mapped_column(Double, nullable=False)
    low: Mapped[float] = mapped_column(Double, nullable=False)
    close: Mapped[float] = mapped_column(Double, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # One row per (ticker, timestamp, interval); enables idempotent upserts.
    __table_args__ = (
        UniqueConstraint("ticker", "timestamp", "interval", name="uq_price_bar"),
        Index("ix_price_ticker_interval_ts", "ticker", "interval", "timestamp"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<StockPrice {self.ticker} {self.timestamp} {self.close}>"


class Watchlist(Base):
    """A ticker the user chose to follow."""

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Owner. Nullable only for rows from before accounts existed; the first admin
    # claims those (services/auth.claim_orphans). Every query filters on it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # (ticker, user_id), not (user_id, ticker): MySQL needs an index that starts
    # with `ticker` for its foreign key while migration 0002 swaps the old index.
    __table_args__ = (UniqueConstraint("ticker", "user_id", name="uq_watchlist_user_ticker"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Watchlist {self.ticker}>"


class Fundamental(Base):
    """
    One row per (ticker, fiscal year). Values are in the reporting currency
    (IDR for IDX) and raw units. Derived ratios (PBV, RoE) are computed at read
    time using the latest price, so they always stay fresh.
    """

    __tablename__ = "fundamentals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    # Reporting currency of the statement figures (e.g. "IDR", "USD"). All
    # monetary columns below are stored CONVERTED to IDR so ratios (PBV) are
    # valid; this column records what the source statements reported in.
    financial_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    total_shares: Mapped[float | None] = mapped_column(Double, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Double, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_liabilities: Mapped[float | None] = mapped_column(Double, nullable=True)
    equity: Mapped[float | None] = mapped_column(Double, nullable=True)
    # "statements" or "summary" (see market/providers/base.FundamentalRow);
    # NULL on rows written before the column existed = statements.
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("ticker", "fiscal_year", name="uq_fundamental_year"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Fundamental {self.ticker} {self.fiscal_year}>"


class StockProfile(Base):
    """
    Point-in-time market metrics from yfinance `.info` (one row per ticker).

    Used as fallbacks/convenience for the recommendation engine and for display.
    """

    __tablename__ = "stock_profiles"

    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
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
    officers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    trailing_pe: Mapped[float | None] = mapped_column(Double, nullable=True)
    profit_margin: Mapped[float | None] = mapped_column(Double, nullable=True)
    revenue_growth: Mapped[float | None] = mapped_column(Double, nullable=True)
    earnings_growth: Mapped[float | None] = mapped_column(Double, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Double, nullable=True)
    beta: Mapped[float | None] = mapped_column(Double, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<StockProfile {self.ticker} ({self.sector})>"


class Transaction(Base):
    """A buy/sell of a tracked stock, used to derive the portfolio."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Owner. Nullable only for rows from before accounts existed; the first admin
    # claims those (services/auth.claim_orphans). Every query filters on it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # "buy" | "sell"
    quantity: Mapped[float] = mapped_column(Double, nullable=False)
    price: Mapped[float] = mapped_column(Double, nullable=False)
    fees: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Transaction {self.side} {self.quantity} {self.ticker}@{self.price}>"


class Alert(Base):
    """A user-defined alert rule on a ticker."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Owner. Nullable only for rows from before accounts existed; the first admin
    # claims those (services/auth.claim_orphans). Every query filters on it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    # price_above | price_below | pct_change | rating_change
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold: Mapped[float | None] = mapped_column(Double, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Alert {self.ticker} {self.type} {self.threshold}>"


class AlertEvent(Base):
    """A triggered alert (kept for the in-app notification list)."""

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Owner. Nullable only for rows from before accounts existed; the first admin
    # claims those (services/auth.claim_orphans). Every query filters on it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True, nullable=False
    )
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

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    strength: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_rating_state"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RatingState {self.user_id} {self.ticker} {self.rating}>"


class Dividend(Base):
    """A historical cash dividend (ex-date + amount per share)."""

    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    ex_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Double, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "ex_date", name="uq_dividend"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Dividend {self.ticker} {self.ex_date} {self.amount}>"


class UserPreference(Base):
    """A server-side preference of one user (key/value, e.g. investing style)."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Owner. Nullable only for rows from before accounts existed; the first admin
    # claims those (services/auth.claim_orphans). Every query filters on it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    # Short values (a style name) or a JSON document (display settings).
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_preference"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<UserPreference {self.user_id} {self.key}={self.value}>"


class IndexQuote(Base):
    """Latest value of an IDX stock index (see market/indices.py)."""

    __tablename__ = "index_quotes"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    last: Mapped[float] = mapped_column(Double, nullable=False)
    previous_close: Mapped[float | None] = mapped_column(Double, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # When the provider's full history was fetched (indices that have one).
    full_history_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<IndexQuote {self.code} {self.last}>"


class IndexBar(Base):
    """Daily bar of an IDX index: provider history, or the app's own daily closes."""

    __tablename__ = "index_bars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Double, nullable=True)
    high: Mapped[float | None] = mapped_column(Double, nullable=True)
    low: Mapped[float | None] = mapped_column(Double, nullable=True)
    close: Mapped[float] = mapped_column(Double, nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (UniqueConstraint("code", "day", name="uq_index_bar"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<IndexBar {self.code} {self.day} {self.close}>"


class Split(Base):
    """A stock split. `ratio` = new shares per old share (5.0 means 5-for-1)."""

    __tablename__ = "splits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    ratio: Mapped[float] = mapped_column(Double, nullable=False)

    __table_args__ = (UniqueConstraint("ticker", "ex_date", name="uq_split"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Split {self.ticker} {self.ex_date} x{self.ratio}>"
