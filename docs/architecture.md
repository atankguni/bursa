# Architecture

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.14, FastAPI, SQLAlchemy 2.0 (async) + aiosqlite, APScheduler, yfinance |
| Database | SQLite by default (WAL mode, persisted on the host); PostgreSQL and MySQL/MariaDB supported |
| Frontend | React 19 + Vite, TypeScript, Tailwind CSS, TanStack Query, lightweight-charts, lucide-react |
| Infra    | Docker Compose (single stack) + nginx |

## Project structure

```
bursa/
├── docker-compose.yml
├── docs/                  # this documentation
├── backend/
│   ├── main.py            # app factory: settings, middleware, lifespan, routers
│   ├── config.py          # Settings (env-driven)
│   ├── deps.py            # FastAPI dependencies (get_session)
│   ├── database.py        # async engine + session factory, init_db()
│   ├── db/                # database adapter: portable upsert, maintenance, migration runner
│   ├── migrations/        # Alembic migration scripts (+ alembic.ini)
│   ├── models.py          # ORM models
│   ├── schemas.py         # Pydantic response models
│   ├── routers/           # HTTP endpoints (stocks, screener, portfolio, alerts, indices, …)
│   ├── services/          # business logic (recommendation, portfolio, risk, sync jobs, …)
│   ├── market/            # tickers, holidays, IDX site/listing, indices, providers + sync
│   ├── assistant/         # AI assistant: provider adapters, read-only tools, service
│   ├── scheduler.py       # APScheduler jobs (prices, fundamentals, indices, retention)
│   ├── scripts/           # evaluate_signals.py (backtest), gen_idx_list.py
│   ├── tests/             # pytest
│   ├── pyproject.toml     # ruff, pyright and pytest config
│   ├── requirements.txt · requirements-dev.txt
│   └── Dockerfile         # multi-stage: runtime + test targets
└── frontend/
    ├── index.html
    ├── src/
    │   ├── App.tsx            # shell + routes
    │   ├── pages/             # Home, Market, Browse, Screener, Watchlist, Portfolio, Alerts, DataHealth
    │   ├── components/        # navbar, charts, modals, panels
    │   ├── api/               # typed API client
    │   ├── hooks/             # React Query hooks + keys
    │   └── lib/               # formatting, theme, helpers
    ├── public/                # favicons, manifest
    ├── package.json
    └── Dockerfile
```

## Data & sync

The app uses **tiered sync** so the free Yahoo API is never hammered:

- **Catalog (all ~960 IDX stocks)**: daily candles only, fetched **chunked**
  (`provider_chunk_size`, default 50) and paced by the governor. The catalog-wide
  backfill runs after the close (16:30 WIB). The full list lives in
  `market/idx_listed.py` (regenerate with `python scripts/gen_idx_list.py`).
- **Active set (≤ `intraday_max_symbols`, default 100)**: index constituents,
  watchlist, portfolio holdings and user-tracked symbols get **1-minute intraday**
  data every 3 minutes during market hours.
- **Fundamentals**: fetched on demand (per ticker). The Screener has capped "Sync missing"
  and paced "Sync all" jobs. The watchlist's fundamentals also refresh daily (~18:00 WIB)
  and via **Refresh**. Figures are **normalized to IDR**: foreign-currency filers (e.g. PGAS,
  which reports in USD) are converted so PBV is calculated on a consistent basis.
  Share counts are cross-checked against IDX's official register.
- **Ratios**: `PBV = market cap ÷ book value` (book value = total assets − total liabilities);
  `RoE = net income ÷ equity`.
- **Retention**: intraday (1m) data is synced **only during market hours**
  (Mon–Fri 09:00–16:00 WIB) and pruned after 5 days. The WAL is auto-checkpointed and
  VACUUMed weekly.
- **Sleep/wake**: jobs have a misfire grace window, so jobs missed while the host slept
  run on wake.

## Database layer

All data access goes through **SQLAlchemy**, which already speaks SQLite, PostgreSQL
and MySQL. The few things SQL dialects disagree on are kept in one adapter package,
`backend/db/`, so services never contain database-specific code:

| Module | What it hides |
|---|---|
| `db/upsert.py` | Insert-or-update: `ON CONFLICT` (SQLite/PostgreSQL) vs `ON DUPLICATE KEY` (MySQL). Also chunks large batches under each database's parameter limit. |
| `db/maintenance.py` | SQLite pragmas (WAL, busy timeout, foreign keys), WAL checkpoints and the weekly `VACUUM`. PostgreSQL gets `VACUUM (ANALYZE)`; MySQL needs nothing. |
| `db/migrate.py` | Runs **Alembic** migrations on startup. It also upgrades databases created before migrations existed. |

Portability rules for new queries (the test suite runs on all three databases to catch these):

- Use `db.upsert.upsert()` instead of a dialect's `insert(...).on_conflict_...`.
- Compute dates in Python (`date.today() - timedelta(...)`), not with SQL date functions.
- Don't rely on where `NULL` sorts. Sort on `column.is_not(None)` first when it matters.
- `GROUP BY` must cover every selected non-aggregated column. Group on the exact
  expression you select, and inline constants rather than binding them.
- Use `Double` for numbers, not `Float`: MySQL's `FLOAT` is 4-byte.

MongoDB is not supported: it isn't SQL, and supporting it would need a repository
layer over every query.

## Architecture & rate-limiting

Temporary data lives in two places; no external cache service is used:

- **The database is the durable cache / source of truth.** The API serves reads from
  it, never from the provider, so browsing never hits Yahoo.
- **In-process TTL caches** for derived/volatile data:
  - recommendation scores: `recommendation_cache_seconds` (60s);
  - FX rates: `fx_cache_hours` (6h);
  - symbol search: `search_cache_seconds` (300s).

**Anti-blacklist:** all outbound provider calls go through a central **governor**
(`market/providers/governor.py`). It caps concurrency, spaces calls
(`provider_min_interval_ms`) and dedupes concurrent identical calls (single-flight).
It also records per-provider metrics, exposed at `GET /api/providers` and summarized
in a daily log line at 23:00 WIB. Together with batched `yf.download`, market-hours-only
intraday syncing and DB-backed staleness checks, this prevents bursts.

**Why not Redis?** The app runs as a **single process** (one uvicorn worker with the
scheduler in-process), so in-process caches are shared by every request. Redis only
becomes worthwhile when scaling to **multiple workers/replicas** (shared cache) or
running the scheduler as a **separate service** (distributed lock). That's the
point to add a shared cache/lock, not before.

## Frontend delivery

The frontend is a static build served by nginx (gzipped, immutable caching,
`/api` reverse-proxied). The chart library and heavier routes are code-split and
loaded on demand.

## Limitations

- **ISSI** is a seeded subset of well-known sharia names, not the full ~500 constituents.
- Fundamentals are fetched **per ticker** (yfinance has no batch statement API), so syncing is throttled.
- yfinance may occasionally rate-limit or omit a ticker; failed jobs are retried and never crash the app.
- Yahoo has no long history for some smaller indices; they build up daily from first sync.
