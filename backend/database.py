"""
database.py
-----------
Async SQLAlchemy 2.0 engine + session factory.

The database is chosen by `DATABASE_URL` (SQLite by default). Everything
dialect-specific lives in the `db` package, so the rest of the app is the same
on SQLite or PostgreSQL:

* `db.maintenance` -> connection setup (SQLite pragmas) and housekeeping;
* `db.upsert`      -> portable insert-or-update;
* `db.migrate`     -> Alembic schema migrations, run by `init_db()` on startup.
"""

import os

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings
from db import maintenance

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
# pool_pre_ping drops connections a database server closed while idle.
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
maintenance.configure(engine)


# Session factory used by the API dependency and the scheduler worker.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep attributes usable after commit
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models. Constraints and indexes get
    predictable names (Alembic needs a name to change or drop one later)."""

    metadata = MetaData(naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
    })


async def init_db() -> None:
    """Bring the schema up to date (Alembic migrations). Awaited on startup."""
    from db.migrate import migrate

    await migrate(engine)
