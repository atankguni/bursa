"""Shared test fixtures.

Uses a throwaway SQLite file and talks to the FastAPI app in-process via httpx's
ASGITransport (which, unlike a real server, does NOT run the lifespan — so no
network backfill or scheduler during tests).

To run the suite against a server database instead, point TEST_DATABASE_URL at
an empty, disposable database (its tables are dropped after every test):

    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host/bursa_test pytest
"""

import os
import pathlib

# Point the app at a temp DB *before* any app module imports config/database.
_TEST_DB = pathlib.Path(__file__).parent / "test_bursa.db"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB}"
)

import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from database import engine, init_db  # noqa: E402
from db.migrate import alembic_config  # noqa: E402
from main import app  # noqa: E402
from services.bootstrap import seed  # noqa: E402


@pytest_asyncio.fixture
async def client():
    await init_db()
    await seed()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # Tear down the DB between tests for isolation.
    if engine.dialect.name != "sqlite":
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: command.downgrade(alembic_config(c), "base"))
    await engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    for suffix in ("-wal", "-shm"):
        side = _TEST_DB.with_name(_TEST_DB.name + suffix)
        if side.exists():
            side.unlink()


@pytest_asyncio.fixture(autouse=True)
async def _no_network(monkeypatch):
    """
    Tests must never reach Yahoo. Block yfinance's network entry points; a test
    that fakes yfinance (monkeypatching these itself) overrides the guard.
    """
    import yfinance as yf

    def blocked(*args, **kwargs):
        raise AssertionError("test tried to reach Yahoo (yfinance network call)")

    for name in ("download", "Ticker", "Search"):
        monkeypatch.setattr(yf, name, blocked)
    yield
