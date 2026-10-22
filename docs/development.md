# Development

For running the dev servers with hot reload, see [Getting started](getting-started.md#development-hot-reload).

## Checks

Everything is statically typed, and one command checks it all (the backend
runs in its Docker test image, so no local Python is needed):

```bash
make check        # everything: types, lint, format, tests, API types in sync
make check-fast   # the pre-commit subset (~10 s): no test suite
make hooks        # once per clone: run check-fast before every commit
make api-types    # after changing a response/request model in backend/schemas.py
```

### Typing rules

- **Backend:** pyright **strict** for all app code (every value has a known
  type); tests and migrations use the standard level. `Any` is allowed only at
  the boundaries where outside data arrives untyped (`market/providers/yahoo.py`,
  `assistant/providers/`, `db/maintenance.py`, migrations), and is turned into
  typed values there. Untyped libraries get small local stubs in
  `backend/typings/` (only what Bursa uses).
- **One definition per shape:** API shapes are the Pydantic models in
  `schemas.py`, and services return them directly (no TypedDict copies).
  Value sets are `Literal` aliases there too (`TradeSide`, `MarketSession`,
  `AlertType`, ...), shared with the database models.
- **Frontend types come from the backend:** `make api-types` exports the
  OpenAPI document and generates `frontend/src/api/schema.gen.ts` (never edit
  it); `src/api/types.ts` gives its models short names. `make check` fails
  when the file is out of date. Response fields with defaults are still *required* in the
  generated types (the `Schema` base class), since the server always sends them.
- **TypeScript:** `strict` plus `noUncheckedIndexedAccess` (`arr[i]` may be
  `undefined`), `exactOptionalPropertyTypes`, `noImplicitOverride` and
  `noPropertyAccessFromIndexSignature`.
- **Lint:** oxlint with type-aware rules (`--type-aware`, via tsgolint, which
  works with the TypeScript 7 compiler; typescript-eslint doesn't yet): no
  `any`, no non-null `!`, no unchecked `as` casts, no unhandled promises,
  exhaustive switches, React hooks rules. Rules turned off are listed with the
  reason in `frontend/.oxlintrc.json`. Data from outside (API errors,
  `localStorage`) is checked at runtime, not cast (`errorDetail`/`errorStatus`
  in `api/client.ts`, `fromStorage` in `lib/settings.tsx`).

## Backend

```bash
cd backend
pip install -r requirements-dev.txt
ruff check .            # lint
pyright                 # type check
python -m pytest -q     # tests
```

No local Python? Run lint, type check and tests in the production package set:

```bash
docker build --target test -t bursa-backend-test ./backend && docker run --rm bursa-backend-test
```

Tests never call Yahoo: an autouse fixture blocks `yf.download`, `yf.Ticker` and `yf.Search`.
They also ignore `backend/.env` (`BURSA_ENV_FILE=""`, set in `tests/conftest.py`), so
real API keys or a configured mail provider never leak into a test run.

### Testing on PostgreSQL / MySQL

Tests use a throwaway SQLite file by default. Point `TEST_DATABASE_URL` at an
**empty, disposable** database to run the same suite there; its tables are dropped
after every test. The test image already includes both drivers:

```bash
docker network create bursa-dbtest
docker run -d --name bursa-pg --network bursa-dbtest \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=bursa_test postgres:17-alpine
docker run --rm --network bursa-dbtest \
  -e TEST_DATABASE_URL=postgresql+asyncpg://postgres:test@bursa-pg/bursa_test \
  bursa-backend-test python -m pytest -q
```

For MySQL use `mysql:8.4` and `mysql+aiomysql://root:test@bursa-my/bursa_test`.

### Schema changes (migrations)

After changing `models.py`, generate a migration, review it, and commit it:

```bash
cd backend
alembic revision --autogenerate -m "add foo column"
alembic upgrade head      # or just restart the app; it migrates on startup
alembic check             # verifies models.py and the database agree
```

Migrations live in `backend/migrations/versions/`, named by creation time (Jakarta):
`20261022_2057_rating_snapshots.py`. New ones get that name and a matching revision id
(`20261022_205703`) automatically. Alembic runs them in the order of each file's
`down_revision`, not by name. `20261017_2114_baseline.py` is the schema at
the time Alembic was introduced.

### Signal backtest

```bash
python scripts/evaluate_signals.py                 # investor style
python scripts/evaluate_signals.py --style trader  # trader style
```

A point-in-time backtest of the recommendation engine. Run it before and after
changing weights or thresholds in `config.py`; inside Docker:
`docker compose exec backend python scripts/evaluate_signals.py`.

It replays past dates using only the data available then and reports how each
rating did afterwards, plus the rank IC (correlation of score and later return;
~0 is noise, above 0.05 useful, above 0.10 good). Results are also split **by
year** and **by sector**: a change is worth keeping only if it helps across
years, not just in the months it was tuned on. The history comes from
`DAILY_HISTORY_YEARS` (5) of daily prices, fetched once per stock by the
`backfill_history` job, and the ~5 fiscal years of fundamentals.

`--write-summary` also saves the main-horizon result (how often each rating beat
the median stock) to `services/backtest_summary.json`. The app shows it as the
**track record** next to each rating, so re-run it for both styles after changing
the model and commit the file:

```bash
docker compose exec backend python scripts/evaluate_signals.py --write-summary
docker compose exec backend python scripts/evaluate_signals.py --style trader --write-summary
docker compose cp backend:/app/services/backtest_summary.json backend/services/
```

Findings so far (5 years, 2026-10): for **investor**, only Valuation had an edge in
every year; reweighting toward it gained only noise and made the top rating do worse
than the second (the very cheapest stocks are often value traps), so the weights were
kept. For **trader**, the Pullback factor added nothing and was dropped (4-week IC
0.099 → 0.112, better in every year).

The **live** track record needs no script: the `record_ratings` job saves both
styles' ratings at each trading day's close (`rating_snapshots`), and the app compares
them with what prices did once the horizon (3 months / 4 weeks) has passed.

## Frontend

```bash
cd frontend
npm run dev             # Vite HMR
npm run check           # tsc + oxlint (type-aware) + prettier --check
npm run build           # production build
npm run format          # prettier --write .
```

`openapi-typescript` needs the TypeScript 5 API, so `make api-types` runs it via
`npx` with its own pinned TypeScript instead of adding it to `package.json`.
