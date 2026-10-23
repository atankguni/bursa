"""
market/history.py
-----------------
Daily history. Every stock gets DAILY_HISTORY_YEARS of daily bars once
(`backfill_history`, a background job), which the daily sync then extends.
"max" (and "5y", until the backfill reaches a stock) fetches a stock's full
history the first time a chart asks for it.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import utcnow
from config import settings
from market.models import Stock
from market.sync import DAILY_INTERVAL, sync_batch
from market.sync_state import done_at, is_done, mark_done

log = logging.getLogger("bursa.history")

# Range -> calendar days back (None = everything stored).
RANGE_DAYS: dict[str, int | None] = {
    "1m": 31, "3m": 92, "6m": 183, "1y": 366, "5y": 5 * 366, "max": None,
}
DEEP_RANGES = {"5y", "max"}  # may be beyond what's stored yet


def range_start(range_: str, now: datetime | None = None) -> datetime | None:
    days = RANGE_DAYS[range_]
    return None if days is None else (now or utcnow()) - timedelta(days=days)


async def ensure_full_history(session: AsyncSession, stock: Stock, range_: str = "max") -> bool:
    """
    Fetch the stock's full daily history once. Returns True if it is available.
    "5y" needs no fetch once backfill_history has stored the stock's years.

    One governed provider call per stock, ever; concurrent requests for the same
    stock share it (governor single-flight). Not marked done when nothing came
    back, so a provider outage is retried on the next request.
    """
    if await done_at(session, "full_history", stock.ticker) is not None:
        return True
    if (
        range_ != "max"
        and settings.daily_history_years >= 5
        and await done_at(session, "history_backfill", stock.ticker) is not None
    ):
        return True
    written = await sync_batch([stock.ticker], period="max", interval=DAILY_INTERVAL)
    if written == 0:
        log.warning("Full history fetch returned nothing for %s", stock.ticker)
        return False
    await mark_done(session, "full_history", [stock.ticker])
    await session.commit()
    log.info("Fetched full daily history for %s (%d bars)", stock.ticker, written)
    return True


async def backfill_history() -> int:
    """
    Fetch DAILY_HISTORY_YEARS of daily bars for every stock that doesn't have
    them yet (first run: the whole catalog; later: new listings). Returns the
    number of stocks done.

    Goes through the governed provider in chunks, like the daily sync, and marks
    each chunk as soon as it's stored, so an interrupted run resumes where it
    stopped. A chunk that brings nothing back (provider down or blocking) ends
    the run; the next one retries.
    """
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        tickers = list(
            (
                await session.execute(
                    select(Stock.ticker)
                    .where(~is_done("history_backfill"), ~is_done("full_history"))
                    .order_by(Stock.ticker)
                )
            ).scalars()
        )
    if not tickers:
        return 0
    period = f"{max(1, settings.daily_history_years)}y"
    size = max(1, settings.provider_chunk_size)
    log.info("Backfilling %s of daily history for %d stocks", period, len(tickers))
    done = 0
    for start in range(0, len(tickers), size):
        chunk = tickers[start : start + size]
        if await sync_batch(chunk, period=period, interval=DAILY_INTERVAL) == 0:
            log.warning("History backfill got no data; stopping, the next run retries")
            break
        async with AsyncSessionLocal() as session:
            await mark_done(session, "history_backfill", chunk)
            await session.commit()
        done += len(chunk)
    log.info("History backfill: %d of %d stocks done", done, len(tickers))
    return done
