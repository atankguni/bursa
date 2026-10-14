"""
scheduler.py
------------
Background market-data worker.

Strategy (anti rate-limit)
~~~~~~~~~~~~~~~~~~~~~~~~~~
Instead of one HTTP request per ticker we issue a SINGLE batched call to
`yf.download()` covering every tracked symbol. This keeps us far under
yfinance/Yahoo throttling limits.

Two jobs run on APScheduler:
  * `backfill_daily`  -> daily candles, 1 year, runs once at startup and daily.
  * `sync_intraday`   -> 1-minute candles, runs every 3 minutes during market
                         hours (WIB = UTC+7, Mon-Fri). All rows are upserted.

Parsing handles yfinance's MultiIndex column layout (ticker, field) that is
returned whenever more than one symbol is requested.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import AsyncSessionLocal, vacuum, wal_checkpoint
from models import StockPrice
from tickers import all_tickers

log = logging.getLogger("bursa.scheduler")

# Flat, de-duplicated ticker list used for the batched downloads.
TICKERS: list[str] = all_tickers()

WIB = ZoneInfo("Asia/Jakarta")

INTRADAY_INTERVAL = "1m"
DAILY_INTERVAL = "1d"

# Drop 1m bars older than this to keep the DB small (daily bars are kept).
INTRADAY_RETENTION_DAYS = 5

# --------------------------------------------------------------------------- #
# yfinance helpers
# --------------------------------------------------------------------------- #


def _download_batch(tickers: list[str], period: str, interval: str) -> pd.DataFrame:
    """Blocking batched download. Runs in a thread via `asyncio.to_thread`."""
    return yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        group_by="ticker",     # -> MultiIndex (ticker, field)
        auto_adjust=False,
        progress=False,
        threads=True,
        prepost=False,
    )


def _frame_for_ticker(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Extract the per-ticker sub-frame from a batched download, tolerating both
    the MultiIndex layout and the flat single-ticker layout.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        first_level = df.columns.get_level_values(0)
        if ticker not in first_level:
            return pd.DataFrame()
        return df[ticker].dropna(subset=["Close"])
    # Single ticker -> flat columns.
    return df.dropna(subset=["Close"])


def _to_rows(df: pd.DataFrame, ticker: str, interval: str) -> list[dict]:
    """Convert a per-ticker OHLCV frame into a list of upsert-ready dicts."""
    rows: list[dict] = []
    for ts, row in df.iterrows():
        try:
            # Normalise pandas Timestamp -> naive UTC datetime.
            dt = ts.to_pydatetime()
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

            close = float(row["Close"])
            if pd.isna(close):
                continue

            rows.append(
                {
                    "ticker": ticker,
                    "timestamp": dt,
                    "interval": interval,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": close,
                    "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                }
            )
        except (KeyError, TypeError, ValueError) as exc:  # skip malformed bars
            log.debug("Skipping bar for %s at %s: %s", ticker, ts, exc)
    return rows


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


async def _download_with_retry(
    tickers: list[str], period: str, interval: str, attempts: int = 3
) -> pd.DataFrame:
    """Batch download with a few retries + backoff to survive transient blocks."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await asyncio.to_thread(
                _download_batch, tickers, period, interval
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
    return pd.DataFrame()


async def _sync(tickers: list[str], period: str, interval: str) -> int:
    """Download a batch, parse every ticker, upsert all rows."""
    try:
        df = await _download_with_retry(tickers, period, interval)
    except Exception as exc:  # network / yfinance failure -> never crash the job
        log.warning("Batch download failed (%s/%s): %s", period, interval, exc)
        return 0

    all_rows: list[dict] = []
    for ticker in tickers:
        sub = _frame_for_ticker(df, ticker)
        if not sub.empty:
            all_rows.extend(_to_rows(sub, ticker, interval))

    written = await _upsert_rows(all_rows)
    log.info(
        "[%s] synced %d bars across %d tickers",
        interval,
        written,
        len(tickers),
    )
    return written


# --------------------------------------------------------------------------- #
# Scheduled jobs
# --------------------------------------------------------------------------- #


async def backfill_daily() -> None:
    """Fetch one year of daily candles for the whole universe."""
    await _sync(TICKERS, period="1y", interval=DAILY_INTERVAL)


def _market_open(now: datetime | None = None) -> bool:
    """True during IDX trading hours (Mon-Fri 09:00-16:00 WIB)."""
    now = now or datetime.now(WIB)
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    return time(9, 0) <= now.time() <= time(16, 0)


async def sync_intraday() -> None:
    """Fetch intraday 1-minute candles for the whole universe (market hours only)."""
    if not _market_open():
        log.debug("Market closed — skipping intraday sync")
        return
    await _sync(TICKERS, period="1d", interval=INTRADAY_INTERVAL)


async def prune_intraday() -> None:
    """Delete old 1m bars, then checkpoint the WAL. Keeps the DB from growing."""
    cutoff = datetime.utcnow() - timedelta(days=INTRADAY_RETENTION_DAYS)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(StockPrice).where(
                StockPrice.interval == INTRADAY_INTERVAL,
                StockPrice.timestamp < cutoff,
            )
        )
        await session.commit()
    await wal_checkpoint()
    log.info("Pruned %d old intraday rows (>= %d days)", result.rowcount, INTRADAY_RETENTION_DAYS)


async def compact_db() -> None:
    """Weekly VACUUM to reclaim disk space."""
    await vacuum()
    log.info("VACUUM complete")


async def sync_watchlist_fundamentals() -> None:
    """Refresh yearly fundamentals for every ticker currently on the watchlist."""
    from sqlalchemy import select

    from database import AsyncSessionLocal
    from fundamentals import sync_many
    from models import Watchlist

    async with AsyncSessionLocal() as session:
        tickers = (
            await session.execute(select(Watchlist.ticker))
        ).scalars().all()

    if not tickers:
        log.info("Watchlist empty — skipping fundamentals sync")
        return
    await sync_many(list(tickers), throttle=1.0)


# --------------------------------------------------------------------------- #
# Scheduler lifecycle
# --------------------------------------------------------------------------- #

scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")


def start_scheduler() -> None:
    """Register jobs and start the AsyncIOScheduler (call on app startup)."""
    if scheduler.running:
        return

    # Daily backfill: at startup, then each weekday at 09:00 WIB.
    scheduler.add_job(
        backfill_daily,
        trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=0),
        id="backfill_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Intraday quotes every 3 min, market hours only (Mon-Fri, 09:00-15:57 WIB).
    scheduler.add_job(
        sync_intraday,
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-15", minute="*/3"),
        id="sync_intraday",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Fundamentals: once per weekday evening (~18:00 WIB).
    scheduler.add_job(
        sync_watchlist_fundamentals,
        trigger=CronTrigger(day_of_week="mon-fri", hour=18, minute=0),
        id="sync_fundamentals",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Retention: prune old 1m bars every day at 17:00 WIB.
    scheduler.add_job(
        prune_intraday,
        trigger=CronTrigger(hour=17, minute=0),
        id="prune_intraday",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Weekly VACUUM (Sunday 03:00 WIB).
    scheduler.add_job(
        compact_db,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="compact_db",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    log.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Gracefully shut the scheduler down on app shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
