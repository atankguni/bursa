"""
signals/schemas.py
------------------
API models (Pydantic) for signals.
"""

from datetime import date
from typing import Literal

from schemas import InvestingStyle, Schema

# "batch" = one capped run; "all" = paced batches until every stock is tried.
SyncMode = Literal["batch", "all"]


# Recommendation rating codes (the UI shows labels: signals/recommendation
# RATING_LABELS) and conviction, best first.
Rating = Literal["Strong Buy", "Buy", "Hold", "Reduce", "Avoid"]


Strength = Literal["Weak", "Moderate", "Strong", "Very Strong"]


class RecommendationSummary(Schema):
    """Compact recommendation, attached to stock + watchlist rows."""

    score: float
    rating: Rating
    strength: Strength


class ScreenerRow(Schema):
    ticker: str
    name: str
    indices: list[str] = []
    sector: str | None = None
    price: float | None = None
    change_percent: float | None = None
    pbv: float | None = None
    roe: float | None = None
    score: float | None = None
    rating: Rating | None = None
    strength: Strength | None = None
    has_fundamentals: bool = False
    board: str | None = None


class ScreenerPage(Schema):
    """One page of screener results plus the total match count (for pagination)."""

    items: list[ScreenerRow]
    total: int
    limit: int
    offset: int


class SyncStatusOut(Schema):
    """Progress of the background 'sync missing data' job."""

    running: bool
    mode: SyncMode = "batch"
    note: str | None = None
    total: int = 0
    done: int = 0
    remaining: int = 0
    last_error: str | None = None
    # Stocks that still have no fundamentals (across the whole universe).
    missing: int = 0


class SyncStartOut(Schema):
    """Response of starting a screener sync."""

    running: bool
    queued: int = 0
    total: int = 0
    remaining: int = 0


# --------------------------------------------------------------------------- #
# Valuation & dividends
# --------------------------------------------------------------------------- #


class ValuationOut(Schema):
    ticker: str
    pbv: float | None = None
    pbv_min: float | None = None
    pbv_max: float | None = None
    pbv_percentile: float | None = None
    roe: float | None = None
    roe_percentile: float | None = None
    years: list[int] = []
    window_days: int = 0


# --------------------------------------------------------------------------- #
# Recommendation
# --------------------------------------------------------------------------- #


class FactorOut(Schema):
    """One scored factor: raw value + cross-sectional percentile score."""

    name: str
    value: float | None = None
    score: float | None = None   # 0-100 percentile (higher = better)
    label: str = ""              # human-readable value


class CategoryOut(Schema):
    """A weighted group of factors."""

    name: str
    weight: float
    score: float | None = None


class RecommendationOut(Schema):
    """Full buy-signal breakdown for one ticker."""

    ticker: str
    score: float                 # 0-100 composite
    rating: Rating
    strength: Strength
    coverage: float              # fraction of factors with data
    categories: list[CategoryOut] = []
    reasons: list[str] = []
    disclaimer: str = ""
    style: InvestingStyle = "investor"  # which model produced this score


class RatingRecordOut(Schema):
    rating: Rating
    n: int           # stock-dates with this rating
    beat: float      # share that beat that date's median stock (0.5 = coin flip)


class BacktestRecordOut(Schema):
    start: str                   # first / last as-of date (YYYY-MM-DD)
    end: str
    universe: str                # which stocks were judged, in words
    ic: float                    # mean rank correlation of score vs. later return
    years: dict[str, float] = {}  # the same, per calendar year
    ratings: list[RatingRecordOut] = []
    generated: str = ""


class LiveRecordOut(Schema):
    since: date | None = None    # first recorded day
    days: int = 0                # days recorded
    matured_days: int = 0        # of which the horizon has passed
    ready_on: date | None = None  # roughly when the first result arrives
    ratings: list[RatingRecordOut] = []


class TrackRecordOut(Schema):
    """How past ratings of this style did over its main horizon."""

    style: InvestingStyle
    horizon: str                 # "3m" / "4w"
    backtest: BacktestRecordOut | None = None
    live: LiveRecordOut = LiveRecordOut()
