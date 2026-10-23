# Development

For running the dev servers with hot reload, see [Getting started](getting-started.md#development-hot-reload).

## Checks

Everything is statically typed, and one command checks it all (the backend
runs in its Docker test image, so no local Python is needed):

```bash
make check        # everything: types, lint, format, tests on SQLite and PostgreSQL,
                  # schema drift, API types in sync
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
- **One definition per shape:** API shapes are the Pydantic models in each
  feature's `schemas.py`, and its logic returns them directly (no TypedDict copies).
  Value sets are `Literal` aliases there too (`TradeSide`, `MarketSession`,
  `AlertType`, ...), shared with the database models.
- **Frontend types come from the backend:** `make api-types` exports the
  OpenAPI document and generates `frontend/src/api/schema.gen.ts` (never edit
  it); `src/api/types.ts` gives its models short names. `make check` fails
  when the file is out of date. Response fields with defaults are still *required* in the
  generated types (the `Schema` base class), since the server always sends them.
- **Time:** points in time are timezone-aware UTC everywhere in Python
  (`clock.utcnow()`); datetime columns use `db.types.UTCDateTime`, which refuses
  naive values. Dates at the exchange come from `clock.local_today()`, never
  `date.today()` (the server runs in UTC). Daily price bars are keyed by their
  trading `day` (a date); where the API needs a time for one it sends
  `clock.day_key(day)`. The API sends times with `Z`.
- **Stock codes:** stored and sent as IDX codes (`BBCA`). Request bodies and
  paths use `schemas.StockCode`, which upper-cases and also accepts `BBCA.JK`
  (old links). Only the Yahoo provider knows the `.JK` suffix.
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

### Testing on PostgreSQL

`make check` runs the suite on SQLite and then on a throwaway PostgreSQL container
(`make backend-pg`; removed afterwards). Tests use a throwaway SQLite file by
default. To run them against another **empty, disposable** database, point
`TEST_DATABASE_URL` at it; its tables are dropped after every test. The test image
includes the driver:

```bash
docker network create bursa-dbtest
docker run -d --name bursa-pg --network bursa-dbtest \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=bursa_test postgres:17-alpine
docker run --rm --network bursa-dbtest \
  -e TEST_DATABASE_URL=postgresql+asyncpg://postgres:test@bursa-pg/bursa_test \
  bursa-backend-test python -m pytest -q
```


### Schema changes (migrations)

After changing a feature's `models.py`, generate a migration, review it, and commit it:

```bash
cd backend
alembic revision --autogenerate -m "add foo column"
alembic upgrade head      # or restart the API: prepare.py migrates before it starts
alembic check             # verifies the models and the database agree
```

`make check` also catches a forgotten migration: `scripts/check_schema.py` migrates an
empty database (SQLite and PostgreSQL) and fails if it differs from the models.

Migrations live in `backend/migrations/versions/`, named by creation time (Jakarta):
`20261023_0735_baseline_schema.py`. New ones get that name and a matching revision id
(`20261023_073546`) automatically. Alembic runs them in the order of each file's
`down_revision`, not by name. The earlier migrations were squashed into that
baseline on 2026-10-23.

### Converting an old database

A SQLite database from before the squash is refused on startup with a pointer here.
Stop both the API and the worker first: nothing may have the file open while it is
copied. (The same goes for reading the live file with `sqlite3` on the host: the Mac
and Docker's VM don't share SQLite's WAL index, so query it inside a container instead,
e.g. `docker compose exec worker python -c "import sqlite3; ..."`.)
Convert it into a new file (the old one is only read), then swap the files:

```bash
docker compose stop backend worker
docker compose run --rm --no-deps backend \
  python scripts/convert_db.py data/bursa.db data/bursa.converted.db
mv backend/data/bursa.db backend/data/bursa.pre-squash.db   # keep as a backup
rm -f backend/data/bursa.db-wal backend/data/bursa.db-shm
mv backend/data/bursa.converted.db backend/data/bursa.db
docker compose start backend worker
```

It strips `.JK` from stock codes, splits the price table into daily and intraday
bars, moves sync timestamps to `sync_state` and preferences to `user_settings`, then
compares row counts and runs SQLite's foreign-key and integrity checks; it stops
with an error if anything doesn't match. The live database (1.17 M price rows) took
about 30 s and shrank from 269 MB to 75 MB.

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
the median stock) to `signals/backtest_summary.json`. The app shows it as the
**track record** next to each rating, so re-run it for both styles after changing
the model and commit the file:

```bash
docker compose exec backend python scripts/evaluate_signals.py --write-summary
docker compose exec backend python scripts/evaluate_signals.py --style trader --write-summary
docker compose cp backend:/app/signals/backtest_summary.json backend/signals/
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
npm run check           # tsc + oxlint (type-aware) + prettier --check + tests
npm test                # Vitest once (npm run test:watch: rerun on save)
npm run build           # production build
npm run format          # prettier --write .
```

`openapi-typescript` needs the TypeScript 5 API, so `make api-types` runs it via
`npx` with its own pinned TypeScript instead of adding it to `package.json`.

Styling is Tailwind CSS 4 through its Vite plugin, with no `tailwind.config.js`:
the theme lives in `src/index.css`. Semantic colours (`bg-panel`, `text-muted`,
`ring-line`, `text-accent`...) are `--color-*` entries in `@theme` that point at
the `--c-*` variables, which change with the theme, high contrast and the
accent. Add a colour there, not as a hex value in a component. Radius scale:
`rounded-xs` tags and bars, `rounded-sm` controls, `rounded-md` surfaces.
