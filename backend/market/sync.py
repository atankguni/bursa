"""
market/sync.py
--------------
Provider-agnostic batched price ingestion (anti rate-limit).

Symbols are split into chunks and each chunk is one governed download call, so
the governor paces work and no single call fans out across the whole universe.

Intraday syncs also roll today's 1-minute bars up into a provisional daily bar.
Every read path (latest price, change %, signals, alerts) uses daily bars, and
the official daily bar is only fetched at 09:00 / startup, so without the rollup
prices would stay frozen at the opening snapshot all session.
"""

import asyncio
import logging
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from clock import day_key, local_today
from config import settings
from database import AsyncSessionLocal
from db.upsert import upsert
from market.providers.base import MarketDataProvider, PriceBar
from market.providers.governor import governor
from market.providers.registry import price_provider
from market.quotes import refresh_quotes
from models import DailyBar, IntradayBar

log = logging.getLogger("bursa.market.sync")

INTRADAY_INTERVAL = "1m"
DAILY_INTERVAL = "1d"

# Wall-clock time (UTC) of the last chunk that actually wrote bars. Bar
# timestamps can't stand in for this: daily bars are dated midnight and the
# newest bar may be hours older than the sync that fetched it.
_last_synced_at: datetime | None = None


def last_synced_at() -> datetime | None:
    return _last_synced_at


def rollup_daily(bars: list[PriceBar], day: date) -> list[PriceBar]:
    """
    Aggregate `day`'s intraday bars (UTC timestamps) into one daily bar per ticker.

    Keyed like provider daily bars (`clock.day_key`: midnight of the local date), so
    the upsert updates today's row and the next official daily sync overwrites it.
    Bars from other days are ignored so a finished day's official bar is never
    replaced by a partial aggregate.
    """
    tz = ZoneInfo(settings.timezone)
    by_ticker: dict[str, list[PriceBar]] = {}
    for bar in bars:
        if bar["timestamp"].astimezone(tz).date() == day:
            by_ticker.setdefault(bar["ticker"], []).append(bar)

    daily: list[PriceBar] = []
    for ticker, rows in by_ticker.items():
        rows.sort(key=lambda b: b["timestamp"])
        daily.append(
            {
                "ticker": ticker,
                "timestamp": day_key(day),
                "interval": DAILY_INTERVAL,
                "open": rows[0]["open"],
                "high": max(b["high"] for b in rows),
                "low": min(b["low"] for b in rows),
                "close": rows[-1]["close"],
                "volume": sum(b["volume"] for b in rows),
            }
        )
    return daily


def _ohlcv(bar: PriceBar) -> dict[str, float | int]:
    return {
        "open": bar["open"], "high": bar["high"], "low": bar["low"],
        "close": bar["close"], "volume": bar["volume"],
    }


async def _upsert_rows(rows: list[PriceBar]) -> int:
    """
    Store bars (daily -> `daily_bars` by trading date, intraday -> `intraday_bars`)
    and refresh the quotes of stocks whose daily bars changed, in one
    transaction. Idempotent; `upsert` splits large inputs to stay under the
    database's bound-parameter limit.
    """
    if not rows:
        return 0
    daily = [
        {"ticker": b["ticker"], "day": b["timestamp"].date(), **_ohlcv(b)}
        for b in rows if b["interval"] == DAILY_INTERVAL
    ]
    intraday = [
        {"ticker": b["ticker"], "timestamp": b["timestamp"], **_ohlcv(b)}
        for b in rows if b["interval"] != DAILY_INTERVAL
    ]
    async with AsyncSessionLocal() as session:
        await upsert(session, DailyBar, daily, keys=["ticker", "day"])
        await upsert(session, IntradayBar, intraday, keys=["ticker", "timestamp"])
        if daily:
            await refresh_quotes(
                session, {b["ticker"] for b in rows if b["interval"] == DAILY_INTERVAL}
            )
        await session.commit()
    return len(rows)


async def _fetch_with_retry(
    provider: MarketDataProvider,
    tickers: list[str],
    period: str,
    interval: str,
    attempts: int = 3,
) -> dict[str, list[PriceBar]]:
    """Provider fetch with a few retries + backoff to survive transient blocks."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await governor.call(
                provider.name,
                # Single-flight key must identify the request: a shared key made a
                # concurrent call (e.g. on-demand history vs. the intraday sync)
                # receive the other request's bars.
                f"prices:{interval}:{period}:{','.join(tickers)}",
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
    global _last_synced_at
    if not tickers:
        return 0
    provider = price_provider()
    size = max(1, settings.provider_chunk_size)
    written = 0
    today = local_today()

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
        if interval == INTRADAY_INTERVAL:
            rows += rollup_daily(rows, today)
        # Persist each chunk immediately so a long run makes durable progress;
        # a failed write must not abort the remaining chunks.
        try:
            n = await _upsert_rows(rows)
        except Exception as exc:  # noqa: BLE001 - keep the run alive
            log.warning(
                "Upsert failed (%s/%s, chunk %d): %s",
                period, interval, start // size, exc,
            )
            continue
        written += n
        if n:
            _last_synced_at = datetime.now(UTC)

    log.info(
        "[%s] synced %d bars across %d tickers",
        interval, written, len(tickers),
    )
    return written
