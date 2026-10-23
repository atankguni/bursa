"""
portfolio/schemas.py
--------------------
API models (Pydantic) for the portfolio and the watchlist.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field

from market.schemas import DerivedMetrics, FundamentalOut, StockBase
from schemas import Schema, StockCode
from signals.schemas import RecommendationSummary

TradeSide = Literal["buy", "sell"]


# --------------------------------------------------------------------------- #
# Portfolio
# --------------------------------------------------------------------------- #


class TransactionIn(Schema):
    """Payload for recording a buy/sell (whole shares, as traded)."""

    ticker: StockCode
    side: TradeSide
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(default=0.0, ge=0)
    trade_date: date
    note: str | None = None


class TransactionOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    side: TradeSide
    quantity: float
    price: float
    fees: float
    trade_date: date
    note: str | None = None


class HoldingOut(Schema):
    """A current position with average-cost P/L."""

    ticker: str
    name: str
    board: str | None = None
    split_adjusted: bool = False  # some trades were re-expressed in post-split shares
    quantity: float
    avg_cost: float
    price: float | None = None  # None: no price yet (values use the average cost)
    market_value: float
    invested: float
    unrealized_pl: float
    unrealized_pl_pct: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    weight: float | None = None  # % of the portfolio's market value
    projected_income: float = 0.0  # a year of dividends at the trailing rate, after tax
    dividends_received: float = 0.0  # since the first trade, after tax


class PortfolioTotals(Schema):
    invested: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float | None = None
    day_change: float
    day_change_pct: float | None = None
    realized_pl: float
    projected_income: float = 0.0  # after dividend tax
    # Selling everything now would cost about this (sell fee + tax).
    exit_costs: float = 0.0
    # Cash dividends the trades were entitled to (held before the ex-date), after tax.
    dividends_received: float = 0.0
    # Unrealized P/L after exit costs + realized P/L + dividends received.
    total_return: float = 0.0


class PortfolioOut(Schema):
    totals: PortfolioTotals
    holdings: list[HoldingOut]


class EquityPoint(Schema):
    date: date
    value: float
    # Cumulative time-weighted return (%): performance with deposits/withdrawals
    # (buys/sells) taken out, so adding money doesn't count as profit. Dividends
    # (after tax) count as income on their ex-date.
    return_pct: float | None = None
    benchmark_pct: float | None = None  # IHSG cumulative change over the same days, %


class WatchlistItemOut(StockBase):
    """A watchlist row: stock + latest price + latest fundamentals + ratios."""

    indices: list[str] = []
    added_at: datetime | None = None
    last_price: float | None = None
    change_percent: float | None = None
    fundamental: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()
    recommendation: RecommendationSummary | None = None


class HoldingRiskOut(Schema):
    ticker: str
    weight: float
    sector: str
    beta: float | None = None


class SectorWeightOut(Schema):
    sector: str
    weight: float


class PortfolioRiskOut(Schema):
    """Concentration, sector exposure, beta vs IHSG, stress test, drawdown (all in %)."""

    holdings: list[HoldingRiskOut]
    sectors: list[SectorWeightOut]
    effective_holdings: float | None = None
    top_weight: float | None = None
    top3_weight: float | None = None
    beta: float | None = None
    stress_ihsg_pct: float
    stress_portfolio_pct: float | None = None
    last_day_portfolio_pct: float | None = None
    last_day_ihsg_pct: float | None = None
    max_drawdown_pct: float | None = None
    warnings: list[str] = []


class ExpectedDividendOut(Schema):
    """A projected (not announced) dividend, from last year's ex-date."""

    ticker: str
    name: str
    expected_ex_date: date
    based_on: date
    amount_per_share: float
    regular: bool
    shares_held: float | None = None
    expected_income: float | None = None
    in_portfolio: bool
    in_watchlist: bool
