# Bursa

A personal stock monitor for the **Indonesia Stock Exchange (IDX / Bursa Efek Indonesia)**.

Track index constituents, watch your hand-picked stocks, and review yearly fundamentals
to compute valuation ratios like **PBV** and **RoE** — all self-hosted via Docker Compose.

---

## Features

- **Multi-index tracking** — LQ45, IDX30, JII, ISSI, IDXHIDIV20, IDXBUMN20.
  Selecting several indices filters to stocks present in **all** of them (AND).
- **Live prices** — batched Yahoo Finance fetch, anti rate-limit, refreshed every 3 minutes.
- **Watchlist** — add/remove stocks; yearly figures (shares, revenue, net income, assets,
  liabilities, equity) with derived **PBV** and **RoE**.
- **Recommendation** — an explainable, cross-sectional **factor score** (Quality, Valuation,
  Growth, Momentum, Health) → rating (Strong Buy → Avoid) + conviction, with a factor
  breakdown and plain-language reasons. Shown on **Home** (sortable column, "Buy only"
  filter, buy-signal counts) and the **Watchlist**, plus a detail tab. Heuristic, not
  financial advice.
- **Charts** — candlestick or line, daily (1d) and intraday (1m), via Lightweight Charts.
- **Theme** — light / dark / **follow system** (set from Settings).
- **Settings** (gear in the navbar) — theme, display **density** (compact/medium/large),
  reduce motion, default indices, chart defaults, auto-refresh, number format,
  change coloring, and per-table **column visibility**; persisted in the browser.
- **Market clock** — a navbar indicator (dot + label) shows whether IDX is
  **Open / Pre-open / Break / Closed** (sessions + holidays), and the background
  sync uses the same clock.

## Tech Stack

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.14, FastAPI, SQLAlchemy 2.0 (async) + aiosqlite, APScheduler, yfinance |
| Database | SQLite (WAL mode), persisted on the host |
| Frontend | React 19 + Vite, TypeScript, Tailwind CSS, TanStack Query, lightweight-charts, lucide-react |
| Infra    | Docker Compose (single stack) + nginx |

---

## Run

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 (nginx, serves the built SPA) |
| Backend  | http://localhost:8000 (docs at `/docs`) |

The SQLite database lives at `./backend/data/bursa.db` and survives container restarts.
The first boot fetches ~1 year of daily candles, so initial charts fill in within a few seconds.

To reset all data, delete the database files and restart:

```bash
rm -f backend/data/bursa.db*
docker compose up --build
```

## Development (hot reload)

The image above is the optimized runtime. For live-reload while coding, run the
dev servers directly (no separate compose file needed):

