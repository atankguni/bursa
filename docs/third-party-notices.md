# Third-party notices

Bursa is released under the [MIT License](../LICENSE). It is built on the
open-source projects below, each under its own license (all permissive and
compatible with MIT). Full license texts ship with each package
(`frontend/node_modules/<package>/LICENSE`, or the package's metadata in the
backend image).

## Required attribution

**TradingView Lightweight Charts™** (Apache-2.0) requires this attribution
notice and a link to <https://www.tradingview.com/> visible to users. Bursa
shows the link in the app footer ("Charts by TradingView").

```
TradingView Lightweight Charts™
Copyright (с) 2024 TradingView, Inc. https://www.tradingview.com/
```

It also incorporates parts of tslib (© Microsoft Corporation, BSD Zero Clause
License).

## Frontend

| Package | Version | License |
|---|---|---|
| lightweight-charts (TradingView) | 4.2.3 | Apache-2.0 |
| react, react-dom | 19.3.1 | MIT |
| react-router-dom | 7.18.4 | MIT |
| @tanstack/react-query | 5.104.3 | MIT |
| axios | 1.20.0 | MIT |
| lucide-react | 1.57.0 | ISC |

## Backend

| Package | Version | License |
|---|---|---|
| fastapi | 0.143.2 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| sqlalchemy | 2.1.4 | MIT |
| aiosqlite | 0.22.1 | MIT |
| alembic (+ Mako, MarkupSafe) | 1.20.0 | MIT (MarkupSafe: BSD-3-Clause) |
| yfinance | 1.7.0 | Apache-2.0 |
| curl_cffi | 0.16.3 | MIT |
| apscheduler | 3.11.3 | MIT |
| pydantic | 2.14.1 | MIT |
| pydantic-settings | 2.16.0 | MIT |
| pandas | 3.0.6 | BSD-3-Clause |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| argon2-cffi | 25.1.0 | MIT |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| segno | 1.6.6 | BSD-3-Clause |

Optional database drivers, installed only when building for that database
(`DB_DRIVER` build arg):

| Package | Version | License |
|---|---|---|
| asyncpg (PostgreSQL) | 0.32.0 | Apache-2.0 |
| aiomysql + PyMySQL (MySQL/MariaDB) | 0.3.2 / 1.2.3 | MIT |

(Versions as pinned at the time of writing; transitive dependencies carry their
own licenses.)

## Data sources and services (not covered by this license)

The MIT License covers Bursa's **source code only**, not the data the app
fetches at runtime:

- **Yahoo Finance** (prices, fundamentals, splits, dividends, index values) via
  the unofficial `yfinance` library. Use of this data is subject to Yahoo's
  terms and is intended for personal, non-commercial use.
- **Indonesia Stock Exchange (idx.co.id)** website data (listing boards,
  listing dates, share counts), fetched from undocumented public endpoints.
- **Google Gemini API** (optional AI assistant), subject to Google's terms;
  each user supplies their own API key.
- **Telegram Bot API** (optional alert delivery), subject to Telegram's terms.

Bursa is not affiliated with or endorsed by Yahoo, the Indonesia Stock
Exchange, TradingView, Google or Telegram. All trademarks belong to their
respective owners.

## Not financial advice

Prices may be delayed, incomplete or wrong; signals, ratings, risk figures and
dividend dates are heuristic estimates for personal reference. Do your own
research before making investment decisions.
