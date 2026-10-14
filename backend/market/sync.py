"""
market/sync.py
--------------
Provider-agnostic batched price ingestion (anti rate-limit).

Symbols are split into chunks and each chunk is one governed download call, so
the governor paces work and no single call fans out across the whole universe.
"""

import asyncio
import logging

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import settings
from database import AsyncSessionLocal
from market.providers.governor import governor
from market.providers.registry import price_provider
from models import StockPrice

log = logging.getLogger("bursa.market.sync")


async def _upsert_rows(rows: list[dict]) -> int:
    """
    Idempotent bulk upsert keyed on (ticker, timestamp, interval).

    SQLite caps bound variables per statement (~32k), and each row binds 8
    values, so large inputs are inserted in slices.
    """
    if not rows:
        return 0

    slice_size = 1000  # 1000 rows * 8 cols = 8000 variables
    async with AsyncSessionLocal() as session:
        for start in range(0, len(rows), slice_size):
            part = rows[start : start + slice_size]
            stmt = sqlite_insert(StockPrice).values(part)
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
    """
    Fetch from the active provider in **chunks** and upsert all bars.

    yfinance issues ~one request per symbol internally, so a huge universe must
    be split into chunks (each chunk is one governed download call, so the
    governor paces between chunks).
    """
    if not tickers:
        return 0
    provider = price_provider()
    size = max(1, settings.provider_chunk_size)
    written = 0

    for start in range(0, len(tickers), size):
        chunk = tickers[start : start + size]
        try:
            per_ticker = await _fetch_with_retry(
                provider, chunk, period, interval
            )
        except Exception as exc:  # never crash the job
            log.warning(
                "Batch download failed (%s/%s, chunk %d): %s",
                period, interval, start // size, exc,
            )
            continue
        rows = [row for r in per_ticker.values() for row in r]
        # Persist each chunk immediately so a long run makes durable progress;
        # a failed write must not abort the remaining chunks.
        try:
            written += await _upsert_rows(rows)
        except Exception as exc:  # noqa: BLE001 - keep the run alive
            log.warning(
                "Upsert failed (%s/%s, chunk %d): %s",
                period, interval, start // size, exc,
            )

    log.info(
        "[%s] synced %d bars across %d tickers",
        interval, written, len(tickers),
    )
    return written
