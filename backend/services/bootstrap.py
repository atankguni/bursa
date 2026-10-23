"""One-time startup bootstrap: seed the index catalog and the stock universe."""

import logging

from sqlalchemy import select

from database import AsyncSessionLocal
from market.indices import INDICES
from market.tickers import all_tickers, associations, name_for
from models import MarketIndex, Stock, StockIndex

log = logging.getLogger("bursa.bootstrap")


async def seed() -> None:
    """Seed indices, stocks and index memberships once; existing rows are left untouched."""
    async with AsyncSessionLocal() as session:
        known = set((await session.execute(select(MarketIndex.code))).scalars().all())
        new_indices = [MarketIndex(code=i.code) for i in INDICES if i.code not in known]
        session.add_all(new_indices)

        existing = set((await session.execute(select(Stock.ticker))).scalars().all())
        new_stocks = [
            Stock(ticker=t, name=name_for(t)) for t in all_tickers() if t not in existing
        ]
        session.add_all(new_stocks)
        await session.flush()

        existing_links = set(
            (await session.execute(select(StockIndex.ticker, StockIndex.index_code))).tuples().all()
        )
        new_links = [
            StockIndex(ticker=t, index_code=idx)
            for t, idx in associations()
            if (t, idx) not in existing_links
        ]
        session.add_all(new_links)

        if new_indices or new_stocks or new_links:
            await session.commit()
            log.info(
                "Seeded %d indices, %d stocks, %d index links",
                len(new_indices), len(new_stocks), len(new_links),
            )
