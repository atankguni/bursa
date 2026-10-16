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
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import func, select

from config import settings
from database import init_db
from models import StockPrice
from routers import alerts, market, meta, portfolio, screener, stocks, watchlist
from scheduler import (
    TICKERS,
    backfill_active,
    backfill_daily,
    start_scheduler,
    stop_scheduler,
    sync_watchlist_fundamentals,
)
from services.bootstrap import purge_stale_fundamentals, seed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("bursa")


async def _catalog_coverage() -> float:
    """Fraction of catalog tickers that already have daily price data."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        have = (
            await session.execute(
                select(func.count(func.distinct(StockPrice.ticker))).where(
                    StockPrice.interval == "1d"
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
    if await _catalog_coverage() < 0.5:
        asyncio.create_task(backfill_daily())

    start_scheduler()

    # Refresh watchlist fundamentals in the background (non-blocking startup).
    asyncio.create_task(sync_watchlist_fundamentals())

    log.info("Bursa API ready")
    try:
        yield
    finally:
        stop_scheduler()


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
