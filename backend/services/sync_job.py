"""
services/sync_job.py
--------------------
In-process background job that fills **missing fundamentals** for the screener.

Only one run at a time; fundamentals-only (no dividends) to halve provider
calls; paced by the shared governor. Progress is tracked in memory (this app
runs as a single process).

Each attempt is stamped on `Stock.fundamentals_checked_at` and the queue is
ordered never-tried first, then least-recently tried. Without that, tickers the
provider has no statements for stay "missing" forever and, being first
alphabetically, would fill every capped run.
"""

import asyncio
import logging
from datetime import datetime
from typing import TypedDict

from sqlalchemy import ColumnElement, func, select, update

from config import settings
from database import AsyncSessionLocal
from models import Fundamental, Stock, StockProfile
from services.fundamentals import sync_ticker
from services.recommendation import invalidate_cache

log = logging.getLogger("bursa.sync_job")



class _State(TypedDict):
    running: bool
    mode: str  # "batch" (one capped run) | "all" (batches until done)
    total: int
    done: int
    last_error: str | None
    note: str | None  # what the job is doing now (e.g. pausing between batches)
    cancel: bool
    started_at: datetime | None
    finished_at: datetime | None


class SyncStatus(TypedDict):
    running: bool
    mode: str
    total: int
    done: int
    remaining: int
    last_error: str | None
    note: str | None


_state: _State = {
    "running": False,
    "mode": "batch",
    "total": 0,
    "done": 0,
    "last_error": None,
    "note": None,
    "cancel": False,
    "started_at": None,
    "finished_at": None,
}
# Strong reference to the running task (the event loop only keeps a weak one).
_task: asyncio.Task | None = None


def _missing_clause() -> ColumnElement[bool]:
    return ~Stock.ticker.in_(select(Fundamental.ticker).distinct())


async def missing_tickers() -> list[str]:
    """Stocks without fundamentals, never-tried first, then least-recently tried."""
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Stock.ticker)
                .where(_missing_clause())
                # SQLite sorts NULL first ascending -> never-tried lead the queue.
                .order_by(Stock.fundamentals_checked_at, Stock.ticker)
            )
        ).scalars().all()
    return list(rows)


async def missing_count() -> int:
    async with AsyncSessionLocal() as session:
        return (
            await session.execute(select(func.count()).select_from(Stock).where(_missing_clause()))
        ).scalar_one()


async def _mark_checked(ticker: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Stock)
            .where(Stock.ticker == ticker)
            .values(fundamentals_checked_at=datetime.utcnow())
        )
        await session.commit()


async def never_tried() -> list[str]:
    """Stocks without fundamentals that have never been attempted."""
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Stock.ticker)
                .where(_missing_clause(), Stock.fundamentals_checked_at.is_(None))
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


def status() -> SyncStatus:
    return {
        "running": _state["running"],
        "mode": _state["mode"],
        "total": _state["total"],
        "done": _state["done"],
        "remaining": max(0, _state["total"] - _state["done"]),
        "last_error": _state["last_error"],
        "note": _state["note"],
    }


def cancel() -> bool:
    """Ask a running job to stop after the current stock. False if none is running."""
    if not _state["running"]:
        return False
    _state["cancel"] = True
    _state["note"] = "Stopping…"
    return True


async def _sleep(seconds: float) -> None:
    """Sleep in short steps so a cancel takes effect quickly."""
    end = asyncio.get_running_loop().time() + seconds
    while not _state["cancel"]:
        left = end - asyncio.get_running_loop().time()
        if left <= 0:
            return
        await asyncio.sleep(min(1.0, left))


async def _process(tickers: list[str]) -> None:
    for ticker in tickers:
        if _state["cancel"]:
            return
        try:
            await sync_ticker(ticker, with_dividends=False)
        except Exception as exc:  # noqa: BLE001 - keep going
            _state["last_error"] = f"{ticker}: {exc}"
            log.warning("Screener sync failed for %s: %s", ticker, exc)
        finally:
            _state["done"] += 1
        try:
            await _mark_checked(ticker)
        except Exception as exc:  # noqa: BLE001 - ordering only; keep going
            log.warning("Could not stamp sync attempt for %s: %s", ticker, exc)
        if settings.screener_sync_throttle:
            await asyncio.sleep(settings.screener_sync_throttle)


async def _run_all() -> None:
    """Batches of never-tried stocks until none are left, gently paced."""
    log.info("Screener 'sync all' started for %d tickers", _state["total"])
    empty_streak = 0
    try:
        while not _state["cancel"]:
            batch = (await never_tried())[: settings.screener_sync_limit]
            if not batch:
                break
            _state["note"] = f"Syncing a batch of {len(batch)}"
            await _process(batch)
            invalidate_cache()  # let the screener show progress as it goes
            if _state["cancel"]:
                break
            if await _with_data(batch) == 0:
                empty_streak += 1
                if empty_streak >= settings.screener_sync_max_empty_batches:
                    _state["last_error"] = (
                        f"{empty_streak} batches in a row returned no data: the provider "
                        "may be rate-limiting. Stopped; try again later."
                    )
                    break
                _state["note"] = "A batch returned no data (possibly rate-limited): waiting 15 min"
                await _sleep(settings.screener_sync_blocked_wait)
            else:
                empty_streak = 0
                pause = settings.screener_sync_batch_pause
                _state["note"] = f"Pausing {pause:.0f}s between batches"
                await _sleep(settings.screener_sync_batch_pause)
    finally:
        invalidate_cache()
        _state.update({"running": False, "finished_at": datetime.utcnow(), "cancel": False,
                       "note": None})
    log.info("Screener 'sync all' finished (%d processed)", _state["done"])


async def _run(tickers: list[str]) -> None:
    """One capped run over `tickers` (the regular "Sync missing" click)."""
    log.info("Screener sync started for %d tickers", len(tickers))
    try:
        await _process(tickers)
        # Fresh fundamentals -> recompute recommendation scores next request.
        invalidate_cache()
    finally:
        # Always release the lock, or the button stays stuck on "Syncing".
        _state.update({"running": False, "finished_at": datetime.utcnow(), "cancel": False,
                       "note": None})
    log.info("Screener sync finished (%d tickers)", len(tickers))


def start(tickers: list[str]) -> bool:
    """Queue a background sync. Returns False if one is already running."""
    global _task
    if _state["running"]:
        return False
    _state.update(
        {
            "running": True,
            "mode": "batch",
            "total": len(tickers),
            "done": 0,
            "last_error": None,
            "note": None,
            "cancel": False,
            "started_at": datetime.utcnow(),
            "finished_at": None,
        }
    )
    _task = asyncio.create_task(_run(tickers))
    return True


async def start_all() -> bool:
    """Queue 'sync all' (every never-tried stock). False if a job is already running."""
    global _task
    if _state["running"]:
        return False
    _state.update(
        {
            "running": True,
            "mode": "all",
            "total": len(await never_tried()),
            "done": 0,
            "last_error": None,
            "note": "Starting…",
            "cancel": False,
            "started_at": datetime.utcnow(),
            "finished_at": None,
        }
    )
    _task = asyncio.create_task(_run_all())
    return True