```bash
# Backend (auto-reload)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (Vite HMR) — in another terminal
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Vite serves on http://localhost:5173 and, with `VITE_API_URL` set, talks to the
backend on `:8000` (CORS is already allowed for `localhost:5173`).

## Notes

- The frontend is a static build served by nginx (gzipped, immutable caching,
  `/api` reverse-proxied). The chart library and the Watchlist route are
  code-split and loaded on demand.
- Intraday (1m) data is synced **only during market hours** (Mon–Fri 09:00–16:00 WIB)
  and pruned after 5 days; the WAL is auto-checkpointed and VACUUMed weekly.

---

## Project Structure

```
bursa/
├── docker-compose.yml
├── backend/
│   ├── main.py            # app factory: settings, middleware, lifespan, routers
│   ├── config.py          # Settings (env-driven)
│   ├── deps.py            # FastAPI dependencies (get_session)
│   ├── database.py        # async engine, WAL, light migrations
│   ├── models.py          # Stock, StockIndex, StockPrice, Watchlist, Fundamental
│   ├── schemas.py         # Pydantic response models
│   ├── routers/           # meta, stocks, watchlist endpoints
│   ├── services/          # metrics (PBV/RoE), prices, fundamentals, bootstrap
│   ├── market/            # tickers + batched yfinance sync
│   ├── scheduler.py       # APScheduler jobs (prices + fundamentals + retention)
│   ├── tests/             # pytest smoke + unit tests
│   ├── pyproject.toml     # ruff + pytest config
│   ├── requirements.txt · requirements-dev.txt
│   └── Dockerfile
└── frontend/
    ├── index.html
    ├── src/
    │   ├── App.tsx            # shell + routes
    │   ├── pages/             # Home, Watchlist
    │   ├── components/        # NavBar, chart, modal, panels
    │   ├── api/               # client, types, stocks, watchlist (barrel)
    │   ├── hooks/             # React Query hooks + keys
    │   └── lib/               # formatting + theme
    ├── public/                # favicons, manifest
    ├── .prettierrc.json
    ├── package.json
    └── Dockerfile
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/health` | Health check |
| GET    | `/api/market-status` | IDX trading status (open / break / closed) |
| GET    | `/api/providers` | Active data providers + registry |
| GET    | `/api/indexes` | Available index names |
| GET    | `/api/stocks?index=LQ45&index=IDX30` | Stocks (AND across indices) + latest price/change |
| GET    | `/api/stocks/{ticker}/history?interval=1d\|1m` | OHLCV bars for charts |
| GET    | `/api/stocks/{ticker}/fundamentals` | Yearly fundamentals + PBV/RoE |
| GET    | `/api/stocks/{ticker}/recommendation` | Buy-signal score + rating + conviction + factors |
| GET    | `/api/watchlist` | Watchlist with price + fundamentals + ratios |
| POST   | `/api/watchlist/{ticker}` | Add a ticker (fetches fundamentals) |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |
| POST   | `/api/watchlist/refresh` | Re-sync all watchlist fundamentals |

`{ticker}` uses the Yahoo suffix, e.g. `BBCA.JK`.

---

## Data & Sync

- **Prices** — a single batched `yf.download()` call every **3 minutes** (avoids rate limits),
  upserted into SQLite; daily candles backfilled on startup.
- **Fundamentals** — refreshed daily (~18:00 WIB) and on demand via the watchlist **Refresh** button.
  Figures are **normalized to IDR**; foreign-currency filers (e.g. PGAS, which reports in USD)
  are converted so PBV is calculated on a consistent basis.
- **Ratios** — `PBV = market cap ÷ book value` (book value = total assets − total liabilities);
  `RoE = net income ÷ equity`.

## Configuration

- **Ports / DB path / API URL** — see `docker-compose.yml` (`DATABASE_URL`, `VITE_API_URL`).
- **Tracked stocks & indices** — edit `backend/market/tickers.py`.
- **Backend settings** (retention days, staleness, CORS, tz, **trading-session times**,
  **recommendation weights & rating thresholds**) — `backend/config.py`.
- **IDX holidays** — `backend/market/holidays.py` (update annually from the IDX calendar).
- **Data provider(s)** — `price_provider` / `fundamentals_provider` in `backend/config.py`
  (Yahoo today). Adapters live in `backend/market/providers/`; add one and register it
  in `market/providers/registry.py` to switch sources.

## Development commands

Backend (see "Development" above for the dev servers):

```bash
cd backend
pip install -r requirements-dev.txt
ruff check .            # lint
python -m pytest -q     # tests
```

Frontend:

```bash
cd frontend
npm run dev             # Vite HMR
npm run typecheck       # tsc --noEmit
npm run format          # prettier --write .
```

> Note: ESLint is intentionally not used — the TypeScript 7 native compiler is not
> yet supported by `typescript-eslint`, so type checking is done by `tsc`.

## Limitations

- **ISSI** is a seeded subset of well-known sharia names, not the full ~500 constituents.
- Fundamentals are fetched **per ticker** (yfinance has no batch statement API), so syncing is throttled.
- yfinance may occasionally rate-limit or omit a ticker; failed jobs are retried and never crash the app.
