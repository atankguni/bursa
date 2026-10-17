"""
services/recommendation.py
--------------------------
Explainable, cross-sectional buy-signal score, in two investing styles.

For each stock we compute a handful of factors, rank each factor as a
percentile WITHIN the rated universe (so scores are relative, not absolute),
average within categories, then take a weighted composite (0-100). The
composite maps to a rating and a conviction ("strength") that also accounts for
factor agreement and data coverage.

* investor (long term): quality, valuation, growth, momentum, health from
  yearly fundamentals + prices. Only stocks with fundamentals are rated.
* trader (swing, 1-4 weeks): stability, setup, pullback from daily prices.
  Any stock liquid enough to trade is rated, fundamentals or not.

Both models were chosen with scripts/evaluate_signals.py (point-in-time
backtest). Everything is transparent and testable — no black-box model.
"""

import logging
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import pstdev

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Fundamental, Stock, StockProfile
from schemas import CategoryOut, InvestingStyle, RecommendationOut
from services.prices import (
    daily_closes,
    fundamental_series,
    latest_daily,
    median_traded_value,
    profiles,
)

log = logging.getLogger("bursa.recommendation")

DISCLAIMER = (
    "Heuristic factor score from stored prices and yearly fundamentals — "
    "for personal reference only, not financial advice."
)

CATEGORY_ORDER = ["Quality", "Valuation", "Growth", "Momentum", "Health"]

# (key, category, direction, display, formatter) — direction is "higher"/"lower" is better.
FACTORS: list[tuple[str, str, str, str, str]] = [
    ("roe", "Quality", "higher", "RoE", "pct"),
    ("net_margin", "Quality", "higher", "Net margin", "pct"),
    ("pbv", "Valuation", "lower", "PBV", "ratio"),
    ("per", "Valuation", "lower", "PER", "ratio"),
    ("revenue_yoy", "Growth", "higher", "Revenue growth", "pct"),
    ("earnings_yoy", "Growth", "higher", "Earnings growth", "pct"),
    ("ret_3m", "Momentum", "higher", "3M return", "pct"),
    ("price_vs_sma50", "Momentum", "higher", "Price vs SMA50", "pct"),
    ("pos_52w", "Momentum", "higher", "52w position", "pct"),
    ("der", "Health", "lower", "Debt/Equity", "ratio"),
    ("equity_ratio", "Health", "higher", "Equity ratio", "pct"),
]
_FACTOR_KEYS = [f[0] for f in FACTORS]
# A stock needs at least one of these (they come from fundamentals) to be rated.
_FUNDAMENTAL_KEYS = [f[0] for f in FACTORS if f[1] in ("Quality", "Valuation")]
_BUY_RATINGS = ("Strong Buy", "Buy")

# factor key -> raw value (None when the input data is missing).
type RawFactors = dict[str, float | None]
type Factor = tuple[str, str, str, str, str]

TRADER_DISCLAIMER = (
    "Short-term (1-4 week) score from daily price behaviour — favours calm, "
    "orderly stocks over recent winners. Backtested in a falling market only; "
    "for personal reference, not financial advice."
)
TRADER_CATEGORY_ORDER = ["Stability", "Setup", "Pullback"]
TRADER_FACTORS: list[Factor] = [
    ("volatility_20d", "Stability", "lower", "20-day volatility", "pct"),
    ("from_high_20d", "Setup", "higher", "vs 20-day high", "pct"),
    ("from_low_20d", "Setup", "lower", "Above 20-day low", "pct"),
    ("ret_20d", "Pullback", "lower", "20-day return", "pct"),
]
_TRADER_KEYS = [f[0] for f in TRADER_FACTORS]


@dataclass(frozen=True)
class _StyleSpec:
    factors: list[Factor]
    categories: list[str]
    weights: Callable[[], dict[str, float]]  # read lazily so settings stay tunable
    disclaimer: str


