"""Read queries over price + fundamental data (shared by the routers)."""

from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from market.tickers import INDEX_ORDER
from models import Fundamental, StockIndex, StockPrice, StockProfile


class LatestQuote(TypedDict, total=False):
    """Latest daily bar summary; `prev_close` is absent with only one bar."""

    close: float
    prev_close: float
    volume: int
    updated_at: datetime


async def indices_map(
    session: AsyncSession, tickers: list[str]
) -> dict[str, list[str]]:
    """Return {ticker: [index, ...]} ordered by INDEX_ORDER."""
    if not tickers:
        return {}
    rows = (
        await session.execute(
            select(StockIndex.ticker, StockIndex.index_name).where(
                StockIndex.ticker.in_(tickers)
            )
        )
    ).all()
    mapping: dict[str, list[str]] = {}
    for ticker, index_name in rows:
        mapping.setdefault(ticker, []).append(index_name)
    order = {name: i for i, name in enumerate(INDEX_ORDER)}
    for ticker in mapping:
        mapping[ticker].sort(key=lambda n: order.get(n, 999))
    return mapping


async def latest_daily(
    session: AsyncSession, tickers: list[str]
) -> dict[str, LatestQuote]:
    """Map each ticker to its latest daily close (+ prev close, volume, time)."""
    if not tickers:
        return {}
    rn = (
        func.row_number()
        .over(
            partition_by=StockPrice.ticker,
            order_by=StockPrice.timestamp.desc(),
        )
        .label("rn")
    )
    ranked = (
        select(
            StockPrice.ticker, StockPrice.close, StockPrice.volume,
            StockPrice.timestamp, rn,
        )
        .where(StockPrice.interval == "1d", StockPrice.ticker.in_(tickers))
        .subquery()
    )
    recent = (
        select(ranked)
        .where(ranked.c.rn <= 2)
        .order_by(ranked.c.ticker, ranked.c.rn)
    )
    rows = (await session.execute(recent)).all()

    latest: dict[str, LatestQuote] = {}
    for ticker, close, volume, ts, rank in rows:
        entry = latest.setdefault(ticker, {})
        if rank == 1:
            entry["close"] = close
            entry["volume"] = volume
            entry["updated_at"] = ts
        else:
            entry["prev_close"] = close
    return latest


async def latest_fundamentals(
    session: AsyncSession, tickers: list[str]
) -> dict[str, Fundamental]:
    """Map each ticker to its most recent fiscal-year Fundamental row."""
    if not tickers:
        return {}
    rows = (
        await session.execute(
            select(Fundamental).where(Fundamental.ticker.in_(tickers))
        )
    ).scalars().all()
    best: dict[str, Fundamental] = {}
    for f in rows:
        cur = best.get(f.ticker)
        if cur is None or f.fiscal_year > cur.fiscal_year:
            best[f.ticker] = f
    return best


# ~1 trading year. Signals/valuation are defined on this window; some stocks
# store their full history (chart "5Y"/"Max"), which must not change them.
TRADING_YEAR = 252


async def daily_closes(
    session: AsyncSession, tickers: list[str], last: int | None = TRADING_YEAR
) -> dict[str, list[float]]:
    """Ascending daily closes per ticker: the most recent `last` (None = all)."""
    if not tickers:
        return {}
    base = select(StockPrice.ticker, StockPrice.close, StockPrice.timestamp).where(
        StockPrice.interval == "1d", StockPrice.ticker.in_(tickers)
    )
    if last is not None:
        rn = (
            func.row_number()
            .over(partition_by=StockPrice.ticker, order_by=StockPrice.timestamp.desc())
            .label("rn")
        )
        ranked = base.add_columns(rn).subquery()
        stmt = (
            select(ranked.c.ticker, ranked.c.close)
            .where(ranked.c.rn <= last)
            .order_by(ranked.c.ticker, ranked.c.timestamp)
        )
    else:
        stmt = (
            select(StockPrice.ticker, StockPrice.close)
            .where(StockPrice.interval == "1d", StockPrice.ticker.in_(tickers))
            .order_by(StockPrice.ticker, StockPrice.timestamp)
        )
    rows = (await session.execute(stmt)).all()
    series: dict[str, list[float]] = {}
    for ticker, close in rows:
        series.setdefault(ticker, []).append(close)
    return series


async def fundamental_series(
    session: AsyncSession, tickers: list[str]
) -> dict[str, list[Fundamental]]:
    """All fiscal-year rows per ticker, ascending (for growth calculations)."""
    if not tickers:
        return {}
    rows = (
        await session.execute(
            select(Fundamental)
            .where(Fundamental.ticker.in_(tickers))
            .order_by(Fundamental.ticker, Fundamental.fiscal_year)
        )
    ).scalars().all()
    series: dict[str, list[Fundamental]] = {}
    for f in rows:
        series.setdefault(f.ticker, []).append(f)
    return series


async def profiles(
    session: AsyncSession, tickers: list[str]
) -> dict[str, StockProfile]:
    """Map each ticker to its StockProfile (info-derived metrics)."""
    if not tickers:
        return {}
    rows = (
        await session.execute(
            select(StockProfile).where(StockProfile.ticker.in_(tickers))
        )
    ).scalars().all()
    return {p.ticker: p for p in rows}


async def median_traded_value(
    session: AsyncSession, tickers: list[str], days: int = 20
) -> dict[str, float]:
    """Median daily traded value (close × volume, IDR) over each ticker's last `days` bars."""
    if not tickers:
        return {}
    rn = (
        func.row_number()
        .over(partition_by=StockPrice.ticker, order_by=StockPrice.timestamp.desc())
        .label("rn")
    )
    ranked = (
        select(StockPrice.ticker, StockPrice.close, StockPrice.volume, rn)
        .where(StockPrice.interval == "1d", StockPrice.ticker.in_(tickers))
        .subquery()
    )
    rows = (
        await session.execute(
            select(ranked.c.ticker, ranked.c.close, ranked.c.volume).where(ranked.c.rn <= days)
        )
    ).all()
    values: dict[str, list[float]] = defaultdict(list)
    for ticker, close, volume in rows:
        values[ticker].append(close * (volume or 0))
    return {t: median(v) for t, v in values.items()}
