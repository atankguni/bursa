"""Shared test fixtures.

Uses a throwaway SQLite file and talks to the FastAPI app in-process via httpx's
ASGITransport (which, unlike a real server, does NOT run the lifespan — so no
network backfill or scheduler during tests).
"""

import os
import pathlib

# Point the app at a temp DB *before* any app module imports config/database.
_TEST_DB = pathlib.Path(__file__).parent / "test_bursa.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from services.bootstrap import seed  # noqa: E402


@pytest_asyncio.fixture
async def client():
    await init_db()
    await seed()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # Tear down the DB file between tests for isolation.
    await engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    for suffix in ("-wal", "-shm"):
        side = _TEST_DB.with_name(_TEST_DB.name + suffix)
        if side.exists():
            side.unlink()
