"""
database.py
-----------
Async SQLAlchemy 2.0 engine + session factory for SQLite (aiosqlite driver).

Key points
~~~~~~~~~~
* WAL (Write-Ahead Logging) journal mode is enabled on every new connection so
  the background scheduler can write while the API reads concurrently.
* `busy_timeout` prevents "database is locked" errors under concurrent access.
* `init_db()` creates all tables and returns nothing; it is awaited on startup.
"""

import os

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

# Allow the DB path to be overridden by the environment (Docker sets this).
# Default resolves to ./data/bursa.db relative to the backend working dir.
DATABASE_URL = settings.database_url

# Ensure the local data directory exists (no-op for the Docker volume mount).
if DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    _path = DATABASE_URL.replace("sqlite+aiosqlite:///", "", 1)
    _dir = os.path.dirname(_path)
    if _dir:
        os.makedirs(_dir, exist_ok=True)

# `echo=False` keeps the logs clean; flip to True when debugging SQL.
engine = create_async_engine(DATABASE_URL, echo=False, future=True)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Configure every raw SQLite connection the moment it is opened."""
    cursor = dbapi_connection.cursor()
    # WAL allows concurrent readers + a single writer without blocking.
    cursor.execute("PRAGMA journal_mode=WAL;")
    # NORMAL is durable enough for WAL and much faster than FULL.
    cursor.execute("PRAGMA synchronous=NORMAL;")
    # Enforce FK constraints (off by default in SQLite).
    cursor.execute("PRAGMA foreign_keys=ON;")
    # Wait up to 5s for a lock instead of failing instantly.
    cursor.execute("PRAGMA busy_timeout=5000;")
    # Checkpoint the WAL every ~1000 pages so the -wal file stays small.
    cursor.execute("PRAGMA wal_autocheckpoint=1000;")
    cursor.close()


# Session factory used by the API dependency and the scheduler worker.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep attributes usable after commit
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


async def init_db() -> None:
    """Create all tables. Import models here to avoid circular imports."""
    import models  # noqa: F401  (registers tables on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_light_migrations)


def _apply_light_migrations(conn) -> None:
    """
    Tiny in-place migrations for SQLite, which cannot add columns via
    create_all. Adds columns introduced after the table already existed.
    """
    def columns(table: str) -> set[str]:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}

    fundamentals = columns("fundamentals")
    if fundamentals and "financial_currency" not in fundamentals:
        conn.exec_driver_sql(
            "ALTER TABLE fundamentals ADD COLUMN financial_currency VARCHAR(8)"
        )

    # User-pinned flag added to stocks after the table existed.
    stocks = columns("stocks")
    if stocks and "tracked" not in stocks:
        conn.exec_driver_sql(
            "ALTER TABLE stocks ADD COLUMN tracked BOOLEAN NOT NULL DEFAULT 0"
        )
    if stocks and "fundamentals_checked_at" not in stocks:
        conn.exec_driver_sql(
            "ALTER TABLE stocks ADD COLUMN fundamentals_checked_at DATETIME"
        )

    # Company-info columns added to stock_profiles after the table existed.
    profiles = columns("stock_profiles")
    new_profile_cols = {
        "industry": "VARCHAR(96)",
        "description": "TEXT",
        "employees": "INTEGER",
        "website": "VARCHAR(160)",
        "country": "VARCHAR(64)",
        "city": "VARCHAR(64)",
        "address": "VARCHAR(200)",
        "phone": "VARCHAR(48)",
        "officers": "JSON",
    }
    if profiles:
        for name, coltype in new_profile_cols.items():
            if name not in profiles:
                conn.exec_driver_sql(
                    f"ALTER TABLE stock_profiles ADD COLUMN {name} {coltype}"
                )


async def wal_checkpoint(truncate: bool = True) -> None:
    """Fold the WAL back into the main DB file (TRUNCATE keeps -wal tiny)."""
    mode = "TRUNCATE" if truncate else "PASSIVE"
    async with engine.connect() as conn:
        await conn.exec_driver_sql(f"PRAGMA wal_checkpoint({mode});")


async def vacuum() -> None:
    """Reclaim free pages. Must run outside a transaction (AUTOCOMMIT)."""
    ac_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    async with ac_engine.connect() as conn:
        await conn.exec_driver_sql("VACUUM;")
