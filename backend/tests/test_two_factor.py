"""Two-factor authentication: sign-in step, methods, recovery codes, policy."""

import re

import pytest
from sqlalchemy import select

import mail
import services.two_factor as tf
from config import settings
from database import AsyncSessionLocal
from models import User
from services import crypto
from tests.conftest import ADMIN_EMAIL, PASSWORD, TOTP_SECRET, make_user, signed_in


async def _login(c, email=ADMIN_EMAIL, password=PASSWORD):
    return await c.post("/api/auth/login", json={"email": email, "password": password})


async def _verify(c, token, code, method="totp", remember=False):
    return await c.post("/api/auth/2fa/verify", json={
        "token": token, "method": method, "code": code, "remember_device": remember})


@pytest.fixture
def outbox(monkeypatch):
    """Email 'set up', messages captured instead of sent."""
    sent: list[mail.Email] = []

    async def send(email):
        sent.append(email)
        return "id"

    async def send_quietly(email):
        sent.append(email)
        return True

    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "send", send)
    monkeypatch.setattr(mail, "send_quietly", send_quietly)
    return sent


def _code_in(email: mail.Email) -> str:
    match = re.search(r"\b(\d{6})\b", email.subject)
    assert match, email.subject
    return match.group(1)


# --- TOTP primitives ---------------------------------------------------------------
def test_totp_matches_rfc6238_and_is_single_use():
    # RFC 6238 test vector (SHA-1, T=59s) for the ASCII secret "12345678901234567890".
    import base64

    secret = base64.b32encode(b"12345678901234567890").decode()
    assert tf.totp_code(secret, at=59) == "287082"  # last 6 of 94287082
    step = tf.match_totp(secret, "287 082", None, at=59)
    assert step == 1
    assert tf.match_totp(secret, "287082", step, at=59) is None  # replay refused
    assert tf.match_totp(secret, "000000", None, at=59) is None
    assert tf.otpauth_uri(secret, "a@b.co").startswith("otpauth://totp/Bursa%3Aa%40b.co?")
    assert tf.qr_svg("otpauth://x").startswith("<svg")


def test_secrets_are_encrypted_and_hashes_keyed():
    token = crypto.encrypt("JBSWY3DP")
    assert "JBSWY3DP" not in token and crypto.decrypt(token) == "JBSWY3DP"
    assert crypto.keyed_hash("a", "x") != crypto.keyed_hash("a", "y")


# --- sign-in with a second step ------------------------------------------------------
async def test_sign_in_with_authenticator_app(anon, client):
    r = (await _login(anon)).json()
    assert r["user"] is None and r["two_factor"]["methods"] == ["totp", "recovery"]
    assert r["two_factor"]["email_hint"] == "a***@example.com"
    assert "set-cookie" not in (await _login(anon)).headers  # no session before the code
    token = (await _login(anon)).json()["two_factor"]["token"]

    assert (await _verify(anon, token, "000000")).status_code == 400
    ok = await _verify(anon, token, tf.totp_code(TOTP_SECRET))
    assert ok.status_code == 200 and ok.json()["email"] == ADMIN_EMAIL
    assert (await anon.get("/api/watchlist")).status_code == 200
    # The challenge is used up; the same code can't sign in again.
    assert (await _verify(anon, token, tf.totp_code(TOTP_SECRET))).status_code == 400


async def test_wrong_codes_are_limited(anon, client, monkeypatch):
    monkeypatch.setattr(settings, "mfa_max_attempts", 3)
    token = (await _login(anon)).json()["two_factor"]["token"]
    for _ in range(2):
        assert "isn't right" in (await _verify(anon, token, "111111")).json()["detail"]
    assert "Too many" in (await _verify(anon, token, "111111")).json()["detail"]
    # That attempt is gone even with the right code.
    assert (await _verify(anon, token, tf.totp_code(TOTP_SECRET))).status_code == 400


async def test_wrong_codes_count_as_failed_sign_ins(anon, client, monkeypatch):
    monkeypatch.setattr(settings, "login_max_failures", 2)
    for _ in range(2):
        token = (await _login(anon)).json()["two_factor"]["token"]
        await _verify(anon, token, "111111")
    assert (await _login(anon)).status_code == 429


async def test_remember_this_device(anon, client):
    token = (await _login(anon)).json()["two_factor"]["token"]
    r = await _verify(anon, token, tf.totp_code(TOTP_SECRET), remember=True)
    trusted = [c for c in r.headers.get_list("set-cookie") if c.startswith("bursa_trusted=")]
    assert trusted and "path=/api/auth" in trusted[0].lower()
    await anon.post("/api/auth/logout")
    assert (await _login(anon)).json()["user"]["email"] == ADMIN_EMAIL  # no code needed
    await anon.post("/api/auth/logout")

    # Forgotten from another session: this browser still has the cookie, but it no
    # longer skips the code.
    assert (await client.delete("/api/auth/2fa/trusted-devices")).status_code == 204
    assert anon.cookies.get("bursa_trusted")
    assert (await _login(anon)).json()["two_factor"] is not None


