"""
services/history.py
-------------------
Daily history. Every stock gets DAILY_HISTORY_YEARS of daily bars once
(`backfill_history`, a background job), which the daily sync then extends.
"max" (and "5y", until the backfill reaches a stock) fetches a stock's full
history the first time a chart asks for it.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from clock import utcnow
from config import settings
from market.sync import DAILY_INTERVAL, sync_batch
from models import Stock

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
    if stock.full_history_at is not None:
        return True
    if (
        range_ != "max"
        and stock.history_backfilled_at is not None
        and settings.daily_history_years >= 5
    ):
        return True
    written = await sync_batch([stock.ticker], period="max", interval=DAILY_INTERVAL)
    if written == 0:
        log.warning("Full history fetch returned nothing for %s", stock.ticker)
        return False
    stock.full_history_at = utcnow()
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
                    .where(Stock.history_backfilled_at.is_(None), Stock.full_history_at.is_(None))
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
            await session.execute(
                update(Stock)
                .where(Stock.ticker.in_(chunk))
                .values(history_backfilled_at=utcnow())
            )
            await session.commit()
        done += len(chunk)
    log.info("History backfill: %d of %d stocks done", done, len(tickers))
    return done
