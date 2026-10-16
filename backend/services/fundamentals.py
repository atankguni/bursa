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

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import settings
from database import AsyncSessionLocal
from market.providers.governor import governor
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


async def sync_ticker(ticker: str, with_dividends: bool = True) -> int:
    """Fetch and upsert one ticker's fundamentals + profile. Returns rows written."""
    provider = fundamentals_provider()
    rows, profile = await governor.call(
        provider.name, f"fund:{ticker}", provider.fetch_fundamentals, ticker
    )
    if not rows and profile is None:
        return 0

    async with AsyncSessionLocal() as session:
        if any(r["source"] == "statements" for r in rows):
            # Real statements supersede any earlier summary-based row, which is
            # dated to the latest quarter and would otherwise look "newer".
            await session.execute(
                delete(Fundamental).where(
                    Fundamental.ticker == ticker, Fundamental.source == "summary"
                )
            )
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
                    "source": stmt.excluded.source,
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
                    "industry": prof.excluded.industry,
                    "description": prof.excluded.description,
                    "employees": prof.excluded.employees,
                    "website": prof.excluded.website,
                    "country": prof.excluded.country,
                    "city": prof.excluded.city,
                    "address": prof.excluded.address,
                    "phone": prof.excluded.phone,
                    "officers": prof.excluded.officers,
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

    # Dividends are best-effort (separate provider call, own session). Callers
    # that only need ratios/sector (e.g. the screener sync) pass False to halve
    # the number of provider calls.
    if rows:
        await reconcile_shares([ticker])
    if with_dividends:
        from services.dividends import sync_dividends

        await sync_dividends(ticker)
    return len(rows)


async def sync_many(
    tickers: list[str], throttle: float = 1.0, with_dividends: bool = True
) -> int:
    """Sync several tickers sequentially with a small delay between calls."""
    total = 0
    for i, ticker in enumerate(tickers):
        total += await sync_ticker(ticker, with_dividends=with_dividends)
        if throttle and i < len(tickers) - 1:
            await asyncio.sleep(throttle)
    if tickers:
        log.info("Fundamentals synced for %d tickers (%d rows)", len(tickers), total)
    return total


# Yahoo's share count is sometimes far off (BBNI 0.58bn vs 37.3bn; AISA 3.8bn vs
# 9.3bn); the IDX listing is the official register. Beyond this gap, use IDX.
SHARES_TOLERANCE = 0.2


async def reconcile_shares(tickers: list[str] | None = None) -> int:
    """Replace the latest fundamentals row's share count with IDX's official one
    where they disagree by more than SHARES_TOLERANCE. Returns rows fixed."""
    from sqlalchemy import func, select

    from models import Stock

    fixed = 0
    async with AsyncSessionLocal() as session:
        latest = (
            select(Fundamental.ticker, func.max(Fundamental.fiscal_year).label("fy"))
            .group_by(Fundamental.ticker)
            .subquery()
        )
        stmt = (
            select(Fundamental, Stock.idx_shares)
            .join(latest, (Fundamental.ticker == latest.c.ticker)
                  & (Fundamental.fiscal_year == latest.c.fy))
            .join(Stock, Stock.ticker == Fundamental.ticker)
            .where(Stock.idx_shares.is_not(None))
        )
        if tickers is not None:
            stmt = stmt.where(Fundamental.ticker.in_(tickers))
        for f, idx_shares in (await session.execute(stmt)).all():
            if idx_shares and (
                not f.total_shares
                or abs(f.total_shares - idx_shares) / idx_shares > SHARES_TOLERANCE
            ):
                log.info("Shares for %s: provider %s -> IDX %s", f.ticker, f.total_shares,
                         idx_shares)
                f.total_shares = idx_shares
                fixed += 1
        await session.commit()
    return fixed
