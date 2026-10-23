"""
services/sync_job.py
--------------------
The background job that fills **missing fundamentals** for the screener.

The API asks for a run (`start`, `start_all`, `cancel`) by writing the
`worker_tasks` row; the worker process runs it (`run_requested`) and reports
progress in the same row, which `status` reads. Only one run at a time;
fundamentals-only (no dividends) to halve provider calls; paced by the
worker's governor. A run cut short by a worker restart is resumed
(`resume_interrupted`).

Each attempt is stamped in `sync_state` ("fundamentals") and the queue is
ordered never-tried first, then least-recently tried. Without that, tickers the
provider has no statements for stay "missing" forever and, being first
alphabetically, would fill every capped run.
"""

import asyncio
import logging
from typing import Any, cast

from sqlalchemy import ColumnElement, CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from clock import utcnow
from config import settings
from database import AsyncSessionLocal
from db.upsert import upsert
from models import Fundamental, Stock, StockProfile, WorkerTask
from schemas import SyncMode, SyncStatusOut, WorkerTaskName
from services import worker_state
from services.fundamentals import sync_ticker
from services.recommendation import invalidate_cache
from services.sync_state import done_column, is_done, mark_done

log = logging.getLogger("bursa.sync_job")

TASK: WorkerTaskName = "fundamentals_sync"
_WAITING = "Waiting for the worker…"


def _missing_clause() -> ColumnElement[bool]:
    return ~Stock.ticker.in_(select(Fundamental.ticker).distinct())


async def missing_tickers() -> list[str]:
    """Stocks without fundamentals, never-tried first, then least-recently tried."""
    tried = done_column("fundamentals")
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Stock.ticker)
                .where(_missing_clause())
                # Never-tried (NULL) lead the queue. Databases disagree on where
                # NULL sorts, so sort on IS NOT NULL first.
                .order_by(tried.is_not(None), tried, Stock.ticker)
            )
        ).scalars().all()
    return list(rows)


async def missing_count() -> int:
    async with AsyncSessionLocal() as session:
        return (
            await session.execute(select(func.count()).select_from(Stock).where(_missing_clause()))
        ).scalar_one()


async def never_tried() -> list[str]:
    """Stocks without fundamentals that have never been attempted."""
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Stock.ticker)
                .where(_missing_clause(), ~is_done("fundamentals"))
                .order_by(Stock.ticker)
            )
        ).scalars().all()
    return list(rows)


async def _with_data(tickers: list[str]) -> int:
    """How many of `tickers` now have fundamentals or a profile (anything came back)."""
    async with AsyncSessionLocal() as session:
        have = set(
            (await session.execute(
                select(Fundamental.ticker).where(Fundamental.ticker.in_(tickers)).distinct()
            )).scalars().all()
        ) | set(
            (await session.execute(
                select(StockProfile.ticker).where(StockProfile.ticker.in_(tickers))
            )).scalars().all()
        )
    return len(have)


def _rowcount(result: object) -> int:
    return cast(CursorResult[Any], result).rowcount or 0


async def _ensure_row(session: AsyncSession) -> None:
    await upsert(session, WorkerTask, {"name": TASK}, keys=["name"], update=[])


# --------------------------------------------------------------------------- #
# API side
# --------------------------------------------------------------------------- #
async def status() -> SyncStatusOut:
    async with AsyncSessionLocal() as session:
        task = await session.get(WorkerTask, TASK)
        alive = worker_state.is_alive(await worker_state.status(session))
    if task is None:
        return SyncStatusOut(running=False)
    note = task.note
    if task.running and not alive:
        note = "The worker isn't running: the sync continues when it starts"
    return SyncStatusOut(
        running=task.running,
        mode=task.mode,
        total=task.total,
        done=task.done,
        remaining=max(0, task.total - task.done),
        last_error=task.last_error,
        note=note,
    )


async def _request(mode: SyncMode, total: int, request: dict[str, Any]) -> bool:
    """Hand a run to the worker. False if one is already queued or running."""
    async with AsyncSessionLocal() as session:
        await _ensure_row(session)
        result = await session.execute(
            update(WorkerTask)
            .where(WorkerTask.name == TASK, WorkerTask.running.is_(False))
            .values(
                request=request, requested_at=utcnow(), cancel_requested=False,
                running=True, mode=mode, total=total, done=0, note=_WAITING,
                last_error=None, started_at=None, finished_at=None,
            )
        )
        await session.commit()
    return _rowcount(result) == 1


async def start(tickers: list[str]) -> bool:
    """Queue one capped run over `tickers`. False if a run is already going."""
    return await _request("batch", len(tickers), {"tickers": tickers})


async def start_all() -> bool:
    """Queue 'sync all' (every never-tried stock). False if a run is already going."""
    return await _request("all", len(await never_tried()), {})


async def cancel() -> bool:
    """Stop the run: at once if the worker hasn't picked it up, else after the
    current stock. False if nothing is running."""
    async with AsyncSessionLocal() as session:
        dropped = await session.execute(
            update(WorkerTask)
            .where(WorkerTask.name == TASK, WorkerTask.requested_at.is_not(None))
            .values(running=False, requested_at=None, request=None, note=None,
                    finished_at=utcnow())
        )
        stopping = await session.execute(
            update(WorkerTask)
            .where(WorkerTask.name == TASK, WorkerTask.running.is_(True))
            .values(cancel_requested=True, note="Stopping…")
        )
        await session.commit()
    return _rowcount(dropped) + _rowcount(stopping) > 0


