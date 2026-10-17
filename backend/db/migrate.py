"""
Schema migrations (Alembic), run on startup by `database.init_db()`.

Migration scripts live in `migrations/versions/`. After changing `models.py`,
create one with `alembic revision --autogenerate -m "..."` (from `backend/`),
review it, and commit it; every database is upgraded on its next start.

Databases created before Alembic was introduced (SQLite, via `create_all` plus
the hand-written column additions below) have no `alembic_version` table. They
first get those column additions; the baseline migration then creates only the
tables that are still missing, so they converge on the same schema as a fresh
database.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger("bursa.db")

_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def alembic_config(connection: Connection | None = None) -> Config:
    cfg = Config(str(_INI))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


async def migrate(engine: AsyncEngine) -> None:
    """Upgrade the database to the latest migration."""
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade)


def _upgrade(conn: Connection) -> None:
    tables = set(inspect(conn).get_table_names())
    if "alembic_version" not in tables and "stocks" in tables:
        log.info("Pre-migration database found; bringing it to the baseline schema")
        _pre_alembic_columns(conn)
    command.upgrade(alembic_config(conn), "head")


def _pre_alembic_columns(conn: Connection) -> None:
    """
    Columns added to existing tables before Alembic, when the schema was made by
    `create_all` (which never alters an existing table). Only SQLite databases
    predate Alembic, so this uses SQLite's PRAGMA. Frozen: new schema changes go
    in a migration script instead.
    """
    if conn.dialect.name != "sqlite":
        return

    def columns(table: str) -> set[str]:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}

    added = {
        "fundamentals": {"financial_currency": "VARCHAR(8)", "source": "VARCHAR(16)"},
        "stocks": {
            "tracked": "BOOLEAN NOT NULL DEFAULT 0",
            "listing_board": "VARCHAR(24)",
            "listed_on": "DATE",
            "idx_shares": "FLOAT",
            "idx_synced_at": "DATETIME",
            "splits_checked_at": "DATETIME",
            "full_history_at": "DATETIME",
            "fundamentals_checked_at": "DATETIME",
        },
        "stock_profiles": {
            "industry": "VARCHAR(96)",
            "description": "TEXT",
            "employees": "INTEGER",
            "website": "VARCHAR(160)",
            "country": "VARCHAR(64)",
            "city": "VARCHAR(64)",
            "address": "VARCHAR(200)",
            "phone": "VARCHAR(48)",
            "officers": "JSON",
        },
    }
    for table, cols in added.items():
        existing = columns(table)
        if not existing:  # table not created yet; the baseline migration makes it
            continue
        for name, coltype in cols.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
