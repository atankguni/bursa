"""
services/idx_listing.py
-----------------------
Keep each stock's IDX listing board, listing date and official share count
current (weekly), and add newly listed companies (IPOs) to the catalog.
"""

import logging
from datetime import timedelta

from sqlalchemy import select

from clock import utcnow
from database import AsyncSessionLocal
from market.idx_site import fetch_listing
from market.providers.governor import governor
from models import Stock
from services.sync_state import last_done, mark_done

log = logging.getLogger("bursa.idx_listing")

STALE_AFTER = timedelta(days=7)
# A full listing has ~960 rows; far fewer means a partial/blocked response.
MIN_ROWS = 500


async def is_stale() -> bool:
    async with AsyncSessionLocal() as session:
        last = await last_done(session, "listing")
    return last is None or utcnow() - last > STALE_AFTER


async def sync_listing() -> int:
    """Update boards/dates/shares; add new listings. Returns rows applied (0 on failure)."""
    try:
        rows = await governor.call("idx", "idx-listing", fetch_listing)
    except Exception as exc:  # noqa: BLE001 - undocumented endpoint; never crash
        log.warning("IDX listing fetch failed: %s", exc)
        return 0
    if len(rows) < MIN_ROWS:
        log.warning("IDX listing looks partial (%d rows); not applied", len(rows))
        return 0

    now = utcnow()
    added = 0
    async with AsyncSessionLocal() as session:
        stocks = {s.ticker: s for s in (await session.execute(select(Stock))).scalars()}
        for r in rows:
            stock = stocks.get(r["ticker"])
            if stock is None:  # newly listed company
                stock = Stock(ticker=r["ticker"], name=r["name"])
                session.add(stock)
                added += 1
            stock.listing_board = r["board"]
            stock.listed_on = r["listed_on"]
            stock.idx_shares = r["shares"]
        await session.flush()
        await mark_done(session, "listing", [r["ticker"] for r in rows], at=now)
        await session.commit()
    log.info("IDX listing applied: %d stocks (%d new listings)", len(rows), added)
    from services.fundamentals import reconcile_shares

    fixed = await reconcile_shares()
    if fixed:
        log.info("Share counts corrected from the IDX register: %d", fixed)
    return len(rows)


async def sync_if_stale() -> None:
    if await is_stale():
        await sync_listing()
