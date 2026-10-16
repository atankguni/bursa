"""
models.py
---------
SQLAlchemy 2.0 ORM models.

`Stock`       -> static metadata for every tracked IDX ticker.
`StockIndex`  -> many-to-many membership: which index a ticker belongs to
                 (a stock can be in several indices at once).
`StockPrice`  -> OHLCV rows (both daily and intraday bars).
`Watchlist`   -> user's hand-picked tickers to follow.
`Fundamental` -> yearly financial statement figures per ticker.

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
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


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
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
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
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"),
        unique=True, index=True, nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

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
    total_shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    trailing_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    earnings_growth: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    beta: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<StockProfile {self.ticker} ({self.sector})>"


class Transaction(Base):
    """A buy/sell of a tracked stock, used to derive the portfolio."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # "buy" | "sell"
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
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
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    # price_above | price_below | pct_change | rating_change
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True, nullable=False
    )
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AlertEvent {self.ticker} {self.triggered_at}>"


class RatingState(Base):
    """Last-seen recommendation rating per ticker (for rating-change alerts)."""

    __tablename__ = "rating_state"

    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    strength: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RatingState {self.ticker} {self.rating}>"


class Dividend(Base):
    """A historical cash dividend (ex-date + amount per share)."""

    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker", ondelete="CASCADE"), index=True,
        nullable=False,
    )
    ex_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "ex_date", name="uq_dividend"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Dividend {self.ticker} {self.ex_date} {self.amount}>"


class Preference(Base):
    """A server-side user preference (key/value; this is a single-user app)."""

    __tablename__ = "preferences"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Preference {self.key}={self.value}>"
