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

from database import AsyncSessionLocal
from models import Fundamental, Stock
from services.fundamentals import sync_ticker
from services.recommendation import invalidate_cache

log = logging.getLogger("bursa.sync_job")



class _State(TypedDict):
    running: bool
    total: int
    done: int
    last_error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class SyncStatus(TypedDict):
    running: bool
    total: int
    done: int
    remaining: int
    last_error: str | None


_state: _State = {
    "running": False,
    "total": 0,
    "done": 0,
    "last_error": None,
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


def status() -> SyncStatus:
    return {
        "running": _state["running"],
        "total": _state["total"],
        "done": _state["done"],
        "remaining": max(0, _state["total"] - _state["done"]),
        "last_error": _state["last_error"],
    }


async def _run(tickers: list[str]) -> None:
    log.info("Screener sync started for %d tickers", len(tickers))
    try:
        for ticker in tickers:
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

        # Fresh fundamentals -> recompute recommendation scores next request.
        invalidate_cache()
    finally:
        # Always release the lock, or the button stays stuck on "Syncing".
        _state["running"] = False
        _state["finished_at"] = datetime.utcnow()
    log.info("Screener sync finished (%d tickers)", len(tickers))


def start(tickers: list[str]) -> bool:
    """Queue a background sync. Returns False if one is already running."""
    global _task
    if _state["running"]:
        return False
    _state.update(
        {
            "running": True,
            "total": len(tickers),
            "done": 0,
            "last_error": None,
            "started_at": datetime.utcnow(),
            "finished_at": None,
        }
    )
    _task = asyncio.create_task(_run(tickers))
    return True
