"""Account activity log, signed-in devices and new-device sign-in emails."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

import mail
from accounts import auth
from accounts.models import SecurityEvent
from accounts.security_log import describe_device
from clock import utcnow
from config import settings
from database import AsyncSessionLocal
from main import app
from tests.conftest import PASSWORD, make_user

BOB = "bob@example.com"
MAC_CHROME = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1"
)


@pytest.fixture
def outbox(monkeypatch):
    sent: list[mail.Email] = []

    async def send_quietly(email):
        sent.append(email)
        return True

    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "send_quietly", send_quietly)
    return sent


def _browser(user_agent: str = MAC_CHROME) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
        headers={"user-agent": user_agent},
    )


async def _login(c: AsyncClient, email: str = BOB, password: str = PASSWORD):
    return await c.post("/api/auth/login", json={"email": email, "password": password})


async def test_new_device_sign_in_is_flagged_and_emailed(client, outbox):
    await make_user(BOB)
    async with _browser() as laptop, _browser(IPHONE) as phone:
        assert (await _login(laptop)).status_code == 200  # first sign-in ever: not "new"
        await laptop.post("/api/auth/logout")
        assert (await _login(laptop)).status_code == 200  # same browser again
        assert outbox == []

        assert (await _login(phone)).status_code == 200
        assert len(outbox) == 1
        assert outbox[0].to == (BOB,) and "New sign-in" in outbox[0].subject
        assert "Safari on iPhone" in outbox[0].text

        events = (await phone.get("/api/auth/activity")).json()
    assert [(e["kind"], e["new_device"]) for e in events] == [
        ("sign_in", True), ("sign_in", False), ("sign_in", False),
    ]
    assert events[0]["device"] == "Safari on iPhone"
    assert events[1]["device"] == "Chrome on macOS"


async def test_failed_sign_ins_are_logged_for_real_accounts_only(client):
    await make_user(BOB)
    async with _browser() as c:
        assert (await _login(c, password="wrong password!")).status_code == 401
        assert (await _login(c, email="nobody@example.com")).status_code == 401
        await _login(c)
        events = (await c.get("/api/auth/activity")).json()
    assert [(e["kind"], e["detail"]) for e in events] == [
        ("sign_in", None), ("sign_in_failed", "wrong password"),
    ]
    async with AsyncSessionLocal() as s:
        total = await s.scalar(select(func.count()).select_from(SecurityEvent))
    assert total == 2  # nothing recorded for the unknown address


async def test_sign_out_one_or_all_other_devices(client):
    await make_user(BOB)
    await make_user("carol@example.com")
    async with _browser() as laptop, _browser(IPHONE) as phone, _browser() as carol:
        await _login(laptop)
        await _login(phone)
        await _login(carol, "carol@example.com")

        sessions = (await laptop.get("/api/auth/sessions")).json()
        assert [(s["device"], s["current"]) for s in sessions] == [
            ("Safari on iPhone", False), ("Chrome on macOS", True),
        ]
        mine, theirs = sessions[1]["id"], sessions[0]["id"]
        assert (await laptop.delete(f"/api/auth/sessions/{mine}")).status_code == 400
        assert (await carol.delete(f"/api/auth/sessions/{theirs}")).status_code == 404
        assert (await phone.get("/api/auth/me")).status_code == 200

        assert (await laptop.delete(f"/api/auth/sessions/{theirs}")).status_code == 204
        assert (await phone.get("/api/auth/me")).status_code == 401

        await _login(phone)
        assert (await laptop.post("/api/auth/sessions/sign-out-others")).status_code == 204
        assert (await phone.get("/api/auth/me")).status_code == 401
        assert (await laptop.get("/api/auth/me")).status_code == 200
        assert (await carol.get("/api/auth/me")).status_code == 200  # other accounts untouched

        events = (await laptop.get("/api/auth/activity")).json()
    assert [(e["kind"], e["detail"]) for e in events[:3]] == [
        ("other_sessions_revoked", "1 device"),
        ("sign_in", None),
        ("session_revoked", "Safari on iPhone"),
    ]


async def test_admin_changes_are_logged_and_admins_see_everyone(client):
    bob_id = await make_user(BOB)
    async with _browser() as bob:
        await _login(bob)
        assert (await bob.get("/api/admin/security-log")).status_code == 403
        r = await client.patch(f"/api/admin/users/{bob_id}", json={"role": "admin"})
        assert r.status_code == 200
        r = await client.patch(f"/api/admin/users/{bob_id}", json={"is_active": False})
        assert r.status_code == 200
        assert (await client.post(f"/api/admin/users/{bob_id}/reset-2fa")).status_code == 200

    log = (await client.get("/api/admin/security-log")).json()
    bobs = [(e["kind"], e["detail"]) for e in log if e["user_email"] == BOB]
    assert bobs == [
        ("two_factor_reset", "by admin"),
        ("account_disabled", "by admin"),
        ("role_changed", "to admin by admin"),
        ("sign_in", None),
    ]


async def test_password_and_two_factor_changes_are_logged(client):
    await make_user(BOB)
    async with _browser() as c:
        await _login(c)
        r = await c.post("/api/auth/password", json={
            "current_password": PASSWORD, "new_password": "a much longer passphrase 42"})
        assert r.status_code == 204
        await c.delete("/api/auth/2fa/trusted-devices")
        kinds = [e["kind"] for e in (await c.get("/api/auth/activity")).json()]
    assert kinds == ["trusted_devices_forgotten", "password_changed", "sign_in"]


async def test_old_entries_are_purged(client):
    async with AsyncSessionLocal() as s:
        old = utcnow() - timedelta(days=settings.security_log_days + 1)
        for at in (old, utcnow()):
            s.add(SecurityEvent(user_id=client.user_id, kind="sign_in", at=at))
        await s.commit()
    await auth.purge_expired()
    async with AsyncSessionLocal() as s:
        left = (await s.execute(select(SecurityEvent.at))).scalars().all()
    assert len(left) == 1 and left[0] > utcnow() - timedelta(days=1)


@pytest.mark.parametrize(("user_agent", "expected"), [
    (MAC_CHROME, "Chrome on macOS"),
    (IPHONE, "Safari on iPhone"),
    ("Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/141.0.0.0 Mobile Safari/537.36", "Chrome on Android"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0", "Edge on Windows"),
    ("Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0",
     "Firefox on Linux"),
    ("curl/8.7.1", "Unknown device"),
    (None, "Unknown device"),
])
def test_describe_device(user_agent, expected):
    assert describe_device(user_agent) == expected
