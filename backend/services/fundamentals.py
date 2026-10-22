"""
services/fundamentals.py
------------------------
Persist yearly fundamentals + profile from the active data provider.

Fetching/parsing (and FX normalization to the base currency) lives in the
provider adapter; this service handles upserts and staleness.
"""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete

from clock import utcnow
from config import settings
from database import AsyncSessionLocal
from db.upsert import upsert
from market.providers.governor import governor
from market.providers.registry import fundamentals_provider
from models import Fundamental, StockProfile

log = logging.getLogger("bursa.fundamentals")


def is_stale(rows: list[Fundamental]) -> bool:
    """True if we have no cached rows or the newest one is older than the TTL."""
    if not rows:
        return True
    times = [r.updated_at for r in rows]
    ttl = timedelta(hours=settings.fundamentals_stale_hours)
    return utcnow() - max(times) > ttl


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
            await upsert(
                session, Fundamental, rows,
                keys=["ticker", "fiscal_year"],
                update=[
                    "financial_currency", "total_shares", "revenue", "net_income",
                    "total_assets", "total_liabilities", "equity", "source", "updated_at",
                ],
            )

        if profile is not None:
            # Every provided field (and updated_at) overwrites the stored profile.
            await upsert(
                session, StockProfile,
                {"ticker": ticker, "updated_at": utcnow(), **profile},
                keys=["ticker"],
            )

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
