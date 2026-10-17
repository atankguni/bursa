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
