"""
market/quotes.py
----------------
`stock_quotes`: each stock's newest daily close and the one before, recomputed
from `daily_bars` whenever bars are written (market/sync), and for every stock
on startup. List pages read one row per stock instead of ranking bars.
"""

from collections.abc import Collection
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import local_today
from db.upsert import upsert
from market.models import DailyBar, StockQuote

# How far back the two newest bars are looked for. A stock without a bar this
# recent keeps its old quote; readers ignore quotes older than a year.
_LOOKBACK = timedelta(days=400)


async def refresh_quotes(session: AsyncSession, tickers: Collection[str] | None = None) -> int:
    """Recompute the quotes of `tickers` (None = every stock). Does not commit."""
    rn = (
        func.row_number()
        .over(partition_by=DailyBar.ticker, order_by=DailyBar.day.desc())
        .label("rn")
    )
    ranked = select(
        DailyBar.ticker, DailyBar.day, DailyBar.close, DailyBar.volume, rn
    ).where(DailyBar.day >= local_today() - _LOOKBACK)
    if tickers is not None:
        if not tickers:
            return 0
        ranked = ranked.where(DailyBar.ticker.in_(list(tickers)))
    sub = ranked.subquery()
    rows = (
        await session.execute(
            select(sub.c.ticker, sub.c.day, sub.c.close, sub.c.volume, sub.c.rn)
            .where(sub.c.rn <= 2)
            .order_by(sub.c.ticker, sub.c.rn)
        )
    ).all()
    quotes: dict[str, dict[str, object]] = {}
    for ticker, day, close, volume, rank in rows:
        if rank == 1:
            quotes[ticker] = {
                "ticker": ticker, "day": day, "close": close,
                "volume": volume or 0, "prev_close": None,
            }
        elif ticker in quotes:
            quotes[ticker]["prev_close"] = close
    await upsert(session, StockQuote, list(quotes.values()), keys=["ticker"])
    return len(quotes)
