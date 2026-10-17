# Configuration

Backend settings live in `backend/config.py` (Pydantic settings). Any of them can be
overridden with an environment variable or in `backend/.env`. That file is git-ignored
and Docker-ignored, and is passed to the container via `env_file`.

| What | Where |
|---|---|
| Ports, DB path, API URL | `docker-compose.yml` (`DATABASE_URL`, `VITE_API_URL`) |
| Tracked stocks & indices | `backend/market/tickers.py` |
| Retention days, staleness, CORS, time zone, **trading-session times** | `backend/config.py` |
| **Recommendation weights & rating thresholds** (investor and trader) | `backend/config.py` (`recommendation_*`) |
| IDX holidays | `backend/market/holidays.py` (update annually from the IDX calendar) |
| IDX lot size | `lot_size` (default 100) in `backend/config.py`; exposed via `/api/status` |

## Database

SQLite is the default and needs no setup. To use a server database, set
`DATABASE_URL` and build the backend with that database's async driver:

| Database | `DATABASE_URL` | Build arg |
|---|---|---|
| SQLite (default) | `sqlite+aiosqlite:////app/data/bursa.db` | none |
| PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/bursa` | `DB_DRIVER=asyncpg` |
| MySQL / MariaDB | `mysql+aiomysql://user:pass@host:3306/bursa` | `DB_DRIVER="aiomysql cryptography"` |

For example, in `docker-compose.yml`:

```yaml
  backend:
    build:
      context: ./backend
      args:
        DB_DRIVER: asyncpg
    environment:
      - DATABASE_URL=postgresql+asyncpg://bursa:secret@postgres:5432/bursa
```

The schema is created and upgraded automatically on startup (Alembic). Data is not
copied between databases: a new database starts empty and fills from the providers.
Your portfolio, watchlist and alerts would need to be moved separately.

## Data providers

`price_provider` / `fundamentals_provider` in `backend/config.py` select the source
(Yahoo today). Adapters live in `backend/market/providers/`. To switch sources, add
an adapter and register it in `market/providers/registry.py`.

## Rate-limiting

`provider_max_concurrency`, `provider_min_interval_ms`, `provider_chunk_size`,
`intraday_max_symbols` and `search_cache_seconds` in `backend/config.py`. See
[Architecture](architecture.md#architecture--rate-limiting) for how they interact.

## AI assistant (optional)

Put your key in `backend/.env`:

```env
GEMINI_API_KEY=...
```

A free key is available from Google AI Studio. Models, the daily question cap,
the tool-round cap and personal-data access are the `assistant_*` settings in
`backend/config.py`. Portfolio/watchlist access stays off unless you set
`assistant_personal_data=true`.

Providers are abstracted in `backend/assistant/providers/`. Adding another LLM means
writing one adapter and registering it; the UI and API stay the same.

## Telegram alerts (optional)

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `backend/.env`. Step-by-step setup
is shown on the Alerts page, which can also send a test message.
