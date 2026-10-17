# API reference

The backend serves interactive OpenAPI docs at http://localhost:8000/docs.
`{ticker}` uses the Yahoo suffix, e.g. `BBCA.JK`.

## Meta

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/health` | Health check |
| GET    | `/api/status` | Global status (last sync, provider, session, counts) |
| GET    | `/api/market-status` | IDX trading status (open / break / closed) |
| GET    | `/api/providers` | Active data providers + registry |
| GET    | `/api/indexes` | Available index names |
| GET    | `/api/data-health` | Jobs, freshness, coverage, suspicious values |
| GET/PUT | `/api/preferences` | Server-side preferences (investing style) |

## Stocks

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/stocks?index=LQ45&index=IDX30` | Stocks (AND across indices) + latest price/change |
| POST   | `/api/stocks` | Track a new ticker |
| GET    | `/api/stocks/{ticker}` | Single tracked stock summary |
| GET    | `/api/stocks/{ticker}/history?interval=1d\|1m` | OHLCV bars for charts |
| GET    | `/api/stocks/{ticker}/fundamentals` | Yearly fundamentals + PBV/RoE |
| GET    | `/api/stocks/{ticker}/recommendation` | Buy-signal score + rating + conviction + factors |
| GET    | `/api/stocks/{ticker}/valuation` | PBV/RoE vs own history (percentile) |
| GET    | `/api/stocks/{ticker}/dividends` | Dividend history + trailing yield |
| GET    | `/api/stocks/{ticker}/company` | Company profile + board/management |
| POST/DELETE | `/api/stocks/{ticker}/track` | Add/remove a symbol from the intraday set |
| GET    | `/api/search?q=&all=` | Symbol search (IDX-only by default; `all=1` for every exchange) |
| GET    | `/api/catalog?q=&limit=&offset=` | Browse the full IDX catalog |

## Market and indices

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/market/overview` | Breadth, top movers, sector performance |
| GET    | `/api/indices` | Latest value + change of 33 IDX stock indices |
| GET    | `/api/indices/{code}/history?range=1y\|5y\|max` | Daily bars for one index |

## Screener

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/screener?min_score=&max_pbv=&min_roe=&rating=&sector=&buy_only=` | Rank/filter the universe |
| POST   | `/api/screener/sync` | Background sync of missing fundamentals (capped) |
| POST   | `/api/screener/sync?all=true` | Paced "sync all missing" |
| POST   | `/api/screener/sync/cancel` | Stop the running sync |
| GET    | `/api/screener/sync/status` | Progress of the sync job |

## Watchlist

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/watchlist` | Watchlist with price + fundamentals + ratios |
| POST   | `/api/watchlist/{ticker}` | Add a ticker (fetches fundamentals) |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |
| POST   | `/api/watchlist/refresh` | Re-sync all watchlist fundamentals |

## Portfolio

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/portfolio` | Holdings + totals (average-cost P/L) |
| GET/POST/DELETE | `/api/portfolio/transactions` | Manage transactions |
| GET    | `/api/portfolio/history` | Portfolio value over time |
| GET    | `/api/portfolio/risk` | Concentration, sectors, beta vs IHSG, stress test, drawdown |
| GET    | `/api/portfolio/dividend-calendar` | Expected (projected) dividends for holdings + watchlist |

## Alerts

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/alerts` | List / create alert rules |
| POST   | `/api/alerts/{id}/toggle` | Pause / resume an alert |
| DELETE | `/api/alerts/{id}` | Delete an alert |
| GET    | `/api/alerts/events` | Recent triggered alerts |
| GET    | `/api/alerts/notifications` | Telegram status |
| POST   | `/api/alerts/notifications/test` | Send a Telegram test message |

## Assistant

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/assistant/status` | Whether the assistant is configured + usage |
| POST   | `/api/assistant/chat` | Ask a question (answers via read-only tools) |
