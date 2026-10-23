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
| @zxcvbn-ts/core, language-common, language-en | 4.2.0 / 4.1.3 / 4.1.1 | MIT |

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
| zxcvbn | 4.5.0 | MIT |

Optional database drivers, installed only when building for that database
(`DB_DRIVER` build arg):

| Package | Version | License |
|---|---|---|
| asyncpg (PostgreSQL) | 0.32.0 | Apache-2.0 |

(Versions as pinned at the time of writing.) Transitive dependencies carry their
own licenses. All of them, frontend and backend, are permissive (MIT, BSD, ISC,
Apache-2.0, PSF, Zlib, CC0); none is GPL or AGPL. The one weak-copyleft package
is **certifi** (Mozilla's CA certificate bundle, MPL-2.0), used unmodified; its
source is at <https://github.com/certifi/python-certifi>.

If you publish ready-built Docker images, they also contain the base image's
operating-system packages (Alpine Linux: musl, BusyBox and others, some under
GPL-2.0); their licenses and sources come from Alpine.

## Data sources and services (not covered by this license)

The MIT License covers Bursa's **source code only**, not the data the app
fetches at runtime:

- **Yahoo Finance** (prices, fundamentals, splits, dividends, index values) via
  the unofficial `yfinance` library. Use of this data is subject to Yahoo's
  terms and is intended for personal, non-commercial use.
- **Indonesia Stock Exchange (idx.co.id)** website data (listing boards,
  listing dates, share counts), fetched weekly from undocumented public
  endpoints. `backend/market/idx_listed.py` (stock codes and company names)
  is generated from the same source.
- **Google Gemini API** (optional AI assistant), subject to Google's terms. The
  server operator supplies one API key for everyone (`GEMINI_API_KEY`); on
  Google's free tier, prompts may be used to improve Google's products.
- **Have I Been Pwned, Pwned Passwords** (optional leaked-password check): only
  the first 5 characters of the password's SHA-1 hash are sent. No license or
  attribution is required.
- **Telegram Bot API** (optional alert delivery) and the email provider you
  configure (SMTP or Resend), each subject to its own terms.

**Running Bursa for other people.** Bursa is meant to be self-hosted for
yourself (and maybe your family). Offering it as a public or paid service would
redistribute Yahoo's and IDX's data, which their terms don't allow without a
license, and showing stock ratings to the public may need a license from your
financial regulator (in Indonesia, OJK). The operator of such a service is
responsible for that; use a licensed data source if you do.

Bursa is not affiliated with or endorsed by Yahoo, PT Bursa Efek Indonesia
(the Indonesia Stock Exchange), TradingView, Google, Telegram or Have I Been
Pwned. IDX, IHSG, LQ45, IDX30, JII and ISSI are names and trademarks of PT Bursa
Efek Indonesia, used here only to identify the indices. All trademarks belong to
their respective owners.

## Not financial advice

Prices may be delayed, incomplete or wrong; signals, ratings, risk figures and
dividend dates are heuristic estimates for personal reference. Do your own
research before making investment decisions.
