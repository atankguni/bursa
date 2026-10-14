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
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config import settings
from database import init_db
from routers import alerts, market, meta, portfolio, screener, stocks, watchlist
from scheduler import (
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB -> seed -> purge stale -> backfill -> start scheduler."""
    await init_db()
    await seed()

    # Drop fundamentals rows written before currency-aware storage.
    await purge_stale_fundamentals()

    # Blocking initial backfill so charts have data immediately after boot.
    await backfill_daily()

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
