"""
Portable "insert or update" across SQL dialects.

Every database spells upsert differently:

* SQLite / PostgreSQL: ``INSERT ... ON CONFLICT (keys) DO UPDATE SET c = excluded.c``
* MySQL / MariaDB:     ``INSERT ... ON DUPLICATE KEY UPDATE c = VALUES(c)``

Services call :func:`upsert` and never import a dialect-specific ``insert``, so
switching ``DATABASE_URL`` to another supported database needs no code changes.
To support a new SQL dialect, add a branch to :func:`_statement`.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.dml import Insert

# Bound-parameter limits: SQLite 32766, PostgreSQL (asyncpg) 32767, MySQL 65535.
# Stay under the smallest so one chunk size works everywhere.
_MAX_PARAMS = 30_000

Row = Mapping[str, Any]


def dialect_name(session: AsyncSession) -> str:
    """The SQLAlchemy dialect behind a session ("sqlite", "postgresql", "mysql", ...)."""
    return session.get_bind().dialect.name


def _statement(
    dialect: str,
    model: type[DeclarativeBase],
    rows: Sequence[Row],
    keys: Sequence[str],
    update: Sequence[str],
) -> Insert:
    if dialect in ("sqlite", "postgresql"):
        ins = (sqlite.insert if dialect == "sqlite" else postgresql.insert)(model)
        ins = ins.values(list(rows))
        if not update:
            return ins.on_conflict_do_nothing(index_elements=list(keys))
        return ins.on_conflict_do_update(
            index_elements=list(keys), set_={c: ins.excluded[c] for c in update}
        )
    if dialect in ("mysql", "mariadb"):
        ins = mysql.insert(model).values(list(rows))
        if not update:
            # Assigning a key column to itself is a no-op that, unlike INSERT
            # IGNORE, still surfaces other errors (bad types, FK violations).
            return ins.on_duplicate_key_update({keys[0]: model.__table__.c[keys[0]]})
        return ins.on_duplicate_key_update({c: ins.inserted[c] for c in update})
    raise NotImplementedError(
        f"upsert() has no adapter for the {dialect!r} dialect; add one in db/upsert.py"
    )


async def upsert(
    session: AsyncSession,
    model: type[DeclarativeBase],
    rows: Row | Sequence[Row],
    *,
    keys: Sequence[str],
    update: Sequence[str] | None = None,
) -> int:
    """
    Insert `rows` into `model`'s table; on a clash of the unique `keys`, overwrite
    the `update` columns with the new values.

    * ``update=None`` overwrites every non-key column present in the rows.
    * ``update=[]`` keeps the existing row untouched (insert-or-ignore).

    Large inputs are split to stay under the dialect's bound-parameter limit.
    Does not commit. Returns the number of rows submitted.
    """
    batch: list[Row] = [rows] if isinstance(rows, Mapping) else list(rows)
    if not batch:
        return 0
    if update is None:
        update = [c for c in batch[0] if c not in keys]
    dialect = dialect_name(session)
    size = max(1, _MAX_PARAMS // max(1, len(batch[0])))
    for start in range(0, len(batch), size):
        await session.execute(
            _statement(dialect, model, batch[start : start + size], keys, update)
        )
    return len(batch)
