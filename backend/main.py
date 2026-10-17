"""
main.py
-------
FastAPI application entrypoint for "Bursa" — personal IDX stock monitor.

This module only wires things together: settings, middleware, the lifespan
(DB init -> seed -> backfill -> scheduler) and the routers. Business logic
lives in `services/` and market integration in `market/`.

Every /api route needs a signed-in user (session cookie) except /api/health
and the sign-in flow under /api/auth. Admin-only routes say so in their router.

Endpoints
~~~~~~~~~
GET    /api/health
POST   /api/auth/login                      (routers/auth.py)
GET    /api/admin/users                     (routers/admin.py, admins only)
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
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from config import settings
from database import init_db
from deps import current_user, require_admin
from models import StockPrice
from routers import (
    admin,
    alerts,
    assistant,
    auth,
    data_health,
    indices,
    mail,
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
from services.auth import ensure_setup_invite
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
    # Fresh install: log the one-time link that creates the first admin.
    await ensure_setup_invite()

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

_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


_TRUSTED_ORIGINS = {_origin(u) for u in [settings.public_url, *settings.cors_origins]}


@app.middleware("http")
async def check_origin(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    CSRF defence on top of the SameSite=Lax cookie: a browser always sends
    Origin with cross-site writes, so a write from another site is refused.
    Requests without Origin (curl, scripts) carry no browser cookies to abuse.
    """
    origin = request.headers.get("origin")
    if request.method in _UNSAFE and origin:
        same_host = urlsplit(origin).netloc.lower() == request.headers.get("host", "").lower()
        # "null" (sandboxed frames, file://) has no netloc, so it is refused too.
        if origin == "null" or not (same_host or _origin(origin) in _TRUSTED_ORIGINS):
            return JSONResponse({"detail": "Cross-site request refused"}, status_code=403)
    return await call_next(request)


signed_in = [Depends(current_user)]
admins = [Depends(require_admin)]

app.include_router(meta.public)  # /api/health
app.include_router(auth.router)  # sign-in flow (public; /me and /password check the cookie)
app.include_router(admin.router)  # admins only (router dependency)
app.include_router(meta.router, dependencies=signed_in)
app.include_router(stocks.router, dependencies=signed_in)
app.include_router(watchlist.router, dependencies=signed_in)
app.include_router(portfolio.router, dependencies=signed_in)
app.include_router(screener.router, dependencies=signed_in)
app.include_router(market.router, dependencies=signed_in)
app.include_router(alerts.router, dependencies=signed_in)
app.include_router(preferences.router, dependencies=signed_in)
app.include_router(assistant.router, dependencies=signed_in)
app.include_router(indices.router, dependencies=signed_in)
app.include_router(data_health.router, dependencies=admins)  # server internals
app.include_router(mail.router, dependencies=admins)  # server-wide email setup
