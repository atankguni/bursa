"""Central application settings (environment-driven)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Env vars override the defaults (e.g. DATABASE_URL)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/bursa.db"

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

    # Recommendation engine -------------------------------------------------
    # Category weights (must sum to ~1.0). Tune here; no code changes needed.
    recommendation_weights: dict[str, float] = {
        "quality": 0.30,
        "valuation": 0.30,
        "growth": 0.20,
        "momentum": 0.10,
        "health": 0.10,
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
    # Reuse a computed universe score for this long (seconds) to avoid
    # recomputing on every 60s poll.
    recommendation_cache_seconds: int = 60


settings = Settings()
