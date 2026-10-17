# Features

## Market data

- **Multi-index tracking**: LQ45, IDX30, JII, ISSI, IDXHIDIV20, IDXBUMN20.
  Selecting several indices filters to stocks present in **all** of them (AND).
- **Live prices**: batched Yahoo Finance fetch with rate-limit protection, refreshed every 3 minutes.
- **Market overview**: **33 IDX stock indices** (indeks saham), including IHSG, LQ45, IDX30, IDX80,
  Kompas100, JII/JII70/ISSI, all 11 sector indices, ESG/thematic indices and boards. They appear as headline cards
  plus grouped, change-tinted tiles. IHSG/LQ45/JII charts go back decades; the others build
  up daily. Also shows breadth, top gainers/losers and a sector-performance view. IHSG is always
  visible in the top bar.
- **Market clock**: a navbar indicator (dot + label) shows whether IDX is
  **Open / Pre-open / Break / Closed** (sessions + holidays), and the background
  sync uses the same clock.
- **Special monitoring**: stocks on IDX's Papan Pemantauan Khusus get a warning badge
  everywhere and their signals are capped at Hold. Boards, IPOs and official share
  counts come from the IDX listing, refreshed weekly.

## Stocks and charts

- **Search**: find any symbol from the navbar (IDX by default). Click a result to
  inspect it in the detail modal. New tickers are auto-added to the tracked universe
  (not your watchlist).
- **Browse IDX**: the full IDX catalog (~960 listed stocks) with search, pagination and a
  Track toggle. Tracked stocks get intraday updates; clicking a row opens the detail modal.
- **Charts**: candlestick or line, daily (1d) and intraday (1m), 1M–Max spans, an
  optional **vs IHSG** overlay (% change) and stock-split markers, via Lightweight Charts.
- **Chart indicators**: MA(20/50/200), volume and RSI overlays on the detail chart.
- **Relative valuation**: where current PBV/RoE sit within the stock's own history.
- **Dividends**: dividend history, trailing yield, and projected annual income for holdings.
- **Company**: a detail tab with the company description, sector/industry, employees,
  HQ/website, and the **board & management** (directors) list.

## Signals and screening

- **Recommendation**: an explainable, cross-sectional **factor score** (Quality, Valuation,
  Growth, Momentum, Health) → rating (Strong Buy → Avoid) + conviction, with a factor
  breakdown and plain-language reasons. It appears on **Home** (sortable column, "Buy only"
  filter, buy-signal counts) and the **Watchlist**, plus a detail tab.
  - Only stocks with fundamentals are rated.
  - Thinly traded names (< Rp 1bn/day median traded value) are capped at Hold.
  - Financials skip leverage-based Health.
- **Investing style**: choose **Investor** (default, fundamentals-led factor score) or
  **Trader** (swing, 1–4 weeks: price stability, setup near the 20-day high and pullbacks).
  Trader mode can rate liquid stocks without fundamentals. The choice is stored on the server.
- **Screener**: rank/filter the tracked universe by score, PBV, RoE, sector, or
  "Buy signals only", with pagination. **Sync missing** backfills fundamentals
  (PBV/RoE/sector) in a capped, throttled background job. **Sync all** runs a paced job
  over the whole catalog and can be cancelled.

Signals are heuristics, **not financial advice**. Measure changes with the point-in-time
backtest (see [Development](development.md#signal-backtest)).

## Personal tracking

- **Watchlist**: add/remove stocks; yearly figures (shares, revenue, net income, assets,
  liabilities, equity) with derived **PBV** and **RoE**. Sorted by ticker by default;
  every column is sortable.
- **Portfolio**: record buy/sell transactions (**in lots**: 1 lot = 100 shares, with a
  shares toggle). Shows holdings with average-cost **P/L**, allocation weights, day change,
  realized P/L and a portfolio value curve. A **hide values** toggle masks amounts
  when others can see your screen.
- **Portfolio analytics**:
  - **Return vs IHSG**, time-weighted so buys and sells don't count as gains.
  - A **risk view**: diversification, sector exposure, beta vs IHSG, an "if IHSG
    falls 10%" stress test and max drawdown.
  - An **expected dividend calendar**, projected from last year's ex-dates.
  - Holdings are **split-adjusted** automatically.
- **Alerts**: price-above/below, %-change and rating-change rules with in-app
  notifications (navbar bell) and optional **Telegram** delivery. Rules are evaluated after
  each market sync.

## Assistant and tools

- **AI assistant**: ask questions in plain language (English or Indonesian) from the
  ✨ navbar button. It answers with the app's own data via read-only tools (stocks,
  signals, screener, fundamentals, price history, market overview); it can't trade or
  change anything. It uses Google Gemini's free tier behind a provider-neutral interface.
  Portfolio/watchlist access is **off** by default (`assistant_personal_data`).
- **Data health** (`/data`, footer link): scheduled jobs, provider calls, price
  freshness, fundamentals coverage and suspicious values. Missed jobs (e.g. while the
  host slept) run on wake, and 1-minute gaps are back-filled.

## Personalization

- **Theme**: light / dark / **follow system**.
- **Settings** (gear in the navbar): theme, display **density** (compact/medium/large),
  reduce motion, high contrast, default indices, chart defaults, auto-refresh, number format,
  change coloring and per-table **column visibility**. These are saved in the browser.

## Accessibility

- A **High contrast** toggle (Settings → Appearance) switches the palette to a
  **WCAG AA** set (body text ≥ 4.5:1, interactive borders ≥ 3:1). Charts follow it too.
- Colour is never the only signal: price changes carry **↑/↓ arrows** and `+/−`
  signs in addition to green/red.
- **Reduce motion** honors the OS `prefers-reduced-motion` by default (also toggleable).
- Visible **focus rings**, `scope="col"` table headers, ARIA labels on icon-only
  controls and an `aria-label` summary on the charts.
