"""
portfolio/schemas.py
--------------------
API models (Pydantic) for the portfolio and the watchlist.
"""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from market.schemas import DerivedMetrics, FundamentalOut, StockBase
from schemas import Schema, StockCode
from signals.schemas import RecommendationSummary

TradeSide = Literal["buy", "sell"]
# How shares were gained: a trade at the exchange, an exercised rights issue
# (HMETD: new shares at the exercise price), or bonus shares / a stock dividend
# (new shares for free: the count rises, the total cost stays).
TransactionKind = Literal["trade", "rights", "bonus"]
CashKind = Literal["deposit", "withdrawal"]
# Why a holding's note asks for attention (see portfolio/notes.py).
NoteFlag = Literal["review_due", "target_reached", "stop_hit"]


# --------------------------------------------------------------------------- #
# Portfolio
# --------------------------------------------------------------------------- #


class TransactionIn(Schema):
    """Payload for recording a buy/sell (whole shares, as traded), an exercised
    rights issue or bonus shares (both: shares received, so `side` is buy)."""

    ticker: StockCode
    side: TradeSide
    kind: TransactionKind = "trade"
    quantity: int = Field(gt=0)
    price: float = Field(ge=0)  # 0 only for bonus shares
    fees: float = Field(default=0.0, ge=0)
    trade_date: date
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _kind_rules(self) -> Self:
        if self.kind != "trade" and self.side != "buy":
            raise ValueError("Rights issues and bonus shares are shares received (side: buy)")
        if self.kind == "bonus":
            if self.price != 0 or self.fees != 0:
                raise ValueError("Bonus shares are free: price and fees 0")
        elif self.price <= 0:
            raise ValueError("Price must be above 0")
        return self


class TransactionOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    side: TradeSide
    kind: TransactionKind = "trade"
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
    # The chosen benchmark's (IHSG unless changed) cumulative change over the same days, %
    benchmark_pct: float | None = None


class WatchlistItemOut(StockBase):
    """A watchlist row: stock + latest price + latest fundamentals + ratios."""

    indices: list[str] = []
    added_at: datetime | None = None
    last_price: float | None = None
    change_percent: float | None = None
    fundamental: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()
    recommendation: RecommendationSummary | None = None
    # Just added: fundamentals are being fetched in the background (re-read the
    # watchlist in a few seconds for them).
    syncing: bool = False


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
    # The user's limits behind the warnings (Settings → Investing), in %.
    stock_limit_pct: float
    sector_limit_pct: float


class DividendMonthOut(Schema):
    """One month's dividends, net of tax: received (by ex-date) and expected."""

    month: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2026-11"])
    received: float
    expected: float


class DividendIncomeOut(Schema):
    """Net dividend income per month: the last 12 received, the next 6 expected."""

    months: list[DividendMonthOut]
    current_month: str
    received_12m: float
    expected_6m: float
    dividend_tax_pct: float


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


# --------------------------------------------------------------------------- #
# Tax summary (SPT Tahunan)
# --------------------------------------------------------------------------- #


class TaxHoldingOut(Schema):
    """A position on the year's last day, in the shares held then."""

    ticker: str
    name: str
    shares: float
    acquired_year: int  # when the position (since it was last empty) was first bought
    cost: float  # acquisition cost (harga perolehan), buy fees included
    close: float | None  # the year's last close, in the prices of then
    market_value: float | None


class TaxSaleOut(Schema):
    """One ticker's sales in the year."""

    ticker: str
    name: str
    shares: float
    proceeds: float  # gross sale value (shares x price)
    sales_tax: float  # the 0.1% final tax on it, withheld by the broker
    fees: float  # everything recorded on the sales (that tax included)
    realized_pl: float


class TaxDividendOut(Schema):
    """One cash dividend received in the year (by ex-date)."""

    ticker: str
    name: str
    ex_date: date
    shares: float
    per_share: float
    gross: float
    tax: float
    net: float


class TaxTotals(Schema):
    cost: float
    market_value: float
    proceeds: float
    sales_tax: float
    realized_pl: float
    dividends_gross: float
    dividends_tax: float
    dividends_net: float


class TaxSummaryOut(Schema):
    year: int
    as_of: date  # 31 December, or today while the year is running
    final: bool  # the year has ended
    years: list[int]  # years with transactions, newest first
    dividend_tax_pct: float
    holdings: list[TaxHoldingOut]
    sales: list[TaxSaleOut]
    dividends: list[TaxDividendOut]
    totals: TaxTotals


# --------------------------------------------------------------------------- #
# Cash (the investor's RDN account)
# --------------------------------------------------------------------------- #


class CashMovementIn(Schema):
    """Money moved into (deposit) or out of (withdrawal) the trading account."""

    kind: CashKind
    amount: float = Field(gt=0, le=1e15)
    day: date
    note: str | None = Field(default=None, max_length=255)


class CashMovementOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: CashKind
    amount: float
    day: date
    note: str | None = None


class CashOut(Schema):
    """The cash balance derived from deposits, withdrawals, trades and dividends,
    and the return on the money put in."""

    movements: list[CashMovementOut]  # newest first
    tracked: bool  # any deposits / withdrawals recorded
    available: float  # cash usable now
    settling: float  # sale proceeds not yet settled (T+2)
    settles_on: date | None  # when the last of them arrives
    balance: float  # available + settling
    net_deposits: float  # deposits - withdrawals
    market_value: float  # shares at the last price
    account_value: float  # market value + balance
    gain: float  # account value - net deposits
    gain_pct: float | None  # of net deposits
    annual_return_pct: float | None  # money-weighted, once a year of history
    since: date | None  # first deposit


# --------------------------------------------------------------------------- #
# Holding notes
# --------------------------------------------------------------------------- #


class HoldingNoteIn(Schema):
    """Why a stock was bought and when to look again. Prices are per share, as
    they are now (a later split is not applied to them)."""

    thesis: str | None = Field(default=None, max_length=2000)
    target: float | None = Field(default=None, gt=0)
    stop: float | None = Field(default=None, gt=0)
    review_on: date | None = None

    @model_validator(mode="after")
    def _stop_below_target(self) -> Self:
        if self.target is not None and self.stop is not None and self.stop >= self.target:
            raise ValueError("The stop must be below the target")
        return self


class HoldingNoteOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    thesis: str | None = None
    target: float | None = None
    stop: float | None = None
    review_on: date | None = None
    updated_at: datetime
    last_price: float | None = None
    flags: list[NoteFlag] = Field(default_factory=list[NoteFlag])
