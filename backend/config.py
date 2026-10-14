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


settings = Settings()
