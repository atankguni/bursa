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
# Fixed 2FA server secret, so tests never write data/secret.key.
os.environ["SECRET_KEY"] = "test-secret-key-0123456789-abcdefghijklmnop"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from config import settings  # noqa: E402
from database import AsyncSessionLocal, engine, init_db  # noqa: E402
from main import app  # noqa: E402
from models import Base, User  # noqa: E402
from services import auth, crypto  # noqa: E402
from services.bootstrap import seed  # noqa: E402

ADMIN_EMAIL = "admin@example.com"
PASSWORD = "correct horse battery"
# Authenticator secret of users made with totp=True (admins by default: 2FA is
# required for them). services.two_factor.totp_code(TOTP_SECRET) gives a code.
TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


async def make_user(
    email: str, role: str = "user", password: str = PASSWORD, totp: bool | None = None
) -> int:
    with_totp = role == "admin" if totp is None else totp
    async with AsyncSessionLocal() as s:
        user = User(email=email, name=email.split("@")[0], role=role,
                    password_hash=auth.hash_password(password),
                    totp_secret=crypto.encrypt(TOTP_SECRET) if with_totp else None)
        s.add(user)
        await s.commit()
        return user.id


async def signed_in(email: str) -> AsyncClient:
    """A client with a session cookie for `email` (caller closes it)."""
    async with AsyncSessionLocal() as s:
        user = await auth.user_by_email(s, email)
        assert user is not None
        raw = await auth.create_session(s, user, "pytest", None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                       cookies={settings.session_cookie_name: raw})


@pytest_asyncio.fixture
async def db():
    """Migrated + seeded database, torn down after the test."""
    await init_db()
    await seed()
    auth._failures.clear()
    yield
    # Tear down the DB between tests for isolation.
    if engine.dialect.name != "sqlite":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    for suffix in ("-wal", "-shm"):
        side = _TEST_DB.with_name(_TEST_DB.name + suffix)
        if side.exists():
            side.unlink()


@pytest_asyncio.fixture
async def anon(db):
    """Not signed in."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def client(db):
    """Signed in as an admin; `client.user_id` is their id."""
    user_id = await make_user(ADMIN_EMAIL, role="admin")
    async with await signed_in(ADMIN_EMAIL) as c:
        c.user_id = user_id  # type: ignore[attr-defined]
        yield c


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
