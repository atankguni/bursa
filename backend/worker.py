"""
worker.py
---------
The worker process: the scheduler and every background job (price and
fundamentals syncs, history backfill, alerts, digests, backups), plus the long
jobs the API asks for (Sync all, signals/sync_job.py). The API (main.py)
only serves requests, so a slow provider or a failing job never slows a page,
and restarting the API doesn't stop a sync.

    python worker.py        # after prepare.py; docker compose runs it as `worker`

Only one worker may run: the scheduled jobs would otherwise run twice.
The worker talks to the API only through the database (system/worker_state.py).
"""

import asyncio
import logging
import signal
from collections.abc import Coroutine
from datetime import datetime

from sqlalchemy import func, select

from accounts.crypto import ensure_secret
from clock import utcnow
from database import AsyncSessionLocal, engine
from db.migrate import wait_until_current
from market.idx_listing import sync_if_stale as sync_idx_listing_if_stale
from market.models import Stock, StockQuote
from market.trading_clock import last_closed_trading_day
from scheduler import (
    TICKERS,
    backfill_active,
    backfill_daily,
    catch_up_intraday,
    job_list,
    refresh_index_quotes,
    start_scheduler,
    stop_scheduler,
    sync_splits_active,
    sync_watchlist_fundamentals,
)
from signals import sync_job
from system import worker_state

log = logging.getLogger("bursa.worker")

# How often to look for a Sync all requested by the API.
TASK_POLL_SECONDS = 2.0

# Strong references to running tasks (the event loop only keeps weak ones).
_tasks: set[asyncio.Task[None]] = set()


def _spawn(coro: Coroutine[object, object, None]) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _catalog_coverage() -> float:
    """Fraction of catalog tickers that have the last *finished* trading day's bar."""
    day = last_closed_trading_day()
    async with AsyncSessionLocal() as session:
        have = (
            await session.execute(
                select(func.count()).select_from(StockQuote).where(StockQuote.day >= day)
            )
        ).scalar_one()
    return have / max(1, len(TICKERS))


async def _wait_for_seed() -> None:
    """prepare.py migrates, then seeds the catalog; wait for both."""
    await wait_until_current(engine)
    while True:
        async with AsyncSessionLocal() as session:
            if (await session.execute(select(func.count()).select_from(Stock))).scalar_one():
                return
        await asyncio.sleep(2)


async def _heartbeat_loop(started_at: datetime) -> None:
    """Every HEARTBEAT_SECONDS: alive + counters, and the jobs' next runs."""
    while True:
        try:
            await worker_state.heartbeat(started_at)
            await worker_state.record_jobs(job_list())
        except Exception:  # noqa: BLE001 - a missed beat must not stop the worker
            log.warning("Heartbeat failed", exc_info=True)
        await asyncio.sleep(worker_state.HEARTBEAT_SECONDS)


async def _task_loop() -> None:
    """Run long jobs the API asks for, one at a time; first finish an interrupted one."""
    try:
        await sync_job.resume_interrupted()
    except Exception:  # noqa: BLE001
        log.exception("Could not resume the interrupted sync")
    while True:
        try:
            ran = await sync_job.run_requested()
        except Exception:  # noqa: BLE001 - keep serving requests
            log.exception("Requested sync failed")
            ran = False
        if not ran:
            await asyncio.sleep(TASK_POLL_SECONDS)


async def run() -> None:
    ensure_secret()
    await _wait_for_seed()
    _spawn(_heartbeat_loop(utcnow()))

    # Fast startup backfill for the active set; the full catalog sync runs in
    # the background only when coverage is low (first boot), keeping restarts fast.
    await backfill_active()
    # Catalog incomplete for the last finished trading day (first boot, or the
    # 16:30 job was missed): fetch it in the background.
    if await _catalog_coverage() < 0.8:
        _spawn(backfill_daily())

    start_scheduler()  # the heartbeat records the job list from now on

    _spawn(sync_watchlist_fundamentals())
    _spawn(refresh_index_quotes())
    # Listing boards / IPOs from the IDX site, if more than a week old.
    _spawn(sync_idx_listing_if_stale())
    _spawn(sync_splits_active())
    # Fill 1-minute gaps from while the worker was down or the host slept.
    _spawn(catch_up_intraday("5d"))
    _spawn(_task_loop())
    log.info("Bursa worker ready")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()

    log.info("Stopping the worker")
    stop_scheduler()
    for task in list(_tasks):
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    )
    asyncio.run(run())
