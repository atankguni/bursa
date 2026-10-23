"""Dividend persistence + trailing-yield helpers."""

import logging
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import local_today
from database import AsyncSessionLocal
from db.upsert import upsert
from market.providers.governor import governor
from market.providers.registry import fundamentals_provider
from models import Dividend

log = logging.getLogger("bursa.dividends")


async def sync_dividends(ticker: str) -> int:
    """Fetch + upsert one ticker's dividend history. Returns rows written."""
    provider = fundamentals_provider()
    rows = await governor.call(
        provider.name, f"div:{ticker}", provider.fetch_dividends, ticker
    )
    values = [
        {"ticker": ticker, "ex_date": r["ex_date"], "amount": float(r["amount"])}
        for r in rows
    ]
    if not values:
        return 0

    async with AsyncSessionLocal() as session:
        await upsert(session, Dividend, values, keys=["ticker", "ex_date"], update=["amount"])
        await session.commit()
    return len(values)


async def list_dividends(session: AsyncSession, ticker: str) -> list[Dividend]:
    rows = (
        await session.execute(
            select(Dividend)
            .where(Dividend.ticker == ticker)
            .order_by(Dividend.ex_date.desc())
        )
    ).scalars().all()
    return list(rows)


async def trailing_dps(
    session: AsyncSession, tickers: list[str], days: int = 365
) -> dict[str, float]:
    """Sum of dividends per share over the trailing window, per ticker."""
    if not tickers:
        return {}
    cutoff = local_today() - timedelta(days=days)
    rows = (
        await session.execute(
            select(Dividend.ticker, Dividend.amount).where(
                Dividend.ticker.in_(tickers), Dividend.ex_date >= cutoff
            )
        )
    ).all()
    out: dict[str, float] = defaultdict(float)
    for ticker, amount in rows:
        out[ticker] += amount
    return dict(out)
