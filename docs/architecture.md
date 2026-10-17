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
│   ├── deps.py            # FastAPI dependencies (DB session, current user, admin, style)
│   ├── database.py        # async engine + session factory, init_db()
│   ├── db/                # database adapter: portable upsert, maintenance, migration runner
│   ├── migrations/        # Alembic migration scripts (+ alembic.ini)
│   ├── models.py          # ORM models
│   ├── schemas.py         # Pydantic response models
│   ├── routers/           # HTTP endpoints (auth, admin, stocks, screener, portfolio, alerts, …)
│   ├── services/          # business logic (auth, recommendation, portfolio, risk, sync jobs, …)
│   ├── market/            # tickers, holidays, IDX site/listing, indices, providers + sync
│   ├── assistant/         # AI assistant: provider adapters, read-only tools, service
│   ├── mail/              # email: provider adapters (SMTP, Resend), service, HTML layout
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
    │   ├── pages/             # Home, Market, Browse, Screener, Watchlist, Portfolio, Alerts,
    │   │                      # DataHealth, Users; auth/ (sign in, invite, password reset)
    │   ├── components/        # navbar, charts, modals, panels
    │   ├── api/               # typed API client
    │   ├── hooks/             # React Query hooks + keys
    │   └── lib/               # auth context, formatting, theme, helpers
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

## Accounts & security

Invite-only accounts (`services/auth.py`, `routers/auth.py`, `routers/admin.py`):

- **Passwords** are hashed with Argon2id (`argon2-cffi`). Sign-in takes the same time
  whether or not the email exists, and failures are throttled per email and per IP
  (in memory: the app is one process).
- **Sessions** are random 256-bit tokens in an `HttpOnly`, `SameSite=Lax` cookie
  (`Secure` with `SESSION_COOKIE_SECURE`). Only the token's SHA-256 is stored, so a
  database copy can't be used to sign in. Sessions slide while in use and are deleted
  on sign-out, password change/reset or when an admin disables the account.
- **CSRF**: besides SameSite, a middleware in `main.py` refuses POST/PUT/PATCH/DELETE
  whose `Origin` isn't the app's own host, `PUBLIC_URL` or `CORS_ORIGINS`.
- **Invite and reset links** are one-time tokens, also stored hashed, that expire
  (`INVITE_DAYS`, `PASSWORD_RESET_HOURS`). A daily job deletes expired sessions and links.
- **Routing**: `main.py` mounts every router behind the `current_user` dependency,
  except `/api/health` and the public `/api/auth` routes. Admin-only routes add
  `require_admin` (data health, mail, syncs, tracking, Telegram, user management).

**Per-user data.** `watchlist`, `transactions`, `alerts`, `alert_events`,
`user_preferences` and `rating_state` have a `user_id`; every query filters by the
signed-in user. `user_preferences` also holds the account part of the Settings menu
(one JSON document, `display_settings`) and the alerts-seen marker; the frontend
(`lib/settings.tsx`, `ACCOUNT_KEYS`) keeps a local copy for instant rendering and
syncs it after sign-in. Appearance settings stay in the browser only. Market data is shared. Signals depend on the investing style, so the
scoring cache is keyed by style and routes pass the user's style
(`deps.user_style`). Alert evaluation runs per user with their own style and rating
baselines. Rows from before accounts existed have no owner until the first admin
accepts the setup invite and claims them.

## Email

`backend/mail/` is a provider-neutral mail service, built the same way as the
assistant's provider layer:

| Module | Role |
|---|---|
| `mail/base.py` | `Email` / `Attachment` types, `MailError` (permanent) and `MailBusyError` (retry later), validation, and the `MailProvider` interface |
| `mail/smtp.py`, `mail/resend.py` | Adapters; standard library only, no extra packages |
| `mail/registry.py` | Picks the adapter named by `MAIL_PROVIDER` |
| `mail/service.py` | The only entry point: `send()` raises errors, `send_quietly()` logs them (for background jobs) |
| `mail/templates.py` | `layout()`: a shared, inline-styled HTML frame for emails |

```python
from mail import Email, send_quietly
from mail.templates import layout

await send_quietly(Email(subject="…", text=plain, html=layout("Title", body_html)))
```

Callers never see SMTP or a vendor API. Sender and recipients default to `MAIL_FROM` /
`MAIL_TO`. Messages are validated before sending (no line breaks in headers, valid
addresses), and logs record only the subject and recipient count, never addresses,
content or credentials.

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
- Sign-in throttling is kept in memory, so it resets on restart and assumes a single
  backend process.
- Telegram delivery uses one server-wide chat, so only admins' alerts are sent there.
