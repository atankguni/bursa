"""
main.py
-------
FastAPI application entrypoint for "Bursa" — personal IDX stock monitor.

This module only wires things together: settings, middleware, the lifespan
(DB init -> seed -> backfill -> scheduler) and the routers. Business logic
lives in `services/` and market integration in `market/`.

Endpoints
~~~~~~~~~
GET    /api/health
GET    /api/indexes                         (routers/meta.py)
GET    /api/stocks?index=LQ45               (routers/stocks.py)
GET    /api/stocks/{ticker}/history
GET    /api/stocks/{ticker}/fundamentals
GET    /api/watchlist                       (routers/watchlist.py)
POST   /api/watchlist/{ticker}
DELETE /api/watchlist/{ticker}
POST   /api/watchlist/refresh
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import func, select

from config import settings
from database import init_db
from models import StockPrice
from routers import (
    alerts,
    assistant,
    data_health,
    indices,
    market,
    meta,
    portfolio,
    preferences,
    screener,
    stocks,
    watchlist,
)
from scheduler import (
    TICKERS,
    backfill_active,
    backfill_daily,
    catch_up_intraday,
    refresh_index_quotes,
    start_scheduler,
    stop_scheduler,
    sync_splits_active,
    sync_watchlist_fundamentals,
)
from services.bootstrap import purge_stale_fundamentals, seed
from services.idx_listing import sync_if_stale as sync_idx_listing_if_stale
from services.market_clock import last_closed_trading_day

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("bursa")
# Alembic logs a line per autogenerate plugin on import; keep only migration work.
logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)

# Strong references to fire-and-forget startup jobs: the event loop only keeps
# weak ones, so an unreferenced task can be garbage-collected mid-run.
_background: set[asyncio.Task[None]] = set()


def _spawn(coro: Coroutine[object, object, None]) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _catalog_coverage() -> float:
    """Fraction of catalog tickers that have the last *finished* trading day's bar."""
    from database import AsyncSessionLocal

    day = last_closed_trading_day()
    async with AsyncSessionLocal() as session:
        have = (
            await session.execute(
                select(func.count(func.distinct(StockPrice.ticker))).where(
                    StockPrice.interval == "1d",
                    StockPrice.timestamp >= datetime.combine(day, datetime.min.time()),
                )
            )
        ).scalar_one()
    return have / max(1, len(TICKERS))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: init DB -> seed -> purge stale -> backfill -> start scheduler."""
    await init_db()
    await seed()

    # Drop fundamentals rows written before currency-aware storage.
    await purge_stale_fundamentals()

    # Fast startup backfill for the active set; the full catalog sync runs in
    # the background only when coverage is low (first boot), keeping restarts fast.
    await backfill_active()
    # Catalog incomplete for the last finished trading day (first boot, or the
    # 16:30 job was missed): fetch it in the background.
    if await _catalog_coverage() < 0.8:
        _spawn(backfill_daily())

    start_scheduler()

    # Refresh watchlist fundamentals in the background (non-blocking startup).
    _spawn(sync_watchlist_fundamentals())
    _spawn(refresh_index_quotes())
    # Listing boards / IPOs from the IDX site, if more than a week old.
    _spawn(sync_idx_listing_if_stale())
    _spawn(sync_splits_active())
    # Fill 1-minute gaps from while the app was down or the host slept.
    _spawn(catch_up_intraday("5d"))

    log.info("Bursa API ready")
    try:
        yield
    finally:
        stop_scheduler()
        # Stop unfinished startup jobs cleanly instead of leaving them pending.
        for task in _background:
            task.cancel()


app = FastAPI(
    title="Bursa API",
    description="Personal IDX (Indonesian stock exchange) monitoring backend.",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress JSON responses (saves bandwidth on the price tables).
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(meta.router)
app.include_router(stocks.router)
app.include_router(watchlist.router)
app.include_router(portfolio.router)
app.include_router(screener.router)
app.include_router(market.router)
app.include_router(alerts.router)
app.include_router(preferences.router)
app.include_router(assistant.router)
app.include_router(indices.router)
app.include_router(data_health.router)
