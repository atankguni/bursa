"""
market/sync.py
--------------
Provider-agnostic batched price ingestion (anti rate-limit).

The active provider issues a SINGLE batched call covering every symbol; this
module only handles retries, flattening, and upserting the bars.
"""

import asyncio
import logging

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import AsyncSessionLocal
from market.providers.governor import governor
from market.providers.registry import price_provider
from models import StockPrice

log = logging.getLogger("bursa.market.sync")


async def _upsert_rows(rows: list[dict]) -> int:
    """Idempotent bulk upsert keyed on (ticker, timestamp, interval)."""
    if not rows:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = sqlite_insert(StockPrice).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "timestamp", "interval"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def _fetch_with_retry(
    provider, tickers: list[str], period: str, interval: str, attempts: int = 3
) -> dict[str, list[dict]]:
    """Provider fetch with a few retries + backoff to survive transient blocks."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await governor.call(
                provider.name,
                "prices",
                provider.fetch_price_rows,
                tickers,
                period,
                interval,
            )
        except Exception as exc:  # noqa: BLE001 - log and retry
            last_exc = exc
            log.warning(
                "Download attempt %d/%d failed (%s/%s): %s",
                attempt, attempts, period, interval, exc,
            )
            if attempt < attempts:
                await asyncio.sleep(2 ** attempt)  # 2s, 4s backoff
    log.error("All %d download attempts failed (%s/%s)", attempts, period, interval)
    if last_exc:
        raise last_exc
    return {}


async def sync_batch(tickers: list[str], period: str, interval: str) -> int:
    """Fetch a batch from the active provider and upsert all bars."""
    provider = price_provider()
    try:
        per_ticker = await _fetch_with_retry(provider, tickers, period, interval)
    except Exception as exc:  # never crash the job
        log.warning("Batch download failed (%s/%s): %s", period, interval, exc)
        return 0

    all_rows = [row for rows in per_ticker.values() for row in rows]
    written = await _upsert_rows(all_rows)
    log.info(
        "[%s] synced %d bars across %d tickers",
        interval, written, len(tickers),
    )
    return written
