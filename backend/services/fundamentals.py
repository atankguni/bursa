"""
services/fundamentals.py
------------------------
Persist yearly fundamentals + profile from the active data provider.

Fetching/parsing (and FX normalization to the base currency) lives in the
provider adapter; this service handles upserts and staleness.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import settings
from database import AsyncSessionLocal
from market.providers.registry import fundamentals_provider
from models import Fundamental, StockProfile

log = logging.getLogger("bursa.fundamentals")


def is_stale(rows: list[Fundamental]) -> bool:
    """True if we have no cached rows or the newest one is older than the TTL."""
    if not rows:
        return True
    times = [r.updated_at for r in rows if r.updated_at is not None]
    if not times:
        return True
    ttl = timedelta(hours=settings.fundamentals_stale_hours)
    return datetime.utcnow() - max(times) > ttl


async def sync_ticker(ticker: str) -> int:
    """Fetch and upsert one ticker's fundamentals + profile. Returns rows written."""
    provider = fundamentals_provider()
    rows, profile = await asyncio.to_thread(provider.fetch_fundamentals, ticker)
    if not rows and profile is None:
        return 0

    async with AsyncSessionLocal() as session:
        if rows:
            stmt = sqlite_insert(Fundamental).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "fiscal_year"],
                set_={
                    "financial_currency": stmt.excluded.financial_currency,
                    "total_shares": stmt.excluded.total_shares,
                    "revenue": stmt.excluded.revenue,
                    "net_income": stmt.excluded.net_income,
                    "total_assets": stmt.excluded.total_assets,
                    "total_liabilities": stmt.excluded.total_liabilities,
                    "equity": stmt.excluded.equity,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await session.execute(stmt)

        if profile is not None:
            prof = sqlite_insert(StockProfile).values(
                ticker=ticker, updated_at=datetime.utcnow(), **profile
            )
            prof = prof.on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "sector": prof.excluded.sector,
                    "trailing_pe": prof.excluded.trailing_pe,
                    "profit_margin": prof.excluded.profit_margin,
                    "revenue_growth": prof.excluded.revenue_growth,
                    "earnings_growth": prof.excluded.earnings_growth,
                    "dividend_yield": prof.excluded.dividend_yield,
                    "beta": prof.excluded.beta,
                    "updated_at": prof.excluded.updated_at,
                },
            )
            await session.execute(prof)

        await session.commit()
    return len(rows)


async def sync_many(tickers: list[str], throttle: float = 1.0) -> int:
    """Sync several tickers sequentially with a small delay between calls."""
    total = 0
    for i, ticker in enumerate(tickers):
        total += await sync_ticker(ticker)
        if throttle and i < len(tickers) - 1:
            await asyncio.sleep(throttle)
    if tickers:
        log.info("Fundamentals synced for %d tickers (%d rows)", len(tickers), total)
    return total
