"""
models.py
---------
SQLAlchemy 2.0 ORM models.

`Stock`       -> static metadata for every tracked IDX ticker.
`StockIndex`  -> many-to-many membership: which index a ticker belongs to
                 (a stock can be in several indices at once).
`StockPrice`  -> OHLCV rows (both daily and intraday bars).

The `interval` column ("1d" for daily, "1m" for intraday) keeps the two series
separate so a chart never mixes a daily close with a minute close. It is not in
the original field list but is required for correct charting.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
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
