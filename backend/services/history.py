"""
services/history.py
-------------------
Chart history ranges. The catalog-wide sync keeps ~1 year of daily bars; longer
ranges ("5y", "max") fetch a stock's full daily history from the provider the
first time they're requested, then keep it (the daily sync extends it).
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from market.sync import DAILY_INTERVAL, sync_batch
from models import Stock

log = logging.getLogger("bursa.history")

# Range -> calendar days back (None = everything stored).
RANGE_DAYS: dict[str, int | None] = {
    "1m": 31, "3m": 92, "6m": 183, "1y": 366, "5y": 5 * 366, "max": None,
}
DEEP_RANGES = {"5y", "max"}  # beyond what the regular sync stores


def range_start(range_: str, now: datetime | None = None) -> datetime | None:
    days = RANGE_DAYS[range_]
    return None if days is None else (now or datetime.utcnow()) - timedelta(days=days)


async def ensure_full_history(session: AsyncSession, stock: Stock) -> bool:
    """
    Fetch the stock's full daily history once. Returns True if it is available.

    One governed provider call per stock, ever; concurrent requests for the same
    stock share it (governor single-flight). Not marked done when nothing came
    back, so a provider outage is retried on the next request.
    """
    if stock.full_history_at is not None:
        return True
    written = await sync_batch([stock.ticker], period="max", interval=DAILY_INTERVAL)
    if written == 0:
        log.warning("Full history fetch returned nothing for %s", stock.ticker)
        return False
    stock.full_history_at = datetime.utcnow()
    await session.commit()
    log.info("Fetched full daily history for %s (%d bars)", stock.ticker, written)
    return True
