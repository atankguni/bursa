"""
services/track_record.py
------------------------
How well have the ratings worked? Two sources, judged the same way: for each
rating, the share of stocks that beat that day's median stock over the style's
main horizon (investor 3 months, trader 4 weeks). 50% is a coin flip.

* Backtest: `backtest_summary.json`, written by
  `scripts/evaluate_signals.py --write-summary` (point-in-time replay of the
  current model over the stored history). Re-run it after changing the model.
* Live: the ratings recorded at each day's close (`RatingSnapshot`, see
  `record_ratings`) against what prices did next. Free of the backtest's
  blind spots (tuning on the same data, delisted stocks), but it needs a
  horizon's worth of days before the first result.
"""

import bisect
import logging
import statistics as st
import time
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

from pydantic import RootModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import DailyBar, RatingSnapshot, StockQuote
from schemas import (
    BacktestRecordOut,
    InvestingStyle,
    LiveRecordOut,
    Rating,
    RatingRecordOut,
)
from services.prices import median_traded_value
from services.recommendation import RATING_LABELS, compute_universe

log = logging.getLogger("bursa.track_record")

RATINGS: list[Rating] = list(RATING_LABELS)
# Main horizon per style, in trading days (the backtest's longest horizon).
HORIZON: dict[InvestingStyle, tuple[str, int]] = {
    "investor": ("3m", 63),
    "trader": ("4w", 20),
}
SUMMARY_FILE = Path(__file__).with_name("backtest_summary.json")
_LIVE_CACHE_SECONDS = 3600
_live_cache: dict[InvestingStyle, tuple[float, LiveRecordOut]] = {}


def beat_rates(rows: Iterable[tuple[str, str, float]]) -> list[RatingRecordOut]:
    """`rows` = (date, rating, forward return). Per rating: how many, and the share
    that beat the median stock of the same date. Ratings without rows are left out."""
    by_date: dict[str, list[float]] = defaultdict(list)
    items = list(rows)
    for day, _, ret in items:
        by_date[day].append(ret)
    median = {day: st.median(rets) for day, rets in by_date.items()}
    wins: dict[str, list[bool]] = defaultdict(list)
    for day, rating, ret in items:
        wins[rating].append(ret > median[day])
    return [
        RatingRecordOut(rating=r, n=len(wins[r]), beat=round(sum(wins[r]) / len(wins[r]), 3))
        for r in RATINGS
        if wins[r]
    ]


def load_backtest(style: InvestingStyle) -> BacktestRecordOut | None:
    try:
        summary = _BacktestSummary.model_validate_json(SUMMARY_FILE.read_bytes())
    except (OSError, ValueError):  # missing, or not the expected shape
        return None
    return summary.root.get(style)


class _BacktestSummary(RootModel[dict[InvestingStyle, BacktestRecordOut]]):
    """backtest_summary.json: {style: record}."""


# --------------------------------------------------------------------------- #
# Live record
# --------------------------------------------------------------------------- #
async def record_ratings(session: AsyncSession) -> int:
    """Store today's ratings (both styles) under the latest daily bar's date.
    Re-running on the same day replaces that day's rows."""
    day = (await session.execute(select(func.max(StockQuote.day)))).scalar()
    if day is None:
        return 0
    written = 0
    for style in HORIZON:
        recs = await compute_universe(session, style)
        liquidity = await median_traded_value(session, list(recs))
        await session.execute(
            delete(RatingSnapshot).where(
                RatingSnapshot.style == style, RatingSnapshot.day == day
            )
        )
        session.add_all(
            RatingSnapshot(
                day=day, style=style, ticker=t, rating=r.rating, score=r.score,
                liquid=liquidity.get(t, 0.0) >= settings.recommendation_min_traded_value,
            )
            for t, r in recs.items()
        )
        written += len(recs)
    await session.commit()
    _live_cache.clear()
    log.info("Recorded %d ratings for %s", written, day)
    return written


async def live_record(session: AsyncSession, style: InvestingStyle) -> LiveRecordOut:
    """Recorded ratings vs. what happened over the main horizon (cached an hour)."""
    cached = _live_cache.get(style)
    if cached and time.monotonic() - cached[0] < _LIVE_CACHE_SECONDS:
        return cached[1]

    _, horizon = HORIZON[style]
    query = select(
        RatingSnapshot.day, RatingSnapshot.ticker, RatingSnapshot.rating
    ).where(RatingSnapshot.style == style)
    if style == "investor":  # the backtest summary covers liquid stocks only
        query = query.where(RatingSnapshot.liquid.is_(True))
    snaps = (await session.execute(query)).all()
    days = sorted({d for d, _, _ in snaps})
    result = LiveRecordOut(
        since=days[0] if days else None,
        days=len(days),
        # ~7 calendar days per 5 trading days, plus slack for holidays.
        ready_on=days[0] + timedelta(days=horizon * 7 // 5 + 7) if days else None,
    )
    if days:
        bars = await _daily_bars(session, sorted({t for _, t, _ in snaps}), days[0])
        rows: list[tuple[str, str, float]] = []
        for day, ticker, rating in snaps:
            series = bars.get(ticker)
            if not series:
                continue
            dates, closes = series
            i = bisect.bisect_right(dates, day) - 1
            if i < 0 or dates[i] != day or i + horizon >= len(dates):
                continue  # no bar that day, or the horizon hasn't passed yet
            rows.append((day.isoformat(), rating, closes[i + horizon] / closes[i] - 1))
        result.matured_days = len({d for d, _, _ in rows})
        result.ratings = beat_rates(rows)
    _live_cache[style] = (time.monotonic(), result)
    return result


async def _daily_bars(
    session: AsyncSession, tickers: list[str], since: date
) -> dict[str, tuple[list[date], list[float]]]:
    out: dict[str, tuple[list[date], list[float]]] = {}
    rows = await session.execute(
        select(DailyBar.ticker, DailyBar.day, DailyBar.close)
        .where(
            DailyBar.ticker.in_(tickers),
            DailyBar.day >= since - timedelta(days=7),
        )
        .order_by(DailyBar.ticker, DailyBar.day)
    )
    for ticker, day, close in rows:
        if close:
            dates, closes = out.setdefault(ticker, ([], []))
            dates.append(day)
            closes.append(close)
    return out