_SPECS: dict[InvestingStyle, _StyleSpec] = {
    "investor": _StyleSpec(
        FACTORS, CATEGORY_ORDER, lambda: settings.recommendation_weights, DISCLAIMER
    ),
    "trader": _StyleSpec(
        TRADER_FACTORS,
        TRADER_CATEGORY_ORDER,
        lambda: settings.recommendation_trader_weights,
        TRADER_DISCLAIMER,
    ),
}


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def _div(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b


def _yoy(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / abs(prev)


def _momentum(closes: list[float]) -> dict[str, float | None]:
    out: dict[str, float | None] = {"ret_3m": None, "price_vs_sma50": None, "pos_52w": None}
    closes = closes[-252:]  # "52w" = one trading year, even if more history is stored
    if not closes:
        return out
    last = closes[-1]
    if len(closes) > 63 and closes[-64]:
        out["ret_3m"] = last / closes[-64] - 1
    window = closes[-50:]
    sma = sum(window) / len(window)
    if sma:
        out["price_vs_sma50"] = last / sma - 1
    hi, lo = max(closes), min(closes)
    if hi > lo:
        out["pos_52w"] = (last - lo) / (hi - lo)
    return out


def raw_factors(
    closes: list[float],
    funds: list[Fundamental],
    profile: StockProfile | None,
    price: float | None,
) -> RawFactors:
    """Compute the raw (un-normalised) factor values for one ticker."""
    raw: RawFactors = dict.fromkeys(_FACTOR_KEYS)
    latest = funds[-1] if funds else None

    if latest is not None:
        raw["net_margin"] = _div(latest.net_income, latest.revenue)
        shares = latest.total_shares
        market_cap = price * shares if price and shares else None
        book = None
        if latest.total_assets is not None and latest.total_liabilities is not None:
            book = latest.total_assets - latest.total_liabilities
        elif latest.equity is not None:
            book = latest.equity
        # Negative book value / equity is a red flag, not missing data: rank it
        # worst instead of dropping it (a negative D/E or a loss over negative
        # equity would otherwise read as a *good* ratio).
        raw["pbv"] = math.inf if book is not None and book <= 0 else _div(market_cap, book)
        if latest.equity is not None and latest.equity <= 0:
            raw["roe"] = -math.inf
            raw["der"] = math.inf
        else:
            raw["roe"] = _div(latest.net_income, latest.equity)
            raw["der"] = _div(latest.total_liabilities, latest.equity)
        eps = _div(latest.net_income, shares)
        raw["per"] = _div(price, eps) if price and eps and eps > 0 else None
        raw["equity_ratio"] = _div(latest.equity, latest.total_assets)
        if len(funds) >= 2:
            raw["revenue_yoy"] = _yoy(latest.revenue, funds[-2].revenue)
            raw["earnings_yoy"] = _yoy(latest.net_income, funds[-2].net_income)

    if profile is not None:
        if raw["per"] is None:
            raw["per"] = profile.trailing_pe
        if raw["net_margin"] is None:
            raw["net_margin"] = profile.profit_margin
        if raw["revenue_yoy"] is None:
            raw["revenue_yoy"] = profile.revenue_growth
        if raw["earnings_yoy"] is None:
            raw["earnings_yoy"] = profile.earnings_growth

    if profile is not None and profile.sector in settings.recommendation_no_leverage_sectors:
        raw["der"] = raw["equity_ratio"] = None

    raw.update(_momentum(closes))
    return raw


def trader_factors(closes: list[float]) -> RawFactors:
    """Swing-trading factors from ascending daily closes (needs >= 21 closes)."""
    raw: RawFactors = dict.fromkeys(_TRADER_KEYS)
    if len(closes) < 21:
        return raw
    last = closes[-1]
    window = closes[-20:]
    rets = [b / a - 1 for a, b in zip(closes[-21:-1], window, strict=True) if a]
    raw["volatility_20d"] = pstdev(rets) if len(rets) >= 10 else None
    raw["from_high_20d"] = last / max(window) - 1 if max(window) else None
    raw["from_low_20d"] = last / min(window) - 1 if min(window) else None
    raw["ret_20d"] = last / closes[-21] - 1 if closes[-21] else None
    return raw


def percentile(values: Sequence[float | None], v: float) -> float:
    """Percentile rank (0-100) of `v` within `values` (None entries ignored)."""
    vals = [x for x in values if x is not None]
    n = len(vals)
    if n <= 1:
        return 50.0
    below = sum(1 for x in vals if x < v)
    equal = sum(1 for x in vals if x == v)
    return min(100.0, max(0.0, (below + 0.5 * equal) / n * 100))


def _fmt(value: float | None, kind: str) -> str:
    if value is None:
        return "—"
    if not math.isfinite(value):
        return "n/m (negative equity)"
    return f"{value * 100:.1f}%" if kind == "pct" else f"{value:.2f}"


def _rating(score: float) -> str:
    for label, threshold in settings.recommendation_ratings:
        if score >= threshold:
            return label
    return settings.recommendation_ratings[-1][0]


def _conviction(score: float, cat_scores: list[float], coverage: float) -> str:
    magnitude = abs(score - 50) / 50
    agreement = 1 - min(pstdev(cat_scores) / 25, 1) if len(cat_scores) >= 2 else 0.0
    confidence = 0.5 * magnitude + 0.3 * agreement + 0.2 * coverage
    if confidence >= settings.conviction_very_strong:
        return "Very Strong"
    if confidence >= settings.conviction_strong:
        return "Strong"
    if confidence >= settings.conviction_moderate:
        return "Moderate"
    return "Weak"


def _reasons(scored: list[tuple[str, str, str, float, float]]) -> list[str]:
    """Plain-language drivers: strongest positives then weakest negatives."""
    positives = [f for f in scored if f[3] >= 60][:2]
    negatives = [f for f in scored if f[3] <= 40][-2:]
    out = [f"{disp} {_fmt(val, fmt)} (strong)" for _, disp, fmt, _, val in positives]
    out += [f"{disp} {_fmt(val, fmt)} (weak)" for _, disp, fmt, _, val in negatives]
    if not out:
        out.append("Mixed signals")
    return out


def _eligible(
    raw: dict[str, RawFactors],
    traded_value: dict[str, float] | None,
    style: InvestingStyle,
) -> dict[str, RawFactors]:
    """Which tickers get a rating at all, per style."""
    if style == "trader":
        # Price behaviour only, but only for stocks liquid enough to swing-trade.
        floor = settings.recommendation_min_traded_value
        return {
            t: v
            for t, v in raw.items()
            if all(v.get(k) is not None for k in _TRADER_KEYS)
            and (traded_value is None or traded_value.get(t, 0.0) >= floor)
        }
    # Investor: needs fundamentals (price-only scores backtested as noise).
    return {t: v for t, v in raw.items() if any(v.get(k) is not None for k in _FUNDAMENTAL_KEYS)}


def score_universe(
    raw: dict[str, RawFactors],
    traded_value: dict[str, float] | None = None,
    style: InvestingStyle = "investor",
    special_monitoring: set[str] | None = None,
) -> dict[str, RecommendationOut]:
    """
    Turn raw per-ticker factor values into recommendation objects.

    `raw` maps ticker -> {factor_key: value or None} for the given `style`
    (`raw_factors` for investor, `trader_factors` for trader). Percentiles are
    computed across the eligible tickers (the cross-section). Investor: when
    `traded_value` is given, Buy/Strong Buy is capped at Hold below
    `recommendation_min_traded_value` (traders never see illiquid names at all).
    Both styles cap stocks on IDX's special-monitoring board at Hold.
    """
    spec = _SPECS[style]
    weights = spec.weights()
    rated = _eligible(raw, traded_value, style)
    keys = [f[0] for f in spec.factors]
    distributions = {k: [rated[t].get(k) for t in rated] for k in keys}
    results: dict[str, RecommendationOut] = {}

    for ticker, values in rated.items():
        by_category: dict[str, list[float]] = {}
        scored: list[tuple[str, str, str, float, float]] = []  # key, display, fmt, score, value
        n_present = 0

        for key, category, direction, display, fmt in spec.factors:
            v = values.get(key)
            if v is None:
                continue
            n_present += 1
            pct = percentile(distributions[key], v)
            factor_score = 100 - pct if direction == "lower" else pct
            by_category.setdefault(category, []).append(factor_score)
            scored.append((key, display, fmt, factor_score, v))

        cat_scores = {c: sum(s) / len(s) for c, s in by_category.items()}
        total_w = sum(weights.get(c.lower(), 0.0) for c in cat_scores)
        composite = (
            sum(cat_scores[c] * weights.get(c.lower(), 0.0) for c in cat_scores) / total_w
            if total_w > 0
            else 50.0
        )
        coverage = n_present / len(spec.factors)

        scored.sort(key=lambda f: f[3], reverse=True)
        rating = _rating(composite)
        reasons = _reasons(scored)
        if style == "investor" and traded_value is not None and rating in _BUY_RATINGS:
            liquidity = traded_value.get(ticker, 0.0)
            if liquidity < settings.recommendation_min_traded_value:
                rating = "Hold"
                reasons.append(
                    f"Thinly traded (Rp {liquidity / 1e6:,.0f}M/day) — capped at Hold"
                )
        if special_monitoring and ticker in special_monitoring and rating in _BUY_RATINGS:
            rating = "Hold"
            reasons.append(
                "Under IDX special monitoring (Papan Pemantauan Khusus) — capped at Hold"
            )
        results[ticker] = RecommendationOut(
            ticker=ticker,
            score=round(composite, 1),
            rating=rating,
            strength=_conviction(composite, list(cat_scores.values()), coverage),
            coverage=round(coverage, 2),
            categories=[
                CategoryOut(
                    name=c, weight=weights.get(c.lower(), 0.0), score=round(cat_scores[c], 1)
                )
                for c in spec.categories
                if c in cat_scores
            ],
            reasons=reasons,
            disclaimer=spec.disclaimer,
            style=style,
        )
    return results


# --------------------------------------------------------------------------- #
# Data-loading entrypoint
# --------------------------------------------------------------------------- #
async def compute_universe(
    session: AsyncSession,
    style: InvestingStyle = "investor",
    tickers: list[str] | None = None,
) -> dict[str, RecommendationOut]:
    """Load stored data and score every ticker (or just `tickers`) in `style`."""
    if tickers is None:
        tickers = list((await session.execute(select(Stock.ticker))).scalars().all())

    closes_map = await daily_closes(session, tickers)
    liquidity = await median_traded_value(session, tickers)
    special = set(
        (await session.execute(
            select(Stock.ticker).where(Stock.listing_board == "Watchlist")
        )).scalars().all()
    )
    if style == "trader":
        raw = {t: trader_factors(closes_map.get(t, [])) for t in tickers}
        return score_universe(raw, liquidity, style, special)

    funds_map = await fundamental_series(session, tickers)
    prof_map = await profiles(session, tickers)
    price_map = await latest_daily(session, tickers)

    raw = {
        t: raw_factors(
            closes_map.get(t, []),
            funds_map.get(t, []),
            prof_map.get(t),
            price_map.get(t, {}).get("close"),
        )
        for t in tickers
    }
    return score_universe(raw, liquidity, style, special)


# In-process TTL cache per style: the cross-section only changes when data syncs
# (prices every 3 min, fundamentals daily), so recomputing on every poll is wasteful.
_cache: dict[InvestingStyle, tuple[float, dict[str, RecommendationOut]]] = {}


async def compute_universe_cached(
    session: AsyncSession, style: InvestingStyle
) -> dict[str, RecommendationOut]:
    """
    Whole-universe scores for one investing style, cached per style for
    `recommendation_cache_seconds`. Callers pass the signed-in user's style
    (`deps`/`services.preferences`), so users with different styles don't mix.
    """
    now = time.monotonic()
    cached = _cache.get(style)
    if cached is not None and now - cached[0] < settings.recommendation_cache_seconds:
        return cached[1]
    data = await compute_universe(session, style)
    _cache[style] = (now, data)
    return data


def invalidate_cache() -> None:
    """Drop the cached universe scores (e.g. after a manual refresh)."""
    _cache.clear()
