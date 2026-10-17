"""
scheduler.py
------------
Background jobs + lifecycle (APScheduler).

Jobs:
  * backfill_daily                -> 1y of daily candles (startup + weekday 09:00)
  * sync_intraday                 -> 1m candles every 3 min, market hours only
  * sync_watchlist_fundamentals   -> refresh watchlist statements (weekday 18:00)
  * prune_intraday                -> drop 1m bars older than the retention window (daily)
  * compact_db                    -> VACUUM where the database needs it (weekly)

The heavy lifting lives in `market.sync` (batched downloads) and
`services.fundamentals` (per-ticker statements).
"""

import logging
from datetime import datetime, timedelta
from typing import Any, cast

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import CursorResult, delete, select

from config import settings
from database import AsyncSessionLocal, engine
from db import maintenance
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


async def refresh_index_quotes() -> None:
    """Latest value of every IDX index (see market/indices.py)."""
    from services.indices import refresh_quotes

    await refresh_quotes()


async def catch_up_intraday(period: str = "1d") -> None:
    """
    Re-fetch 1-minute bars to fill gaps (e.g. the host slept mid-session).
    Runs after the close for the day ("1d") and at startup for the whole
    retention window ("5d"). Not gated on market hours, unlike sync_intraday.
    """
    await sync_batch(await active_tickers(), period=period, interval=INTRADAY_INTERVAL)


async def sync_idx_listing() -> None:
    """Listing boards, dates, official shares and new IPOs from the IDX site."""
    from services.idx_listing import sync_listing

    await sync_listing()


async def sync_splits_active() -> None:
    """Stock splits for the active set, re-checked weekly per stock."""
    from services.corporate_actions import sync_due

    await sync_due(await active_tickers())


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
    """Delete old 1m bars, then checkpoint (SQLite's WAL). Keeps the DB from growing."""
    cutoff = datetime.utcnow() - timedelta(days=settings.intraday_retention_days)
    async with AsyncSessionLocal() as session:
        result = cast(CursorResult[Any], await session.execute(
            delete(StockPrice).where(
                StockPrice.interval == INTRADAY_INTERVAL,
                StockPrice.timestamp < cutoff,
            )
        ))
        await session.commit()
    await maintenance.checkpoint(engine)
    log.info(
        "Pruned %d old intraday rows (>= %d days)",
        result.rowcount, settings.intraday_retention_days,
    )


async def compact_db() -> None:
    """Weekly housekeeping: VACUUM on SQLite/PostgreSQL, nothing on MySQL."""
    ran = await maintenance.compact(engine)
    if ran:
        log.info("%s complete", ran)


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

# APScheduler drops a run that is late by more than `misfire_grace_time`
# (default: 1 second). On a laptop, Docker pauses while the host sleeps, so a
# 09:00 backfill would silently never happen. Run missed jobs once on wake
# instead (within 6h), collapsing any backlog into a single run.
scheduler = AsyncIOScheduler(
    timezone=settings.timezone,
    job_defaults={"misfire_grace_time": 6 * 3600, "coalesce": True},
)


# Last outcome per job id, for the data-health page (in-memory; single process).
job_runs: dict[str, dict[str, object]] = {}


def _record_job(event: JobExecutionEvent) -> None:
    job_runs[event.job_id] = {
        "last_run": datetime.utcnow(),
        "ok": event.exception is None,
        "error": str(event.exception)[:300] if event.exception else None,
    }


def job_report() -> list[dict[str, object]]:
    """Every scheduled job with its next run and last outcome (if any yet)."""
    return [
        {
            "id": job.id,
            "description": (job.func.__doc__ or job.id).strip().splitlines()[0],
            "next_run": job.next_run_time,
            **job_runs.get(job.id, {"last_run": None, "ok": None, "error": None}),
        }
        for job in sorted(scheduler.get_jobs(), key=lambda j: j.id)
    ]


def start_scheduler() -> None:
    """Register jobs and start the AsyncIOScheduler (call on app startup)."""
    if scheduler.running:
        return

    # Daily bars for the whole catalog: weekdays at 16:30 WIB, after the close,
    # so every stock gets the day's final bar (at 09:00 the day had barely begun
    # and most stocks only got yesterday's bar the next morning).
    scheduler.add_job(
        backfill_daily,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=30),
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

    # IDX listing (boards / special monitoring, IPOs): weekly, Monday 08:00 WIB.
    scheduler.add_job(
        sync_idx_listing,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="sync_idx_listing",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Stock splits for the active set (each stock re-checked weekly): daily 07:30.
    scheduler.add_job(
        sync_splits_active,
        trigger=CronTrigger(hour=7, minute=30),
        id="sync_splits",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # After the close: fill any 1-minute gaps from the day (host sleep etc.).
    scheduler.add_job(
        catch_up_intraday,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=10),
        id="catch_up_intraday",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Index values: every 15 min while trading, plus once after the close
    # (16:05 WIB) to store the final daily values.
    scheduler.add_job(
        refresh_index_quotes,
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-15", minute="*/15"),
        id="refresh_index_quotes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        refresh_index_quotes,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=5),
        id="refresh_index_quotes_close",
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

    scheduler.add_listener(_record_job, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    scheduler.start()
    log.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Gracefully shut the scheduler down on app shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
