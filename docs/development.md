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
changing weights or thresholds in `config.py`.

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
