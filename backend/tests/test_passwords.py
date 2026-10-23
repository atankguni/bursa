"""Password strength, the leaked-password check and weak-password handling."""

import hashlib

import pytest

import accounts.passwords as passwords
from accounts import auth
from accounts.models import User
from config import settings
from database import AsyncSessionLocal
from tests.conftest import ADMIN_EMAIL, PASSWORD, make_user, signed_in

STRONG = "tropical lantern quietly misplaced"


@pytest.mark.parametrize("password", [
    "short",
    "x" * 257,
    "1234567890ab",
    "password1234",
    "qwertyuiopas",
    "aaaaaaaaaaaaaaaa",
    "Password123!",
])
def test_weak_passwords_are_refused(password):
    assert passwords.strength_problem(password) is not None


def test_personal_and_app_words_count_against_strength():
    assert passwords.strength_problem("me@example.com", email="me@example.com")
    assert passwords.strength_problem("budisantoso2024", name="Budi Santoso")
    assert passwords.strength_problem("bursasaham123")
    assert passwords.strength_problem(STRONG, email="me@example.com", name="Budi") is None


def test_feedback_explains_why():
    problem = passwords.strength_problem("password1234")
    assert problem and problem.startswith("This password is too easy to guess.")
    assert len(passwords.strength_problem("short") or "") > 0


def _hibp(monkeypatch, password, count):
    """Fake range API: `password` appears `count` times (plus a padding row)."""
    digest = hashlib.sha1(password.encode()).hexdigest().upper()  # noqa: S324
    seen = []

    def fetch(prefix):
        seen.append(prefix)
        return f"{digest[5:]}:{count}\r\n{'0' * 35}:0"

    monkeypatch.setattr(settings, "password_breach_check", True)
    monkeypatch.setattr(passwords, "_fetch_range", fetch)
    return digest, seen


async def test_leaked_password_is_refused_sending_only_the_hash_prefix(monkeypatch):
    digest, seen = _hibp(monkeypatch, STRONG, 42)
    assert await passwords.breach_count(STRONG) == 42
    assert seen == [digest[:5]]  # never the password, never the full hash
    problem = await passwords.password_problem(STRONG)
    assert problem and "data breach" in problem

    assert await passwords.breach_count("another long unusual phrase") == 0


async def test_breach_service_down_does_not_block(monkeypatch):
    def down(prefix):
        raise OSError("unreachable")

    monkeypatch.setattr(settings, "password_breach_check", True)
    monkeypatch.setattr(passwords, "_fetch_range", down)
    assert await passwords.password_problem(STRONG) is None
    assert await passwords.is_weak(STRONG) is None  # unknown: keep the old verdict
    assert await passwords.is_weak("password1234") is True  # offline checks still apply


async def test_change_password_enforces_policy(client):
    r = await client.post("/api/auth/password", json={
        "current_password": PASSWORD, "new_password": "password1234"})
    assert r.status_code == 400 and "too easy to guess" in r.json()["detail"]
    r = await client.post("/api/auth/password", json={
        "current_password": PASSWORD, "new_password": STRONG})
    assert r.status_code == 204


async def _login(c, email, password):
    return await c.post("/api/auth/login", json={"email": email, "password": password})


async def test_weak_admin_password_must_be_changed(db, anon):
    await make_user(ADMIN_EMAIL, role="admin", password="password1234", totp=False)
    # Admin without 2FA is held at 2FA setup anyway; give them 2FA to isolate this.
    async with AsyncSessionLocal() as s:
        user = await auth.user_by_email(s, ADMIN_EMAIL)
        assert user is not None
        user.mfa_email = True
        await s.commit()
    async with await signed_in(ADMIN_EMAIL) as c:
        assert (await c.get("/api/stocks")).status_code == 200  # not known to be weak yet

    # Signing in reveals it (the trusted-device path skips 2FA here: use the API directly).
    r = await _login(anon, ADMIN_EMAIL, "password1234")
    assert r.status_code == 200
    async with AsyncSessionLocal() as s:
        user = await auth.user_by_email(s, ADMIN_EMAIL)
        assert user is not None and user.password_weak and user.password_change_required

    async with await signed_in(ADMIN_EMAIL) as c:
        me = (await c.get("/api/auth/me")).json()
        assert me["password_weak"] is True and me["password_change_required"] is True
        r = await c.get("/api/stocks")
        assert r.status_code == 403 and r.json()["detail"] == "password_change_required"
        r = await c.post("/api/auth/password", json={
            "current_password": "password1234", "new_password": STRONG})
        assert r.status_code == 204
        me = (await c.get("/api/auth/me")).json()
        assert me["password_weak"] is False and me["password_change_required"] is False
        assert (await c.get("/api/stocks")).status_code == 200


async def test_weak_user_password_is_flagged_not_blocked(db, anon):
    await make_user("bob@example.com", password="password1234")
    assert (await _login(anon, "bob@example.com", "password1234")).status_code == 200
    me = (await anon.get("/api/auth/me")).json()
    assert me["password_weak"] is True and me["password_change_required"] is False
    assert (await anon.get("/api/stocks")).status_code == 200


async def test_strong_password_at_sign_in_clears_the_flag(db, anon):
    await make_user("bob@example.com")
    async with AsyncSessionLocal() as s:
        user = await auth.user_by_email(s, "bob@example.com")
        assert isinstance(user, User)
        user.password_weak = True
        await s.commit()
    assert (await _login(anon, "bob@example.com", PASSWORD)).status_code == 200
    assert (await anon.get("/api/auth/me")).json()["password_weak"] is False


async def test_options_expose_policy(anon):
    r = (await anon.get("/api/auth/options")).json()
    assert r["password_min_length"] == settings.password_min_length
    assert r["password_min_score"] == settings.password_min_score
