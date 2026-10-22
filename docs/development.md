# Development

For running the dev servers with hot reload, see [Getting started](getting-started.md#development-hot-reload).

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

Migrations live in `backend/migrations/versions/`. `0001_baseline` is the schema at
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
npm run typecheck       # tsc --noEmit
npm run build           # production build
npm run format          # prettier --write .
```

> ESLint is intentionally not used: the TypeScript 7 native compiler is not
> yet supported by `typescript-eslint`, so type checking is done by `tsc`.
