"""
services/indices.py
-------------------
IDX stock indices: latest quotes (refreshed on a schedule), each day's close
stored as a bar, and full provider history for indices that have it (fetched
once, the first time their chart is opened).
"""

import logging
from datetime import date, datetime, timedelta
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from market.indices import BY_CODE, BY_SYMBOL, INDICES
from market.providers.governor import governor
from market.providers.registry import price_provider
from models import IndexBar, IndexQuote
from services.history import RANGE_DAYS
from services.market_clock import last_trading_day

log = logging.getLogger("bursa.indices")


class IndexRow(TypedDict):
    code: str
    name: str
    group: str
    last: float | None
    previous_close: float | None
    change: float | None
    change_percent: float | None
    updated_at: datetime | None
    has_history: bool  # provider has full history (else it builds up daily)
    history_since: date | None  # first stored bar


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

    now = datetime.utcnow()
    day = last_trading_day()
    async with AsyncSessionLocal() as session:
        for q in quotes:
            idx = BY_SYMBOL.get(q["symbol"])
            if idx is None:
                continue
            stmt = sqlite_insert(IndexQuote).values(
                code=idx.code, last=q["last"], previous_close=q["previous_close"],
                updated_at=now,
            )
            await session.execute(stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={"last": stmt.excluded.last, "previous_close": stmt.excluded.previous_close,
                      "updated_at": stmt.excluded.updated_at},
            ))
            bar = sqlite_insert(IndexBar).values(
                code=idx.code, day=day, open=q["open"], high=q["high"], low=q["low"],
                close=q["last"],
            )
            await session.execute(bar.on_conflict_do_update(
                index_elements=["code", "day"],
                set_={"open": bar.excluded.open, "high": bar.excluded.high,
                      "low": bar.excluded.low, "close": bar.excluded.close},
            ))
        await session.commit()
    log.info("Index quotes refreshed: %d of %d", len(quotes), len(symbols))
    return len(quotes)


async def ensure_full_history(session: AsyncSession, code: str) -> None:
    """Fetch the provider's full daily history once, for indices that have one."""
    idx = BY_CODE[code]
    if not idx.history:
        return
    quote = await session.get(IndexQuote, code)
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
    for start in range(0, len(values), 1000):  # stay under SQLite's variable limit
        stmt = sqlite_insert(IndexBar).values(values[start : start + 1000])
        await session.execute(stmt.on_conflict_do_update(
            index_elements=["code", "day"],
            set_={k: getattr(stmt.excluded, k) for k in ("open", "high", "low", "close", "volume")},
        ))
    now = datetime.utcnow()
    stmt = sqlite_insert(IndexQuote).values(
        code=code,
        last=bars[-1]["close"],
        previous_close=bars[-2]["close"] if len(bars) > 1 else None,
        updated_at=now,
        full_history_at=now,
    )
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["code"], set_={"full_history_at": stmt.excluded.full_history_at},
    ))
    await session.commit()
    log.info("Fetched full history for index %s (%d bars)", code, len(values))


async def list_indices(session: AsyncSession) -> list[IndexRow]:
    quotes = {q.code: q for q in (await session.execute(select(IndexQuote))).scalars()}
    since = dict(
        (await session.execute(
            select(IndexBar.code, func.min(IndexBar.day)).group_by(IndexBar.code)
        )).all()
    )
    out: list[IndexRow] = []
    for idx in INDICES:
        q = quotes.get(idx.code)
        last = q.last if q else None
        prev = q.previous_close if q else None
        change = round(last - prev, 2) if last is not None and prev else None
        out.append({
            "code": idx.code, "name": idx.name, "group": idx.group,
            "last": last, "previous_close": prev, "change": change,
            "change_percent": (
                round(change / prev * 100, 2) if change is not None and prev else None
            ),
            "updated_at": q.updated_at if q else None,
            "has_history": idx.history, "history_since": since.get(idx.code),
        })
    return out


async def index_history(session: AsyncSession, code: str, range_: str) -> list[IndexBar]:
    await ensure_full_history(session, code)
    stmt = select(IndexBar).where(IndexBar.code == code)
    days = RANGE_DAYS[range_]
    if days is not None:
        stmt = stmt.where(IndexBar.day >= date.today() - timedelta(days=days))
    return list((await session.execute(stmt.order_by(IndexBar.day))).scalars().all())
