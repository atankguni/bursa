"""
market/index_quotes.py
----------------------
IDX stock indices: latest quotes (refreshed on a schedule), each day's close
stored as a bar, and full provider history for indices that have it (fetched
once, the first time their chart is opened).
"""

import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import local_today, utcnow
from database import AsyncSessionLocal
from db.upsert import upsert
from market.history import RANGE_DAYS
from market.indices import BY_CODE, BY_SYMBOL, INDICES
from market.models import IndexBar, MarketIndex
from market.providers.governor import governor
from market.providers.registry import price_provider
from market.schemas import IndexOut
from market.trading_clock import last_trading_day

log = logging.getLogger("bursa.indices")


async def refresh_quotes() -> int:
    """Fetch every index's latest value; store the quote and today's bar."""
    provider = price_provider()
    symbols = [i.symbol for i in INDICES]
    try:
        quotes = await governor.call(
            provider.name, "index-quotes", provider.fetch_index_quotes, symbols
        )
    except Exception as exc:  # noqa: BLE001 - never crash the job
        log.warning("Index quote refresh failed: %s", exc)
        return 0
    if not quotes:
        return 0

    now = utcnow()
    day = last_trading_day()
    async with AsyncSessionLocal() as session:
        for q in quotes:
            idx = BY_SYMBOL.get(q["symbol"])
            if idx is None:
                continue
            await upsert(
                session, MarketIndex,
                {"code": idx.code, "last": q["last"], "previous_close": q["previous_close"],
                 "updated_at": now},
                keys=["code"],
            )
            await upsert(
                session, IndexBar,
                {"code": idx.code, "day": day, "open": q["open"], "high": q["high"],
                 "low": q["low"], "close": q["last"]},
                keys=["code", "day"],
            )
        await session.commit()
    log.info("Index quotes refreshed: %d of %d", len(quotes), len(symbols))
    return len(quotes)


async def ensure_full_history(session: AsyncSession, code: str) -> None:
    """Fetch the provider's full daily history once, for indices that have one."""
    idx = BY_CODE[code]
    if not idx.history:
        return
    quote = await session.get(MarketIndex, code)
    if quote is not None and quote.full_history_at is not None:
        return
    provider = price_provider()
    try:
        rows = await governor.call(
            provider.name, f"index-history:{idx.symbol}",
            provider.fetch_price_rows, [idx.symbol], "max", "1d",
        )
    except Exception as exc:  # noqa: BLE001 - serve what's stored; retry next time
        log.warning("Index history fetch failed for %s: %s", code, exc)
        return
    bars = rows.get(idx.symbol, [])
    if not bars:
        return
    values = [
        {"code": code, "day": b["timestamp"].date(), "open": b["open"], "high": b["high"],
         "low": b["low"], "close": b["close"], "volume": b["volume"]}
        for b in bars
    ]
    # The index row first: its bars reference it.
    await upsert(session, MarketIndex, {"code": code, "full_history_at": utcnow()}, keys=["code"])
    await upsert(session, IndexBar, values, keys=["code", "day"])
    await session.commit()
    log.info("Fetched full history for index %s (%d bars)", code, len(values))


async def list_indices(session: AsyncSession) -> list[IndexOut]:
    quotes = {q.code: q for q in (await session.execute(select(MarketIndex))).scalars()}
    since = dict(
        (await session.execute(
            select(IndexBar.code, func.min(IndexBar.day)).group_by(IndexBar.code)
        )).all()
    )
    out: list[IndexOut] = []
    for idx in INDICES:
        q = quotes.get(idx.code)
        last = q.last if q else None
        prev = q.previous_close if q else None
        change = round(last - prev, 2) if last is not None and prev else None
        out.append(IndexOut(
            code=idx.code, name=idx.name, group=idx.group,
            last=last, previous_close=prev, change=change,
            change_percent=(
                round(change / prev * 100, 2) if change is not None and prev else None
            ),
            updated_at=q.updated_at if q else None,
            has_history=idx.history, history_since=since.get(idx.code),
        ))
    return out


async def index_history(session: AsyncSession, code: str, range_: str) -> list[IndexBar]:
    await ensure_full_history(session, code)
    stmt = select(IndexBar).where(IndexBar.code == code)
    days = RANGE_DAYS[range_]
    if days is not None:
        stmt = stmt.where(IndexBar.day >= local_today() - timedelta(days=days))
    return list((await session.execute(stmt.order_by(IndexBar.day))).scalars().all())
