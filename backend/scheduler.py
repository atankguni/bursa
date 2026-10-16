"""
scheduler.py
------------
Background jobs + lifecycle (APScheduler).

Jobs:
  * backfill_daily                -> 1y of daily candles (startup + weekday 09:00)
  * sync_intraday                 -> 1m candles every 3 min, market hours only
  * sync_watchlist_fundamentals   -> refresh watchlist statements (weekday 18:00)
  * prune_intraday                -> drop 1m bars older than the retention window (daily)
  * compact_db                    -> VACUUM (weekly)

The heavy lifting lives in `market.sync` (batched downloads) and
`services.fundamentals` (per-ticker statements).
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, select

from config import settings
from database import AsyncSessionLocal, vacuum, wal_checkpoint
from market.sync import DAILY_INTERVAL, INTRADAY_INTERVAL, sync_batch
from market.tickers import all_tickers
from models import Stock, StockIndex, StockPrice, Transaction, Watchlist
from services.market_clock import is_open

log = logging.getLogger("bursa.scheduler")

# Full IDX catalog (daily sync target).
TICKERS: list[str] = all_tickers()


async def active_tickers() -> list[str]:
    """
    Symbols polled at high frequency: index constituents, watchlist, portfolio
    holdings, and user-tracked symbols — capped by `intraday_max_symbols`.
    """
    active: set[str] = set()
    async with AsyncSessionLocal() as session:
        active.update(
            (await session.execute(select(StockIndex.ticker))).scalars().all()
        )
        active.update(
            (await session.execute(select(Watchlist.ticker))).scalars().all()
        )
        active.update(
            (await session.execute(select(Transaction.ticker).distinct()))
            .scalars()
            .all()
        )
        active.update(
            (
                await session.execute(
                    select(Stock.ticker).where(Stock.tracked.is_(True))
                )
            )
            .scalars()
            .all()
        )
    return sorted(active)[: settings.intraday_max_symbols]


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #


async def backfill_daily() -> None:
    """Fetch one year of daily candles for the ENTIRE IDX catalog."""
    await sync_batch(TICKERS, period="1y", interval=DAILY_INTERVAL)


async def backfill_active() -> None:
    """Fast startup backfill for just the high-frequency set."""
    await sync_batch(await active_tickers(), period="1y", interval=DAILY_INTERVAL)


async def sync_intraday() -> None:
    """Fetch intraday 1-minute candles for the active set (market hours only)."""
    if not is_open():
        log.debug("Market closed — skipping intraday sync")
        return
    await sync_batch(await active_tickers(), period="1d", interval=INTRADAY_INTERVAL)
    # Evaluate alert rules against the freshly synced prices.
    from services.alerts import evaluate_alerts

    await evaluate_alerts()


async def sync_watchlist_fundamentals() -> None:
    """Refresh yearly fundamentals for every ticker currently on the watchlist."""
    from services.fundamentals import sync_many

    async with AsyncSessionLocal() as session:
        tickers = (
            await session.execute(select(Watchlist.ticker))
        ).scalars().all()

    if not tickers:
        log.info("Watchlist empty — skipping fundamentals sync")
        return
    await sync_many(list(tickers), throttle=1.0)


async def prune_intraday() -> None:
    """Delete old 1m bars, then checkpoint the WAL. Keeps the DB from growing."""
    cutoff = datetime.utcnow() - timedelta(days=settings.intraday_retention_days)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(StockPrice).where(
                StockPrice.interval == INTRADAY_INTERVAL,
                StockPrice.timestamp < cutoff,
            )
        )
        await session.commit()
    await wal_checkpoint()
    log.info(
        "Pruned %d old intraday rows (>= %d days)",
        result.rowcount, settings.intraday_retention_days,
    )


async def compact_db() -> None:
    """Weekly VACUUM to reclaim disk space."""
    await vacuum()
    log.info("VACUUM complete")


async def log_provider_stats() -> None:
    """Log today's outbound provider calls, then reset the daily counter."""
    from market.providers.governor import governor

    stats = governor.stats()
    log.info(
        "Provider calls today: %s",
        {name: s["calls_today"] for name, s in stats.items()},
    )
    governor.reset_daily()


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #

scheduler = AsyncIOScheduler(timezone=settings.timezone)


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

    # Daily provider-call summary (23:00 WIB).
    scheduler.add_job(
        log_provider_stats,
        trigger=CronTrigger(hour=23, minute=0),
        id="log_provider_stats",
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
