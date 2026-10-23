"""
scripts/check_schema.py
-----------------------
Schema drift check (run by `make check`): migrate an empty database to the
latest revision and compare it with models.py. Any difference means a model
change without a migration (or a migration that doesn't match the models).

    python scripts/check_schema.py                      # a temporary SQLite file
    python scripts/check_schema.py postgresql+asyncpg://...   # an EMPTY database
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from sqlalchemy import Connection  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from db.migrate import migrate  # noqa: E402
from models import Base  # noqa: E402  (importing models registers every table)


def _diff(conn: Connection) -> list[Any]:
    ctx = MigrationContext.configure(conn, opts={"compare_type": True})
    return list(compare_metadata(ctx, Base.metadata))


async def drift(url: str) -> list[Any]:
    engine = create_async_engine(url)
    try:
        await migrate(engine)
        async with engine.connect() as conn:
            return await conn.run_sync(_diff)
    finally:
        await engine.dispose()


def main() -> None:
    if len(sys.argv) > 1:
        url = sys.argv[1]
        found = asyncio.run(drift(url))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite+aiosqlite:///{tmp}/schema.db"
            found = asyncio.run(drift(url))
    dialect = url.split(":", 1)[0]
    if found:
        print(f"Schema drift on {dialect}: models.py and the migrations disagree:")
        for item in found:
            print(f"  {item}")
        print("Generate a migration: alembic revision --autogenerate -m '...'")
        raise SystemExit(1)
    print(f"Schema matches the migrations ({dialect}).")


if __name__ == "__main__":
    main()
