"""
main.py
-------
FastAPI application entrypoint for "Bursa" — personal IDX stock monitor.

This module only wires things together: settings, middleware, the lifespan
and the routers. The API only serves requests: prepare.py migrates and seeds
the database before it starts, and the worker process (worker.py) runs the
scheduler and every background job. The code is organized by feature
(accounts, market, signals, portfolio, alerts, assistant, mail, system), each
with its own models, schemas, logic and routes.

Every /api route needs a signed-in user (session cookie) except /api/health
and the sign-in flow under /api/auth. Admin-only routes say so in their router.

Endpoints
~~~~~~~~~
GET    /api/health
POST   /api/auth/login                      (accounts/routes/auth.py)
GET    /api/admin/users                     (accounts/routes/admin.py, admins only)
GET    /api/indexes                         (system/routes/meta.py)
GET    /api/stocks?index=LQ45               (market/routes/stocks.py)
GET    /api/stocks/{ticker}/history
GET    /api/stocks/{ticker}/fundamentals
GET    /api/watchlist                       (portfolio/routes/watchlist.py)
POST   /api/watchlist/{ticker}
DELETE /api/watchlist/{ticker}
POST   /api/watchlist/refresh
"""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

import mail as mail_service
from accounts.crypto import ensure_secret
from accounts.routes import admin, auth, preferences, two_factor
from alerts import routes as alert_routes
from assistant import routes as assistant_routes
from config import settings
from deps import current_user, require_admin
from mail import routes as mail_routes
from market.routes import indices, overview, stocks
from portfolio.routes import portfolio, watchlist
from signals import routes as screener_routes
from system.routes import data_health, meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("bursa")
# Alembic logs a line per autogenerate plugin on import; keep only migration work.
logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup checks only; the database is prepared by prepare.py."""
    ensure_secret()  # load the 2FA server secret now, so a problem shows at once
    if mail_service.configured() and mail_service.status()["provider"] == "console":
        log.warning("DEVELOPMENT EMAIL: messages (2FA codes, reset links) are printed to "
                    "this log, not sent. Never use MAIL_PROVIDER=console on a real server.")
    log.info("Bursa API ready")
    yield


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
app.include_router(two_factor.router)  # 2FA: second step (public) + your own methods
app.include_router(admin.router)  # admins only (router dependency)
app.include_router(meta.router, dependencies=signed_in)
app.include_router(stocks.router, dependencies=signed_in)
app.include_router(watchlist.router, dependencies=signed_in)
app.include_router(portfolio.router, dependencies=signed_in)
app.include_router(screener_routes.router, dependencies=signed_in)
app.include_router(overview.router, dependencies=signed_in)
app.include_router(alert_routes.router, dependencies=signed_in)
app.include_router(preferences.router, dependencies=signed_in)
app.include_router(assistant_routes.router, dependencies=signed_in)
app.include_router(indices.router, dependencies=signed_in)
app.include_router(data_health.router, dependencies=admins)  # server internals
app.include_router(mail_routes.router, dependencies=admins)  # server-wide email setup
