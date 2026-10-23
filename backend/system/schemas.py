"""
system/schemas.py
-----------------
API models (Pydantic) for the API and worker processes.
"""

from datetime import date, datetime
from typing import Literal

from market.schemas import MarketSession, ProviderStat
from schemas import Schema

# Long-running work the API asks the worker to do (system.models.WorkerTask).
WorkerTaskName = Literal["fundamentals_sync"]


# Cached results that other processes must drop when the data changes (system.models.DataVersion).
DataName = Literal["scores"]


class StatusOut(Schema):
    """Global status for the app footer."""

    server_time: datetime
    timezone: str
    session: MarketSession
    last_sync: datetime | None = None
    stocks_tracked: int = 0
    providers: dict[str, str] = {}
    calls_today: dict[str, int] = {}
    lot_size: int = 100


# --------------------------------------------------------------------------- #
# Data health
# --------------------------------------------------------------------------- #
HealthStatus = Literal["ok", "warn", "error"]


class JobHealth(Schema):
    id: str
    description: str
    next_run: datetime | None = None
    last_run: datetime | None = None
    ok: bool | None = None  # None: hasn't run yet
    error: str | None = None


class TickerIssue(Schema):
    ticker: str
    issue: str


class ProviderHealth(ProviderStat):
    name: str


class JobsHealth(Schema):
    status: HealthStatus
    items: list[JobHealth]
    # The worker process's last heartbeat; error status when it is too old.
    worker_seen_at: datetime | None = None
    worker_running: bool = False


class ProvidersHealth(Schema):
    status: HealthStatus
    items: list[ProviderHealth]


class PricesHealth(Schema):
    status: HealthStatus
    trading_day: date
    stocks: int
    current: int  # with a bar for the last closed trading day
    coverage_pct: float
    no_prices: int
    stale: int  # no bar in STALE_DAYS (likely suspended or delisted)
    stale_sample: list[str]
    intraday_tickers: int
    intraday_last: datetime | None = None


class FundamentalsHealth(Schema):
    status: HealthStatus
    statements: int
    summary: int
    missing: int
    never_tried: int


class IndicesHealth(Schema):
    status: HealthStatus
    count: int
    oldest_update: datetime | None = None
    newest_update: datetime | None = None


class ListingHealth(Schema):
    status: HealthStatus
    synced_at: datetime | None = None
    boards: dict[str, int]


class SuspiciousHealth(Schema):
    status: HealthStatus
    extreme_values: list[TickerIssue]
    share_mismatches: list[TickerIssue]


class HealthSections(Schema):
    jobs: JobsHealth
    providers: ProvidersHealth
    prices: PricesHealth
    fundamentals: FundamentalsHealth
    indices: IndicesHealth
    listing: ListingHealth
    suspicious: SuspiciousHealth


class DataHealthOut(Schema):
    """Can the app's data be trusted right now? One status per area."""

    generated_at: datetime
    sections: HealthSections
    timezone_now: datetime
