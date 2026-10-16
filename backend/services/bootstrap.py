"""One-time startup bootstrap: seed the universe and clean stale data."""

import logging
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select

from database import AsyncSessionLocal
from market.tickers import all_tickers, associations, name_for
from models import Fundamental, Stock, StockIndex

log = logging.getLogger("bursa.bootstrap")


async def seed() -> None:
    """Seed stocks + index memberships once; existing rows are left untouched."""
    async with AsyncSessionLocal() as session:
        existing = set(
            (await session.execute(select(Stock.ticker))).scalars().all()
        )
        new_stocks = [
            Stock(ticker=t, name=name_for(t))
            for t in all_tickers()
            if t not in existing
        ]
        if new_stocks:
            session.add_all(new_stocks)
            await session.flush()

        existing_links = set(
            (await session.execute(
                select(StockIndex.ticker, StockIndex.index_name)
            )).all()
        )
        new_links = [
            StockIndex(ticker=t, index_name=idx)
            for t, idx in associations()
            if (t, idx) not in existing_links
        ]
        if new_links:
            session.add_all(new_links)

        if new_stocks or new_links:
            await session.commit()
            log.info(
                "Seeded %d stocks, %d index links",
                len(new_stocks), len(new_links),
            )


async def purge_stale_fundamentals() -> None:
    """Remove fundamentals rows lacking a currency tag (pre-conversion rows)."""
    async with AsyncSessionLocal() as session:
        result = cast(CursorResult[Any], await session.execute(
            delete(Fundamental).where(Fundamental.financial_currency.is_(None))
        ))
        await session.commit()
        if result.rowcount:
            log.info("Purged %d stale fundamentals rows", result.rowcount)
