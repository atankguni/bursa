"""
Schema migrations (Alembic), run on startup by `database.init_db()`.

Migration scripts live in `migrations/versions/`. After changing `models.py`,
create one with `alembic revision --autogenerate -m "..."` (from `backend/`),
review it, and commit it; every database is upgraded on its next start.

The migrations were squashed into one baseline on 2026-10-23. A database from
before that is converted (copied into a fresh one) with scripts/convert_db.py.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger("bursa.db")

_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


class OutdatedDatabase(RuntimeError):
    """The database predates the migration squash; it needs converting."""


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
    cfg = alembic_config(conn)
    tables = set(inspect(conn).get_table_names())
    known = {s.revision for s in ScriptDirectory.from_config(cfg).walk_revisions()}
    current: list[str] = (
        list(conn.execute(text("SELECT version_num FROM alembic_version")).scalars())
        if "alembic_version" in tables
        else []
    )
    if (tables - {"alembic_version"} and not current) or set(current) - known:
        raise OutdatedDatabase(
            "This database was made by an older Bursa version whose schema can't be "
            "upgraded in place. Convert it first: "
            "python scripts/convert_db.py <old.db> <new.db> (see docs/development.md)."
        )
    command.upgrade(cfg, "head")
