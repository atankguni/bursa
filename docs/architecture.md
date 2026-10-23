# Architecture

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.14, FastAPI, SQLAlchemy 2.0 (async) + aiosqlite, APScheduler, yfinance |
| Database | SQLite by default (WAL mode, persisted on the host); PostgreSQL supported |
| Frontend | React 19 + Vite, TypeScript, Tailwind CSS, TanStack Query, lightweight-charts, lucide-react |
| Infra    | Docker Compose (single stack) + nginx |

## Project structure

```
bursa/
├── docker-compose.yml
├── docs/                  # this documentation
├── backend/
│   ├── main.py            # the API: settings, middleware, routers (serves requests only)
│   ├── worker.py          # the worker: scheduler + every background job
│   ├── prepare.py         # before start: secret, migrations, seed, setup link
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
│   ├── scheduler.py       # APScheduler jobs (prices, fundamentals, indices, retention); worker only
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
  and paced "Sync all" jobs, run by the worker. The watchlist's fundamentals also refresh daily (~18:00 WIB)
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

All data access goes through **SQLAlchemy** on SQLite or PostgreSQL. The few things
the two disagree on are kept in one adapter package, `backend/db/`, so services never
contain database-specific code:

| Module | What it hides |
|---|---|
| `db/upsert.py` | Insert-or-update (`ON CONFLICT`), chunked under each database's parameter limit. |
| `db/maintenance.py` | SQLite pragmas (WAL, busy timeout, foreign keys), WAL checkpoints and the weekly `VACUUM`. PostgreSQL gets `VACUUM (ANALYZE)`. |
| `db/migrate.py` | Runs **Alembic** migrations on startup. Refuses a database from before the 2026-10-23 squash (convert it: `scripts/convert_db.py`). |
| `db/types.py` | `UTCDateTime` (timezone-aware UTC only) and `one_of()`, a CHECK constraint built from a `Literal` in `schemas.py`. |

**Schema.** The main tables and their keys:

| Table | Key | Holds |
|---|---|---|
| `stocks` | `ticker` | The catalog. `ticker` is the IDX code (`BBCA`); Yahoo's `.JK` symbol exists only inside the Yahoo provider. Every stock foreign key is `ON UPDATE CASCADE`, so a renamed code is one update. |
| `daily_bars` | `ticker, day` | One bar per trading day (`day` is a date). `WITHOUT ROWID` on SQLite: rows are stored in key order. |
| `intraday_bars` | `ticker, timestamp` | 1-minute bars, pruned after the retention window. |
| `stock_quotes` | `ticker` | Latest and previous close per stock, rewritten by every daily sync (`market/quotes.py`). Screens and lists read this instead of searching the bars. |
| `indices`, `stock_indices`, `index_bars` | `code`; `index_code, ticker`; `code, day` | The index catalog with its latest value, memberships and daily closes. |
| `fundamentals`, `stock_profiles`, `dividends`, `splits` | per stock (+ year / ex-date) | Company data from the providers. |
| `sync_state` | `ticker, job` | When each sync job last finished per stock (listing, history backfill, full history, splits, fundamentals). Job bookkeeping stays off the data tables. |
| `rating_snapshots` | `style, day, ticker` | The daily ratings behind the live track record. |
| `user_settings` | `user_id` | One typed row per user: style, assistant and digest switches, alerts-seen marker, display and trading-cost JSON. |
| `watchlist`, `rating_state` | `user_id, ticker` | Per-user lists and the last rating seen (rating-change alerts). |
| `transactions`, `alerts`, `alert_events` | `id` | Per-user records. Quantities are whole shares (`BIGINT`); prices stay `DOUBLE` (exact for whole rupiah far beyond any real amount). |

Value sets (roles, trade sides, alert types, ratings, styles, chat roles, ...) are
CHECK constraints generated from the same `Literal` types as the API and the
frontend, and amounts have range checks (quantity and price > 0, fees >= 0).
Constraint names follow one convention (`pk_`, `fk_`, `uq_`, `ix_`, `ck_`), set on
`Base.metadata`.

Portability rules for new queries (`make check` runs the tests on both databases to catch these):

- Use `db.upsert.upsert()` instead of a dialect's `insert(...).on_conflict_...`.
- Compute dates in Python (`date.today() - timedelta(...)`), not with SQL date functions.
- Don't rely on where `NULL` sorts. Sort on `column.is_not(None)` first when it matters.
- `GROUP BY` must cover every selected non-aggregated column. Group on the exact
  expression you select, and inline constants rather than binding them.
- Use `Double` for numbers, not `Float` (4-byte `REAL` on PostgreSQL).

MongoDB is not supported: it isn't SQL, and supporting it would need a repository
layer over every query.

## Accounts & security

Invite-only accounts (`services/auth.py`, `routers/auth.py`, `routers/admin.py`):

- **Passwords** are hashed with Argon2id (`argon2-cffi`). Sign-in takes the same time
  whether or not the email exists, and failures are throttled per email and per IP
  (stored in `login_failures`, so every API process counts them).
- **Sessions** are random 256-bit tokens in an `HttpOnly`, `SameSite=Lax` cookie
  (`Secure` with `SESSION_COOKIE_SECURE`). Only the token's SHA-256 is stored, so a
  database copy can't be used to sign in. Sessions slide while in use and are deleted
  on sign-out, password change/reset or when an admin disables the account.
- **CSRF**: besides SameSite, a middleware in `main.py` refuses POST/PUT/PATCH/DELETE
  whose `Origin` isn't the app's own host, `PUBLIC_URL` or `CORS_ORIGINS`.
- **Invite and reset links** are one-time tokens, also stored hashed, that expire
  (`INVITE_DAYS`, `PASSWORD_RESET_HOURS`). A daily job deletes expired sessions and links.
- **Two-factor** (`services/two_factor.py`, `routers/two_factor.py`): after the
  password, `/api/auth/login` returns a short-lived challenge instead of a session.
  TOTP is RFC 6238 (standard library, ±1 step, each code accepted once). Secrets are
  encrypted with Fernet and recovery / emailed codes stored as HMAC-SHA256, both
  keyed by the server secret (`services/crypto.py`). Each challenge allows
  `MFA_MAX_ATTEMPTS` wrong codes, which also count toward sign-in throttling.
  "Remember this device" is a separate HttpOnly cookie limited to `/api/auth`.
  `deps.current_user` holds admins without 2FA at the setup (403); `signed_in_user`
  skips that check for `/me` and the 2FA endpoints. Password resets keep 2FA on.
- **Routing**: `main.py` mounts every router behind the `current_user` dependency,
  except `/api/health` and the public `/api/auth` routes. Admin-only routes add
  `require_admin` (data health, mail, syncs, tracking, Telegram, user management).

**Per-user data.** `watchlist`, `transactions`, `alerts`, `alert_events`,
`user_settings` and `rating_state` have a required `user_id`; every query filters by
the signed-in user. `user_settings` also holds the account part of the Settings menu
(the `display` JSON document) and the alerts-seen marker; the frontend
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

## Processes: API and worker

The backend image runs as two services (`docker-compose.yml`):

| Process | Runs | Count |
|---|---|---|
| `backend` (API, `main.py`) | `prepare.py` once (secret, migrations, seed), then uvicorn. Serves requests only. | `API_WORKERS` processes (default 1) |
| `worker` (`worker.py`) | The scheduler, the startup catch-up syncs, and long jobs the API asks for (Sync all). | exactly 1 |

So a slow Yahoo call or a crashing job never slows a page, and restarting the API
doesn't stop a sync. The two share **nothing but the database**
(`services/worker_state.py`, `services/sync_job.py`, `services/data_version.py`):

- **Heartbeat:** the worker writes `worker_status` every 30 s (with its provider call
  counters and last price sync). Data health shows "Worker not running" when it is
  older than 2 minutes, and the Screener says a queued sync waits for the worker.
- **Scheduled jobs:** each job's next run and last outcome go to `scheduled_jobs`, which
  the data-health page reads.
- **Sync all / Sync missing:** the API writes a request to `worker_tasks`; the worker
  claims it (a conditional update, so two clicks can't start two runs), saves progress
  after every stock and checks the cancel flag. If the worker stops mid-run (deploy,
  crash), the run stays "running" and the next worker resumes it where it left off.
- **Cache invalidation:** after new fundamentals, `data_versions.scores` is bumped; each
  API process sees the new number on its next request and recomputes its cached scores.
- **Per-user limits** (sign-in throttling, the assistant's daily cap) are rows too, so
  they hold across several API processes.

The API still calls the provider for a few things a click needs at once: symbol search,
a chart's full history the first time, adding a stock to the watchlist, Refresh.

## Architecture & rate-limiting

Temporary data lives in two places; no external cache service is used:

- **The database is the durable cache / source of truth.** The API serves reads from
  it, never from the provider, so browsing never hits Yahoo.
- **Per-process TTL caches** for derived/volatile data:
  - recommendation scores: `recommendation_cache_seconds` (60s), dropped early when
    the data changes (`data_versions`);
  - FX rates: `fx_cache_hours` (6h);
  - symbol search: `search_cache_seconds` (300s).

**Anti-blacklist:** all outbound provider calls go through a central **governor**
(`market/providers/governor.py`). It caps concurrency, spaces calls
(`provider_min_interval_ms`) and dedupes concurrent identical calls (single-flight).
It also records per-provider metrics, exposed at `GET /api/providers` (the worker's
and the API's added up) and summarized in a daily log line at 23:00 WIB. The governor
is per process; the worker makes nearly all calls. Together with batched `yf.download`, market-hours-only
intraday syncing and DB-backed staleness checks, this prevents bursts.

**Why not Redis?** The few things processes must share (job requests, progress,
heartbeats, cache versions, throttling) are small and change rarely, so they live in
the database the app already has. Each API process keeps its own cache of the scored
universe; the shared version number keeps them correct. Redis becomes worthwhile when
several machines run the API, or for caching heavier than that.

## Frontend delivery

The frontend is a static build served by nginx (gzipped, immutable caching,
`/api` reverse-proxied). The chart library and heavier routes are code-split and
loaded on demand.

nginx is the only way in from the network: the backend's port 8000 is bound to
`127.0.0.1`, because the backend trusts the client-IP header (`X-Real-IP`) that
nginx sets. Every response carries security headers
(`frontend/security-headers.conf`): a Content-Security-Policy that allows
scripts only from the site itself (no inline scripts; the theme is applied by
`public/theme-init.js`), no framing, `nosniff`, a same-origin referrer policy,
and no camera/microphone/location access. Put HTTPS (and HSTS) on a proxy in
front of nginx when exposing Bursa beyond your network.

## Limitations

- **ISSI** is a seeded subset of well-known sharia names, not the full ~500 constituents.
- Fundamentals are fetched **per ticker** (yfinance has no batch statement API), so syncing is throttled.
- yfinance may occasionally rate-limit or omit a ticker; failed jobs are retried and never crash the app.
- Yahoo has no long history for some smaller indices; they build up daily from first sync.
- Run exactly one worker: two would run every scheduled job twice (there is no
  leader election).
- No passkeys (WebAuthn) yet; they need HTTPS on the final domain.
- Telegram delivery uses one server-wide chat, so only admins' alerts are sent there.
