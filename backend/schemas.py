"""
schemas.py
----------
Pydantic v2 response models for the public API surface.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StockBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str


class RecommendationSummary(BaseModel):
    """Compact recommendation, attached to stock + watchlist rows."""

    score: float
    rating: str
    strength: str


class MarketStatusOut(BaseModel):
    """Current IDX trading state for the navbar indicator."""

    is_open: bool
    session: str
    timezone: str
    server_time: datetime
    next_change_at: datetime | None = None
    next_change_label: str = ""


class ProviderInfo(BaseModel):
    """A registered market-data provider and what it supports."""

    name: str
    capabilities: list[str]


class ProviderStat(BaseModel):
    """Lightweight outbound-call metrics per provider."""

    calls: int = 0
    calls_today: int = 0
    errors: int = 0
    last_error: str | None = None
    last_call_at: float | None = None


class ProvidersOut(BaseModel):
    """Active data providers (price + fundamentals are selected separately)."""

    price: str
    fundamentals: str
    available: list[ProviderInfo]
    metrics: dict[str, ProviderStat] = {}


class StatusOut(BaseModel):
    """Global status for the app footer."""

    server_time: datetime
    timezone: str
    session: str
    last_sync: datetime | None = None
    stocks_tracked: int = 0
    providers: dict[str, str] = {}
    calls_today: dict[str, int] = {}
    lot_size: int = 100


# --------------------------------------------------------------------------- #
# Portfolio
# --------------------------------------------------------------------------- #


class TransactionIn(BaseModel):
    """Payload for recording a buy/sell."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(default=0.0, ge=0)
    trade_date: date
    note: str | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    side: str
    quantity: float
    price: float
    fees: float
    trade_date: date
    note: str | None = None


class HoldingOut(BaseModel):
    """A current position with average-cost P/L."""

    ticker: str
    name: str
    quantity: float
    avg_cost: float
    price: float | None = None
    market_value: float | None = None
    invested: float
    unrealized_pl: float | None = None
    unrealized_pl_pct: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    weight: float | None = None
    projected_income: float | None = None


class PortfolioTotals(BaseModel):
    invested: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float | None = None
    day_change: float
    day_change_pct: float | None = None
    realized_pl: float
    projected_income: float = 0.0


class PortfolioOut(BaseModel):
    totals: PortfolioTotals
    holdings: list[HoldingOut]


class EquityPoint(BaseModel):
    date: date
    value: float


# --------------------------------------------------------------------------- #
# Screener / search / market overview
# --------------------------------------------------------------------------- #


class SearchResultOut(BaseModel):
    symbol: str
    name: str
    exchange: str = ""
    type: str = ""


class TrackStockIn(BaseModel):
    ticker: str
    name: str | None = None


class ScreenerRow(BaseModel):
    ticker: str
    name: str
    indices: list[str] = []
    sector: str | None = None
    price: float | None = None
    change_percent: float | None = None
    pbv: float | None = None
    roe: float | None = None
    score: float | None = None
    rating: str | None = None
    strength: str | None = None


class SyncStatusOut(BaseModel):
    """Progress of the background 'sync missing data' job."""

    running: bool
    total: int = 0
    done: int = 0
    remaining: int = 0
    last_error: str | None = None


class SyncStartOut(BaseModel):
    """Response of starting a screener sync."""

    running: bool
    queued: int = 0
    total: int = 0
    remaining: int = 0


class MoverOut(BaseModel):
    ticker: str
    name: str
    price: float | None = None
    change_percent: float | None = None


class SectorOut(BaseModel):
    sector: str
    count: int
    avg_change_percent: float


class MarketOverviewOut(BaseModel):
    up: int
    down: int
    flat: int
    top_gainers: list[MoverOut]
    top_losers: list[MoverOut]
    sectors: list[SectorOut]


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #

AlertType = Literal["price_above", "price_below", "pct_change", "rating_change"]


class AlertIn(BaseModel):
    ticker: str
    type: AlertType
    threshold: float | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    type: str
    threshold: float | None = None
    active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime


class AlertEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    ticker: str
    triggered_at: datetime
    value: float | None = None
    message: str


# --------------------------------------------------------------------------- #
# Valuation & dividends
# --------------------------------------------------------------------------- #


class ValuationOut(BaseModel):
    ticker: str
    pbv: float | None = None
    pbv_min: float | None = None
    pbv_max: float | None = None
    pbv_percentile: float | None = None
    roe: float | None = None
    roe_percentile: float | None = None
    years: list[int] = []
    window_days: int = 0


class DividendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ex_date: date
    amount: float


class DividendSummary(BaseModel):
    ticker: str
    trailing_dps: float = 0.0
    yield_percent: float | None = None
    history: list[DividendOut] = []


class OfficerOut(BaseModel):
    name: str
    title: str | None = None


class CompanyOut(BaseModel):
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

    id: int
    indices: list[str] = []
    last_price: float | None = None
    previous_close: float | None = None
    change: float | None = None          # absolute point change vs prev close
    change_percent: float | None = None  # percentage change vs prev close
    volume: int | None = None
    updated_at: datetime | None = None
    recommendation: RecommendationSummary | None = None


class CatalogRow(BaseModel):
    """A row in the full IDX catalog browse list."""

    ticker: str
    name: str
    tracked: bool = False
    indices: list[str] = []
    last_price: float | None = None
    change_percent: float | None = None


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


# --------------------------------------------------------------------------- #
# Recommendation
# --------------------------------------------------------------------------- #


class FactorOut(BaseModel):
    """One scored factor: raw value + cross-sectional percentile score."""

    name: str
    value: float | None = None
    score: float | None = None   # 0-100 percentile (higher = better)
    label: str = ""              # human-readable value


class CategoryOut(BaseModel):
    """A weighted group of factors."""

    name: str
    weight: float
    score: float | None = None


class RecommendationOut(BaseModel):
    """Full buy-signal breakdown for one ticker."""

    ticker: str
    score: float                 # 0-100 composite
    rating: str                  # Strong Buy / Buy / Hold / Reduce / Avoid
    strength: str                # Weak / Moderate / Strong / Very Strong
    coverage: float              # fraction of factors with data
    categories: list[CategoryOut] = []
    reasons: list[str] = []
    disclaimer: str = ""


class WatchlistItemOut(StockBase):
    """A watchlist row: stock + latest price + latest fundamentals + ratios."""

    id: int
    indices: list[str] = []
    added_at: datetime | None = None
    last_price: float | None = None
    change_percent: float | None = None
    fundamental: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()
    recommendation: RecommendationSummary | None = None


class FundamentalsResponse(BaseModel):
    """Yearly fundamentals series + derived metrics for one ticker."""

    ticker: str
    name: str
    yearly: list[FundamentalOut]
    latest: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()
