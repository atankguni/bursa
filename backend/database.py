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

# Allow the DB path to be overridden by the environment (Docker sets this).
# Default resolves to ./data/bursa.db relative to the backend working dir.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/bursa.db",
)

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


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields a scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Import models here to avoid circular imports."""
    import models  # noqa: F401  (registers tables on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
