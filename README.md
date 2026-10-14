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
- **Charts** — candlestick or line, daily (1d) and intraday (1m), via Lightweight Charts.
- **Theme** — light / dark / **follow system** (toggle in the top bar).

## Tech Stack

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.11, FastAPI, SQLAlchemy 2.0 (async) + aiosqlite, APScheduler, yfinance |
| Database | SQLite (WAL mode), persisted on the host |
| Frontend | React + Vite, TypeScript, Tailwind CSS, TanStack Query, lightweight-charts, lucide-react |
| Infra    | Docker Compose |

---

## Quick Start

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| Backend  | http://localhost:8000 (docs at `/docs`) |

The SQLite database lives at `./backend/data/bursa.db` and survives container restarts.
The first boot fetches ~1 year of daily candles, so initial charts fill in within a few seconds.

To reset all data, delete the database files and restart:

```bash
rm -f backend/data/bursa.db*
docker compose up --build
```

---

## Project Structure

```
bursa/
├── docker-compose.yml
├── backend/
│   ├── main.py            # FastAPI app + endpoints
│   ├── database.py        # async engine, WAL, light migrations
│   ├── models.py          # Stock, StockIndex, StockPrice, Watchlist, Fundamental
│   ├── schemas.py         # Pydantic response models
│   ├── scheduler.py       # APScheduler jobs (prices + fundamentals)
│   ├── fundamentals.py    # yfinance statements -> IDR-normalized rows
│   ├── tickers.py         # index universe + constituents
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── index.html
    ├── src/
    │   ├── App.tsx            # shell + routes
    │   ├── pages/             # Home, Watchlist
    │   ├── components/        # NavBar, chart, modal, index selector
    │   ├── api.ts             # typed API client
    │   └── lib/               # formatting + theme
    ├── public/                # favicons, manifest
    ├── package.json
    └── Dockerfile
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/health` | Health check |
| GET    | `/api/indexes` | Available index names |
| GET    | `/api/stocks?index=LQ45&index=IDX30` | Stocks (AND across indices) + latest price/change |
| GET    | `/api/stocks/{ticker}/history?interval=1d\|1m` | OHLCV bars for charts |
| GET    | `/api/stocks/{ticker}/fundamentals` | Yearly fundamentals + PBV/RoE |
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
- **Tracked stocks & indices** — edit `backend/tickers.py`.

## Limitations

- **ISSI** is a seeded subset of well-known sharia names, not the full ~500 constituents.
- Fundamentals are fetched **per ticker** (yfinance has no batch statement API), so syncing is throttled.
- yfinance may occasionally rate-limit or omit a ticker; failed jobs are retried and never crash the app.
