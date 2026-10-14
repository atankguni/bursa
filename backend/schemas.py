"""
schemas.py
----------
Pydantic v2 response models for the public API surface.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StockBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str


class StockOut(StockBase):
    """A tracked stock enriched with its latest quote + daily change."""

    id: int
    indices: list[str] = []
    last_price: float | None = None
    previous_close: float | None = None
    change: float | None = None          # absolute point change vs prev close
    change_percent: float | None = None  # percentage change vs prev close
    volume: int | None = None
    updated_at: datetime | None = None


class PricePoint(BaseModel):
    """A single OHLCV bar for charting."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistory(BaseModel):
    """Full history payload for one ticker."""

    ticker: str
    name: str
    indices: list[str]
    interval: str
    points: list[PricePoint]


class FundamentalOut(BaseModel):
    """One fiscal year of financial figures, converted to IDR (raw units)."""

    model_config = ConfigDict(from_attributes=True)

    fiscal_year: int
    financial_currency: str | None = None
    total_shares: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    equity: float | None = None


class DerivedMetrics(BaseModel):
    """Valuation ratios computed against the latest price."""

    market_cap: float | None = None
    book_value: float | None = None
    pbv: float | None = None   # price-to-book value
    roe: float | None = None   # return on equity (latest year, fraction)


class WatchlistItemOut(StockBase):
    """A watchlist row: stock + latest price + latest fundamentals + ratios."""

    id: int
    indices: list[str] = []
    added_at: datetime | None = None
    last_price: float | None = None
    change_percent: float | None = None
    fundamental: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()


class FundamentalsResponse(BaseModel):
    """Yearly fundamentals series + derived metrics for one ticker."""

    ticker: str
    name: str
    yearly: list[FundamentalOut]
    latest: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()
