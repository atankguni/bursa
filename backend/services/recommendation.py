"""
services/recommendation.py
--------------------------
Explainable, cross-sectional buy-signal score.

For each tracked stock we compute a handful of factors (valuation, quality,
growth, momentum, health), rank each factor as a percentile WITHIN the tracked
universe (so scores are relative, not absolute), average within categories, then
take a weighted composite (0-100). The composite maps to a rating and a
conviction ("strength") that also accounts for factor agreement and data
coverage.

Everything is transparent and testable — no black-box model.
"""

import logging
from statistics import pstdev

from sqlalchemy import select

from config import settings
from models import Stock, StockProfile
from schemas import CategoryOut, RecommendationOut
from services.prices import (
    daily_closes,
    fundamental_series,
    latest_daily,
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


def raw_factors(closes, funds, profile: StockProfile | None, price: float | None) -> dict:
    """Compute the raw (un-normalised) factor values for one ticker."""
    raw: dict[str, float | None] = dict.fromkeys(_FACTOR_KEYS)
    latest = funds[-1] if funds else None

    if latest is not None:
        raw["roe"] = _div(latest.net_income, latest.equity)
        raw["net_margin"] = _div(latest.net_income, latest.revenue)
        shares = latest.total_shares
        market_cap = price * shares if price and shares else None
        book = None
        if latest.total_assets is not None and latest.total_liabilities is not None:
            book = latest.total_assets - latest.total_liabilities
        elif latest.equity is not None:
            book = latest.equity
        raw["pbv"] = _div(market_cap, book)
        eps = _div(latest.net_income, shares)
        raw["per"] = _div(price, eps) if price and eps and eps > 0 else None
        raw["der"] = _div(latest.total_liabilities, latest.equity)
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

    raw.update(_momentum(closes))
    return raw


def percentile(values: list[float | None], v: float) -> float:
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


def score_universe(raw: dict[str, dict]) -> dict[str, RecommendationOut]:
    """
    Turn raw per-ticker factor values into recommendation objects.

    `raw` maps ticker -> {factor_key: value or None}. Percentiles are computed
    across all tickers in `raw` (the cross-section).
    """
    weights = settings.recommendation_weights
    distributions = {k: [raw[t].get(k) for t in raw] for k in _FACTOR_KEYS}
    results: dict[str, RecommendationOut] = {}

    for ticker, values in raw.items():
        by_category: dict[str, list[float]] = {}
        scored: list[tuple[str, str, str, float, float]] = []  # key, display, fmt, score, value
        n_present = 0

        for key, category, direction, display, fmt in FACTORS:
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
        coverage = n_present / len(FACTORS)

        scored.sort(key=lambda f: f[3], reverse=True)
        results[ticker] = RecommendationOut(
            ticker=ticker,
            score=round(composite, 1),
            rating=_rating(composite),
            strength=_conviction(composite, list(cat_scores.values()), coverage),
            coverage=round(coverage, 2),
            categories=[
                CategoryOut(
                    name=c, weight=weights.get(c.lower(), 0.0), score=round(cat_scores[c], 1)
                )
                for c in CATEGORY_ORDER
                if c in cat_scores
            ],
            reasons=_reasons(scored),
            disclaimer=DISCLAIMER,
        )
    return results


# --------------------------------------------------------------------------- #
# Data-loading entrypoint
# --------------------------------------------------------------------------- #
async def compute_universe(session, tickers: list[str] | None = None):
    """Load stored data and score every ticker (or just `tickers`)."""
    if tickers is None:
        tickers = [t for (t,) in (await session.execute(select(Stock.ticker))).all()]

    closes_map = await daily_closes(session, tickers)
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
    return score_universe(raw)
