"""Central application settings (environment-driven)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Env vars override the defaults (e.g. DATABASE_URL)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/bursa.db"
    # AI assistant. Ordered "provider:model" attempts (see assistant/providers):
    # the first configured one answers; on busy/quota/errors the next is tried.
    # Providers without credentials are skipped, so a fallback can be listed
    # before its key exists. Env override: ASSISTANT_CHAIN='["gemini:..."]'.
    assistant_chain: list[str] = ["gemini:gemini-3.5-flash", "gemini:gemini-3.1-flash-lite"]
    # Provider credentials: from the environment / backend/.env, never commit them.
    gemini_api_key: str | None = None
    assistant_daily_limit: int = 100
    assistant_max_tool_rounds: int = 6
    # Off by default: when on, watchlist and portfolio are sent to the AI provider
    # (Gemini's free tier may use prompts for training).
    assistant_personal_data: bool = False
    # yfinance's timezone cache. Kept on the data volume so it survives rebuilds.
    yfinance_cache_dir: str = "./data/yfinance-cache"

    # CORS: wildcard "*" + allow_credentials is invalid, so list explicit origins.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Market / sync behaviour
    timezone: str = "Asia/Jakarta"
    intraday_retention_days: int = 5
    fundamentals_stale_hours: int = 24
    fx_cache_hours: int = 6

    # Data sources. Yahoo is the only implemented provider today; extend the
    # registry in market/providers/ and switch these per capability.
    price_provider: str = "yahoo"
    fundamentals_provider: str = "yahoo"
    base_currency: str = "IDR"

    # Alerts: minimum time before the same alert may fire again.
    alert_cooldown_hours: int = 12

    # Outbound provider governance (anti-burst / anti-blacklist).
    provider_max_concurrency: int = 2
    provider_min_interval_ms: int = 200
    search_cache_seconds: int = 300
    # Catalog sync: symbols per download batch, and the intraday universe cap.
    provider_chunk_size: int = 50
    intraday_max_symbols: int = 100

    # IDX trades in lots; 1 lot = 100 shares.
    lot_size: int = 100

    # Screener "sync missing data" job (manual; fundamentals-only, bounded).
    screener_sync_limit: int = 40
    screener_sync_throttle: float = 0.4

    # IDX trading sessions (local exchange time, "HH:MM"). Session 2 end is the
    # point after which intraday data stops; the lunch break is skipped.
    pre_open_start: str = "08:45"
    session1_start: str = "09:00"
    session1_end: str = "12:00"
    session2_start: str = "13:30"
    session2_end: str = "15:50"

    # Recommendation engine -------------------------------------------------
    # Category weights (must sum to ~1.0). Tune here; no code changes needed.
    # Chosen with scripts/evaluate_signals.py on a time split (picked on Jan-May
    # 2026, validated on Jun-Sep): valuation was the strongest factor and growth
    # was consistently negative, so weight moved from growth to valuation/health.
    # Re-check as more history accumulates; the sample is still short.
    recommendation_weights: dict[str, float] = {
        "quality": 0.30,
        "valuation": 0.40,
        "growth": 0.05,
        "momentum": 0.10,
        "health": 0.15,
    }
    # Composite score (0-100) -> rating label. Highest threshold that is met wins.
    recommendation_ratings: list[tuple[str, int]] = [
        ("Strong Buy", 80),
        ("Buy", 65),
        ("Hold", 45),
        ("Reduce", 30),
        ("Avoid", 0),
    ]
    # Conviction blend: magnitude (distance from neutral), agreement, coverage.
    conviction_very_strong: float = 0.75
    conviction_strong: float = 0.55
    conviction_moderate: float = 0.35
    # Guards backed by scripts/evaluate_signals.py (a point-in-time backtest):
    # * A stock is only rated when it has Quality or Valuation data, i.e.
    #   fundamentals; price-only (momentum-only) scores had no predictive power.
    # * Buy / Strong Buy need this median daily traded value (IDR, last 20 days);
    #   thinly traded names are capped at Hold.
    recommendation_min_traded_value: float = 1_000_000_000
    # Trader (swing, 1-4 weeks) style: price behaviour only, for liquid stocks.
    # From the factor research: low volatility, a tight range near the 20-day
    # high, and recent pullbacks predicted 1-4 week returns; classic momentum
    # did not (it was slightly negative). Measured in a falling market only.
    recommendation_trader_weights: dict[str, float] = {
        "stability": 0.50,
        "setup": 0.30,
        "pullback": 0.20,
    }
    # Leverage ratios are structural for balance-sheet businesses (bank deposits
    # are liabilities), so Health (Debt/Equity, equity ratio) is not scored here.
    recommendation_no_leverage_sectors: list[str] = ["Financial Services"]
    # Reuse a computed universe score for this long (seconds) to avoid
    # recomputing on every 60s poll.
    recommendation_cache_seconds: int = 60


settings = Settings()
