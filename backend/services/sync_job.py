"""
services/sync_job.py
--------------------
In-process background job that fills **missing fundamentals** for the screener.

Only one run at a time; fundamentals-only (no dividends) to halve provider
calls; paced by the shared governor. Progress is tracked in memory (this app
runs as a single process).
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from database import AsyncSessionLocal
from models import Fundamental, Stock
from services.fundamentals import sync_ticker
from services.recommendation import invalidate_cache

log = logging.getLogger("bursa.sync_job")

_state: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "last_error": None,
    "started_at": None,
    "finished_at": None,
}


async def missing_tickers() -> list[str]:
    """Tracked stocks that have no fundamentals yet (blank PBV/RoE/sector)."""
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Stock.ticker)
                .where(~Stock.ticker.in_(select(Fundamental.ticker).distinct()))
                .order_by(Stock.ticker)
            )
        ).scalars().all()
    return list(rows)


def status() -> dict:
    return {
        "running": _state["running"],
        "total": _state["total"],
        "done": _state["done"],
        "remaining": max(0, _state["total"] - _state["done"]),
        "last_error": _state["last_error"],
    }


async def _run(tickers: list[str]) -> None:
    log.info("Screener sync started for %d tickers", len(tickers))
    for ticker in tickers:
        try:
            await sync_ticker(ticker, with_dividends=False)
        except Exception as exc:  # noqa: BLE001 - keep going
            _state["last_error"] = f"{ticker}: {exc}"
            log.warning("Screener sync failed for %s: %s", ticker, exc)
        finally:
            _state["done"] += 1

    # Fresh fundamentals -> recompute recommendation scores next request.
    invalidate_cache()
    _state["running"] = False
    _state["finished_at"] = datetime.utcnow()
    log.info("Screener sync finished (%d tickers)", len(tickers))


def start(tickers: list[str]) -> bool:
    """Queue a background sync. Returns False if one is already running."""
    if _state["running"]:
        return False
    _state.update(
        running=True,
        total=len(tickers),
        done=0,
        last_error=None,
        started_at=datetime.utcnow(),
        finished_at=None,
    )
    asyncio.create_task(_run(tickers))
    return True
