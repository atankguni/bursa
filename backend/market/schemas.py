"""
market/schemas.py
-----------------
API models (Pydantic) for market data (shared by every user).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict

from schemas import Schema, StockCode
from signals.schemas import RecommendationSummary

# IDX trading state (market/trading_clock).
MarketSession = Literal["pre_open", "open", "break", "closed"]


# Where a fundamentals row came from: yearly statement tables, or Yahoo's summary
# metrics for companies without statements (market/providers/base.FundamentalRow).
FundamentalSource = Literal["statements", "summary"]


# Per-stock background work whose last run is remembered (market.models.SyncState).
SyncJob = Literal["listing", "history_backfill", "full_history", "splits", "fundamentals"]


class StockBase(Schema):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    # IDX listing board; "Watchlist" = special monitoring (Papan Pemantauan Khusus).
    board: str | None = None


class MarketStatusOut(Schema):
    """Current IDX trading state for the navbar indicator."""

    is_open: bool
    session: MarketSession
    timezone: str
    server_time: datetime
    next_change_at: datetime | None = None
    next_change_label: str = ""


class ProviderInfo(Schema):
    """A registered market-data provider and what it supports."""

    name: str
    capabilities: list[str]


class ProviderStat(Schema):
    """Lightweight outbound-call metrics per provider."""

    calls: int = 0
    calls_today: int = 0
    errors: int = 0
    last_error: str | None = None
    last_call_at: float | None = None


class ProvidersOut(Schema):
    """Active data providers (price + fundamentals are selected separately)."""

    price: str
    fundamentals: str
    available: list[ProviderInfo]
    metrics: dict[str, ProviderStat] = {}


# --------------------------------------------------------------------------- #
# Screener / search / market overview
# --------------------------------------------------------------------------- #


class SearchResultOut(Schema):
    symbol: str
    name: str
    exchange: str = ""
    type: str = ""


class TrackStockIn(Schema):
    ticker: StockCode
    name: str | None = None


class MoverOut(Schema):
    ticker: str
    name: str
    price: float | None = None
    change_percent: float | None = None


class SectorOut(Schema):
    sector: str
    count: int
    avg_change_percent: float


class MarketOverviewOut(Schema):
    up: int
    down: int
    flat: int
    top_gainers: list[MoverOut]
    top_losers: list[MoverOut]
    sectors: list[SectorOut]


class DividendOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    ex_date: date
    amount: float


class DividendSummary(Schema):
    ticker: str
    trailing_dps: float = 0.0
    yield_percent: float | None = None
    history: list[DividendOut] = []


class OfficerOut(Schema):
    name: str
    title: str | None = None


class CompanyOut(Schema):
    """Company profile / board information for the detail modal."""

    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    employees: int | None = None
    website: str | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    officers: list[OfficerOut] = []


class StockOut(StockBase):
    """A tracked stock enriched with its latest quote + daily change."""

    indices: list[str] = []
    last_price: float | None = None
    previous_close: float | None = None
    change: float | None = None          # absolute point change vs prev close
    change_percent: float | None = None  # percentage change vs prev close
    volume: int | None = None
    updated_at: datetime | None = None
    recommendation: RecommendationSummary | None = None


class CatalogRow(Schema):
    """A row in the full IDX catalog browse list."""

    ticker: str
    name: str
    board: str | None = None
    tracked: bool = False
    indices: list[str] = []
    last_price: float | None = None
    change_percent: float | None = None


class CatalogPage(Schema):
    """One page of the catalog plus the total match count (for pagination)."""

    items: list[CatalogRow]
    total: int
    limit: int
    offset: int


class PricePoint(Schema):
    """A single OHLCV bar for charting."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class SplitOut(Schema):
    ex_date: date
    ratio: float


class StockHistory(Schema):
    """Full history payload for one ticker."""

    ticker: str
    name: str
    indices: list[str]
    interval: str
    points: list[PricePoint]
    splits: list[SplitOut] = []  # for chart markers


class FundamentalOut(Schema):
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
    source: str | None = None  # "statements" | "summary" (None = statements)


class DerivedMetrics(Schema):
    """Valuation ratios computed against the latest price."""

    market_cap: float | None = None
    book_value: float | None = None
    pbv: float | None = None   # price-to-book value
    roe: float | None = None   # return on equity (latest year, fraction)


class FundamentalsResponse(Schema):
    """Yearly fundamentals series + derived metrics for one ticker."""

    ticker: str
    name: str
    yearly: list[FundamentalOut]
    latest: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()


class IndexOut(Schema):
    """One IDX stock index (indeks saham) with its latest value."""

    code: str
    name: str
    group: str
    last: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    updated_at: datetime | None = None
    has_history: bool = False
    history_since: date | None = None


class IndexBarOut(Schema):
    """Daily index bar, shaped like PricePoint so the stock chart can draw it."""

    timestamp: date
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class IndexHistoryOut(Schema):
    code: str
    name: str
    has_history: bool
    points: list[IndexBarOut]