# --------------------------------------------------------------------------- #
# Worker side
# --------------------------------------------------------------------------- #
class _Run:
    """Progress of the run in this worker, saved to the task row as it goes."""

    def __init__(self, mode: SyncMode, total: int, done: int) -> None:
        self.mode = mode
        self.total = total
        self.done = done
        self.note: str | None = None
        self.last_error: str | None = None
        self.cancelled = False

    async def save(self) -> None:
        """Write progress; pick up a cancel request from the API."""
        async with AsyncSessionLocal() as session:
            task = await session.get(WorkerTask, TASK)
            if task is None or not task.running:
                self.cancelled = True
                return
            self.cancelled = self.cancelled or task.cancel_requested
            task.total = self.total
            task.done = self.done
            task.note = "Stopping…" if self.cancelled else self.note
            task.last_error = self.last_error or task.last_error
            await session.commit()

    async def finish(self) -> None:
        async with AsyncSessionLocal() as session:
            task = await session.get(WorkerTask, TASK)
            if task is not None:
                task.running = False
                task.cancel_requested = False
                task.request = None
                task.note = None
                task.done = self.done
                task.last_error = self.last_error or task.last_error
                task.finished_at = utcnow()
                await session.commit()

    async def sleep(self, seconds: float) -> None:
        """Sleep in short steps so a cancel takes effect quickly."""
        end = asyncio.get_running_loop().time() + seconds
        while not self.cancelled:
            left = end - asyncio.get_running_loop().time()
            if left <= 0:
                return
            await asyncio.sleep(min(2.0, left))
            await self.save()


async def _process(run: _Run, tickers: list[str]) -> None:
    for ticker in tickers:
        if run.cancelled:
            return
        try:
            await sync_ticker(ticker, with_dividends=False)
        except Exception as exc:  # noqa: BLE001 - keep going
            run.last_error = f"{ticker}: {exc}"
            log.warning("Screener sync failed for %s: %s", ticker, exc)
        finally:
            run.done += 1
        try:
            async with AsyncSessionLocal() as session:
                await mark_done(session, "fundamentals", [ticker])
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - ordering only; keep going
            log.warning("Could not stamp sync attempt for %s: %s", ticker, exc)
        await run.save()
        if settings.screener_sync_throttle:
            await asyncio.sleep(settings.screener_sync_throttle)


async def _run_all(run: _Run) -> None:
    """Batches of never-tried stocks until none are left, gently paced."""
    log.info("Screener 'sync all' running (%d to go)", run.total - run.done)
    empty_streak = 0
    while not run.cancelled:
        batch = (await never_tried())[: settings.screener_sync_limit]
        if not batch:
            break
        run.note = f"Syncing a batch of {len(batch)}"
        await _process(run, batch)
        await invalidate_cache()  # let the screener show progress as it goes
        if run.cancelled:
            break
        if await _with_data(batch) == 0:
            empty_streak += 1
            if empty_streak >= settings.screener_sync_max_empty_batches:
                run.last_error = (
                    f"{empty_streak} batches in a row returned no data: the provider "
                    "may be rate-limiting. Stopped; try again later."
                )
                break
            run.note = "A batch returned no data (possibly rate-limited): waiting 15 min"
            await run.save()
            await run.sleep(settings.screener_sync_blocked_wait)
        else:
            empty_streak = 0
            pause = settings.screener_sync_batch_pause
            run.note = f"Pausing {pause:.0f}s between batches"
            await run.save()
            await run.sleep(pause)


async def _execute(task: WorkerTask) -> None:
    run = _Run(task.mode, task.total, task.done)
    request = task.request or {}
    try:
        if task.mode == "all":
            await _run_all(run)
        else:
            tickers = [str(t) for t in request.get("tickers", [])][task.done :]
            log.info("Screener sync running for %d tickers", len(tickers))
            await _process(run, tickers)
    except asyncio.CancelledError:
        # The worker is stopping: leave the task running (progress is saved
        # after every stock) so the next worker resumes it.
        log.info("Screener sync interrupted after %d; resumes on next start", run.done)
        raise
    except Exception as exc:
        run.last_error = str(exc)[:300]
        log.exception("Screener sync failed")
    # Fresh fundamentals -> recompute recommendation scores; and release the
    # task, or the button stays stuck on "Syncing".
    await invalidate_cache()
    await run.finish()
    log.info("Screener sync finished (%d processed)", run.done)


async def run_requested() -> bool:
    """Claim and run a run the API asked for. False if there was none."""
    async with AsyncSessionLocal() as session:
        claimed = await session.execute(
            update(WorkerTask)
            .where(WorkerTask.name == TASK, WorkerTask.requested_at.is_not(None))
            .values(requested_at=None, started_at=utcnow(), note=None)
        )
        await session.commit()
        if _rowcount(claimed) == 0:
            return False
        task = await session.get(WorkerTask, TASK)
    if task is None:
        return False
    await _execute(task)
    return True


async def resume_interrupted() -> bool:
    """On worker start: continue a run the previous worker didn't finish."""
    async with AsyncSessionLocal() as session:
        task = await session.get(WorkerTask, TASK)
    if task is None or not task.running or task.requested_at is not None:
        return False
    log.info("Resuming the screener sync interrupted by a restart (%d done)", task.done)
    await _execute(task)
    return True