async def test_email_codes_and_recovery_codes(anon, client, outbox):
    await make_user("bob@example.com")
    async with await signed_in("bob@example.com") as bob:
        assert (await bob.post("/api/auth/2fa/email")).status_code == 202
        code = _code_in(outbox[-1])
        assert (await bob.post("/api/auth/2fa/email/confirm", json={"code": "000000"})
                ).status_code == 400
        r = await bob.post("/api/auth/2fa/email/confirm", json={"code": code})
        codes = r.json()["recovery_codes"]
        assert len(codes) == 10 and all(re.fullmatch(r"[A-Z2-9]{5}-[A-Z2-9]{5}", c) for c in codes)
        status = (await bob.get("/api/auth/2fa")).json()
        assert status["email"] and status["recovery_codes_left"] == 10 and not status["required"]

    # Sign in: the email code is sent at once.
    step = (await _login(anon, "bob@example.com")).json()["two_factor"]
    assert step["methods"] == ["email", "recovery"] and step["email_sent"] is True
    code = _code_in(outbox[-1])
    resend = await anon.post("/api/auth/2fa/resend", json={"token": step["token"]})
    assert resend.status_code == 400  # at most one a minute
    assert (await _verify(anon, step["token"], code, "email")).status_code == 200

    # A recovery code works once (spaces/case don't matter) and the user is told.
    await anon.post("/api/auth/logout")
    token = (await _login(anon, "bob@example.com")).json()["two_factor"]["token"]
    assert (await _verify(anon, token, codes[0].lower(), "recovery")).status_code == 200
    assert "recovery code was used" in outbox[-1].text and "9 codes are left" in outbox[-1].text
    await anon.post("/api/auth/logout")
    token = (await _login(anon, "bob@example.com")).json()["two_factor"]["token"]
    assert (await _verify(anon, token, codes[0], "recovery")).status_code == 400


async def test_admin_must_set_up_2fa_and_keep_it(anon, client):
    await make_user("root@example.com", role="admin", totp=False)
    async with await signed_in("root@example.com") as root:
        me = (await root.get("/api/auth/me")).json()
        assert me["mfa_setup_required"] is True
        assert (await root.get("/api/stocks")).json()["detail"] == "two_factor_setup_required"
        assert (await root.get("/api/admin/users")).status_code == 403

        setup = (await root.post("/api/auth/2fa/totp")).json()
        assert setup["uri"].startswith("otpauth://") and "<svg" in setup["qr_svg"]
        bad = await root.post("/api/auth/2fa/totp/confirm", json={"code": "000000"})
        assert bad.status_code == 400
        r = await root.post("/api/auth/2fa/totp/confirm",
                            json={"code": tf.totp_code(setup["secret"])})
        assert len(r.json()["recovery_codes"]) == 10
        assert (await root.get("/api/stocks")).status_code == 200  # unlocked

        # Turning it off needs the password, and admins can't turn the last method off.
        off = "/api/auth/2fa/totp/disable"
        assert (await root.post(off, json={"password": "nope"})).json()["detail"] == (
            "Password is incorrect")
        r = await root.post(off, json={"password": PASSWORD})
        assert r.status_code == 400 and "Admins must keep" in r.json()["detail"]


async def test_user_can_turn_2fa_off(client):
    await make_user("bob@example.com", totp=True)
    async with await signed_in("bob@example.com") as bob:
        r = await bob.post("/api/auth/2fa/recovery-codes", json={"password": PASSWORD})
        assert len(r.json()["recovery_codes"]) == 10
        r = await bob.post("/api/auth/2fa/totp/disable", json={"password": PASSWORD})
        assert r.status_code == 204
        status = (await bob.get("/api/auth/2fa")).json()
        assert not status["totp"] and status["recovery_codes_left"] == 0  # all cleaned up


async def test_password_reset_keeps_2fa_and_admin_can_reset_it(anon, client, monkeypatch):
    monkeypatch.setattr(mail, "configured", lambda: False)
    uid = await make_user("bob@example.com", totp=True)
    link = (await client.post(f"/api/admin/users/{uid}/reset-link")).json()["link"]
    token = link.rsplit("/", 1)[1]
    await anon.post(f"/api/auth/password-reset/{token}", json={"password": "a new passphrase"})
    step = (await _login(anon, "bob@example.com", "a new passphrase")).json()
    assert step["two_factor"] is not None  # the inbox alone isn't enough

    users = (await client.get("/api/admin/users")).json()
    assert {u["email"]: u["has_2fa"] for u in users}["bob@example.com"] is True
    r = await client.post(f"/api/admin/users/{uid}/reset-2fa")
    assert r.status_code == 200 and r.json()["has_2fa"] is False
    assert (await _login(anon, "bob@example.com", "a new passphrase")).json()["user"]
    me = client.user_id  # type: ignore[attr-defined]
    assert (await client.post(f"/api/admin/users/{me}/reset-2fa")).status_code == 400


async def test_secret_is_never_stored_in_plain_text(client):
    async with AsyncSessionLocal() as s:
        stored = (await s.execute(select(User.totp_secret))).scalar_one()
    assert stored and TOTP_SECRET not in stored
