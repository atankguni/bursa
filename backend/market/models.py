"""
market/models.py
----------------
Tables for market data (shared by every user). Conventions: models.py.
"""

from datetime import date, datetime

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
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from db.columns import created_at_column, stock_fk, updated_at_column
from db.types import UTCDateTime, one_of
from market.schemas import FundamentalSource, SyncJob


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
    # From the IDX listing (market/idx_listing): board ("Main", "Development",
    # "Acceleration", "Watchlist" = special monitoring), listing date, official shares.
    listing_board: Mapped[str | None] = mapped_column(String(24), nullable=True)
    listed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    idx_shares: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[datetime] = created_at_column()

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

    ticker: Mapped[str] = stock_fk(primary_key=True)
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
    ticker: Mapped[str] = stock_fk(primary_key=True, index=True)

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

    ticker: Mapped[str] = stock_fk(primary_key=True)
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

    ticker: Mapped[str] = stock_fk(primary_key=True)
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

    ticker: Mapped[str] = stock_fk(primary_key=True)
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
    ticker: Mapped[str] = stock_fk()
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    financial_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    total_shares: Mapped[float | None] = mapped_column(Double, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Double, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_assets: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_liabilities: Mapped[float | None] = mapped_column(Double, nullable=True)
    equity: Mapped[float | None] = mapped_column(Double, nullable=True)
    source: Mapped[FundamentalSource] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = updated_at_column()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Fundamental {self.ticker} {self.fiscal_year}>"


class StockProfile(Base):
    """
    Company profile and point-in-time metrics from the provider (one row per
    stock); fallbacks for the recommendation engine and for display.
    """

    __tablename__ = "stock_profiles"

    ticker: Mapped[str] = stock_fk(primary_key=True)
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
    updated_at: Mapped[datetime] = updated_at_column()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<StockProfile {self.ticker} ({self.sector})>"


class Dividend(Base):
    """A historical cash dividend (ex-date + amount per share)."""

    __tablename__ = "dividends"
    __table_args__ = (CheckConstraint("amount >= 0", name="amount_not_negative"),)

    ticker: Mapped[str] = stock_fk(primary_key=True)
    ex_date: Mapped[date] = mapped_column(Date, primary_key=True)
    amount: Mapped[float] = mapped_column(Double, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Dividend {self.ticker} {self.ex_date} {self.amount}>"


class Split(Base):
    """A stock split. `ratio` = new shares per old share (5.0 means 5-for-1)."""

    __tablename__ = "splits"
    __table_args__ = (CheckConstraint("ratio > 0", name="ratio_positive"),)

    ticker: Mapped[str] = stock_fk(primary_key=True)
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
