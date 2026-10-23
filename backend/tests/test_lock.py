"""Inactivity lock: idle browsers lock; the password (no 2FA code) unlocks them."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from accounts.models import SecurityEvent, UserSession
from clock import utcnow
from config import settings
from database import AsyncSessionLocal
from tests.conftest import PASSWORD, make_user, signed_in

USER = "user@example.com"


async def _idle(minutes: float) -> None:
    """Every session was last used `minutes` ago."""
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(UserSession).values(active_at=utcnow() - timedelta(minutes=minutes))
        )
        await s.commit()


async def _kinds(user_id: int) -> list[str]:
    async with AsyncSessionLocal() as s:
        return list((await s.execute(
            select(SecurityEvent.kind).where(SecurityEvent.user_id == user_id)
            .order_by(SecurityEvent.id)
        )).scalars())


@pytest.fixture
async def user(db):
    user_id = await make_user(USER, totp=True)  # 2FA on: unlocking still needs no code
    async with await signed_in(USER) as c:
        c.user_id = user_id  # type: ignore[attr-defined]
        yield c


async def test_idle_browser_locks_and_password_unlocks(user):
    assert (await user.get("/api/preferences")).json()["lock_minutes"] == 15  # default
    await _idle(14)
    assert (await user.get("/api/watchlist")).status_code == 200

    await _idle(16)
    r = await user.get("/api/watchlist")
    assert (r.status_code, r.json()["detail"]) == (423, "session_locked")
    me = (await user.get("/api/auth/me")).json()
    assert me["locked"] is True and me["name"] == "user"  # the lock screen shows who
    assert (await user.post("/api/auth/active")).status_code == 423  # activity can't unlock

    r = await user.post("/api/auth/unlock", json={"password": "wrong"})
    assert r.status_code == 400 and "4 attempts left" in r.json()["detail"]
    r = await user.post("/api/auth/unlock", json={"password": PASSWORD})
    assert r.status_code == 200 and r.json()["locked"] is False
    assert (await user.get("/api/watchlist")).status_code == 200
    assert (await _kinds(user.user_id))[-2:] == ["sign_in_failed", "session_unlocked"]


async def test_too_many_wrong_passwords_sign_out(user):
    await user.post("/api/auth/lock")
    for _ in range(settings.lock_max_attempts - 1):
        assert (await user.post("/api/auth/unlock", json={"password": "x"})).status_code == 400
    r = await user.post("/api/auth/unlock", json={"password": "x"})
    assert r.status_code == 401 and "Signed out" in r.json()["detail"]
    assert (await user.get("/api/auth/me")).status_code == 401  # the session is gone
    assert (await _kinds(user.user_id))[-1] == "session_revoked"


async def test_lock_now_and_lock_survives_setting_change(user):
    assert (await user.post("/api/auth/lock")).status_code == 204
    assert (await user.get("/api/watchlist")).status_code == 423
    # Settings can't be changed while locked, and the lock isn't lifted by them.
    r = await user.put("/api/preferences", json={"lock_minutes": 0})
    assert r.status_code == 423
    assert (await user.get("/api/auth/me")).json()["locked"] is True


async def test_activity_reports_keep_the_browser_open(user):
    await _idle(14)
    assert (await user.post("/api/auth/active")).status_code == 204
    async with AsyncSessionLocal() as s:
        active_at = (await s.execute(select(UserSession.active_at))).scalar_one()
    assert utcnow() - active_at < timedelta(seconds=5)
    await _idle(1)  # recent enough: not locked
    assert (await user.get("/api/watchlist")).status_code == 200


async def test_users_can_turn_it_off_or_lengthen_it(user):
    r = await user.put("/api/preferences", json={"lock_minutes": 0})
    assert r.status_code == 200 and r.json()["lock_minutes"] == 0
    await _idle(600)
    assert (await user.get("/api/watchlist")).status_code == 200
    assert (await user.put("/api/preferences", json={"lock_minutes": 7})).status_code == 422


async def test_admins_always_lock_within_the_cap(client):
    r = await client.put("/api/preferences", json={"lock_minutes": 0})
    assert r.status_code == 400 and "15 minutes or less" in r.json()["detail"]
    assert (await client.put("/api/preferences", json={"lock_minutes": 60})).status_code == 400
    r = await client.put("/api/preferences", json={"lock_minutes": 5})
    assert r.json()["lock_minutes"] == 5
    await _idle(6)
    assert (await client.get("/api/admin/users")).status_code == 423


async def test_other_browsers_are_independent(user):
    async with await signed_in(USER) as other:
        await user.post("/api/auth/lock")
        assert (await other.get("/api/watchlist")).status_code == 200
        assert (await user.get("/api/watchlist")).status_code == 423


def test_effective_minutes():
    from accounts.auth import effective_lock_minutes

    assert effective_lock_minutes(None, "user") == 15
    assert effective_lock_minutes(0, "user") == 0
    assert effective_lock_minutes(60, "user") == 60
    assert effective_lock_minutes(0, "admin") == 15  # stored before becoming admin
    assert effective_lock_minutes(60, "admin") == 15
    assert effective_lock_minutes(5, "admin") == 5
