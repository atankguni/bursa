"""
Per-dialect connection setup and housekeeping.

SQLite needs pragmas on every connection plus periodic WAL checkpoints and
VACUUM; server databases (PostgreSQL, MySQL) handle all of that themselves.
The scheduler calls `checkpoint()` / `compact()` without knowing which database
is in use.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine


def configure(engine: AsyncEngine) -> None:
    """Register connection-level settings for the engine's dialect."""
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
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


async def checkpoint(engine: AsyncEngine) -> None:
    """Fold SQLite's WAL back into the main file (TRUNCATE keeps -wal tiny)."""
    if engine.dialect.name != "sqlite":
        return
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE);")


async def compact(engine: AsyncEngine) -> str | None:
    """
    Reclaim space / refresh planner statistics. Returns what ran, or None when
    the database needs nothing (MySQL/InnoDB manages itself).
    """
    sql = {"sqlite": "VACUUM", "postgresql": "VACUUM (ANALYZE)"}.get(engine.dialect.name)
    if sql is None:
        return None
    # Both must run outside a transaction.
    autocommit = engine.execution_options(isolation_level="AUTOCOMMIT")
    async with autocommit.connect() as conn:
        await conn.exec_driver_sql(sql)
    return sql
