"""Accounts: sign-in, sessions, invites, resets, admin, per-user data isolation."""

from datetime import timedelta

from sqlalchemy import func, select

import mail
from config import settings
from database import AsyncSessionLocal
from models import Invite, User, UserSession
from services import auth
from tests.conftest import ADMIN_EMAIL, PASSWORD, make_user, signed_in


async def _login(c, email=ADMIN_EMAIL, password=PASSWORD):
    return await c.post("/api/auth/login", json={"email": email, "password": password})


# --- protection ---------------------------------------------------------------
async def test_everything_but_health_and_sign_in_needs_a_session(anon):
    assert (await anon.get("/api/health")).status_code == 200
    assert (await anon.get("/api/auth/options")).status_code == 200
    for path in ("/api/stocks", "/api/watchlist", "/api/portfolio", "/api/alerts",
                 "/api/preferences", "/api/screener", "/api/market/overview",
                 "/api/indexes", "/api/auth/me", "/api/admin/users", "/api/data-health"):
        assert (await anon.get(path)).status_code == 401, path


async def test_admin_only_routes(client):
    await make_user("bob@example.com")
    async with await signed_in("bob@example.com") as bob:
        for method, path in (
            ("get", "/api/admin/users"), ("get", "/api/data-health"),
            ("get", "/api/mail/status"), ("post", "/api/screener/sync"),
            ("post", "/api/stocks/BBCA/track"), ("post", "/api/watchlist/refresh"),
            ("post", "/api/alerts/notifications/test"),
        ):
            assert (await getattr(bob, method)(path)).status_code == 403, path
        assert (await bob.get("/api/screener")).status_code == 200  # reading is fine


async def test_cross_site_writes_are_refused(client):
    evil = {"origin": "https://evil.example"}
    r = await client.post("/api/watchlist/BBCA", headers=evil)
    assert r.status_code == 403
    r = await client.post("/api/watchlist/BBCA", headers={"origin": "null"})
    assert r.status_code == 403
    ok = await client.delete("/api/watchlist/BBCA", headers={"origin": "http://test"})
    assert ok.status_code == 404  # same host passes the check (and isn't on the list)
    assert (await client.get("/api/stocks", headers=evil)).status_code == 200  # reads pass


# --- sign in / out ------------------------------------------------------------
async def test_login_me_logout(anon, client):
    await make_user("bob@example.com")  # no 2FA: the password signs in directly
    r = await _login(anon, "bob@example.com")
    assert r.status_code == 200 and r.json()["user"]["role"] == "user"
    assert r.json()["two_factor"] is None
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert (await anon.get("/api/auth/me")).json()["email"] == "bob@example.com"
    assert (await anon.post("/api/auth/logout")).status_code == 204
    assert (await anon.get("/api/auth/me")).status_code == 401


async def test_login_is_case_insensitive_and_errors_are_uniform(anon, client):
    assert (await _login(anon, " Admin@Example.COM ")).status_code == 200
    wrong = await _login(anon, password="nope nope nope")
    unknown = await _login(anon, "ghost@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_login_throttling(anon, client, monkeypatch):
    monkeypatch.setattr(settings, "login_max_failures", 3)
    for _ in range(3):
        assert (await _login(anon, password="wrong password")).status_code == 401
    assert (await _login(anon)).status_code == 429  # even the right password, for now


async def test_disabled_user_is_signed_out(client):
    uid = await make_user("bob@example.com")
    async with await signed_in("bob@example.com") as bob:
        r = await client.patch(f"/api/admin/users/{uid}", json={"is_active": False})
        assert r.status_code == 200 and r.json()["is_active"] is False
        assert (await bob.get("/api/auth/me")).status_code == 401
        assert (await _login(bob, "bob@example.com")).status_code == 401


async def test_expired_session_is_rejected(client):
    async with AsyncSessionLocal() as s:
        sess = (await s.execute(select(UserSession))).scalar_one()
        sess.expires_at = sess.created_at - timedelta(days=1)
        await s.commit()
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_change_password_signs_out_other_browsers(client):
    async with await signed_in(ADMIN_EMAIL) as other:
        weak = await client.post("/api/auth/password",
                                 json={"current_password": PASSWORD, "new_password": "short"})
        assert weak.status_code == 400 and "at least" in weak.json()["detail"]
        bad = await client.post("/api/auth/password",
                                json={"current_password": "wrong", "new_password": "x" * 12})
        assert bad.status_code == 400
        ok = await client.post("/api/auth/password", json={
            "current_password": PASSWORD, "new_password": "a brand new passphrase"})
        assert ok.status_code == 204
        assert (await client.get("/api/auth/me")).status_code == 200  # this browser stays
        assert (await other.get("/api/auth/me")).status_code == 401


# --- invites -------------------------------------------------------------------
async def test_setup_invite_creates_first_admin(anon):
    await auth.ensure_setup_invite()
    async with AsyncSessionLocal() as s:
        invite = (await s.execute(select(Invite))).scalar_one()
        assert invite.email == "" and invite.role == "admin"
        # The raw token isn't stored; make a known one for the test.
        raw, invite.token_hash = "setup-token", auth.hash_token("setup-token")
        await s.commit()

    info = (await anon.get(f"/api/auth/invites/{raw}")).json()
    assert info == {"email": None, "role": "admin"}
    r = await anon.post(f"/api/auth/invites/{raw}/accept", json={
        "name": "Lalu", "email": "Owner@Example.com", "password": PASSWORD})
    assert r.status_code == 201 and r.json()["email"] == "owner@example.com"
    assert r.json()["role"] == "admin" and r.json()["mfa_setup_required"] is True
    # 2FA is required for admins: only the setup works until it is turned on.
    blocked = await anon.get("/api/watchlist")
    assert blocked.status_code == 403 and blocked.json()["detail"] == "two_factor_setup_required"
    assert (await anon.get("/api/auth/2fa")).json()["required"] is True
    # Used once only; and no new setup link once an account exists.
    again = await anon.post(f"/api/auth/invites/{raw}/accept",
                            json={"name": "X", "email": "x@example.com", "password": PASSWORD})
    assert again.status_code == 400
    await auth.ensure_setup_invite()
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(Invite))).scalar_one() == 1


async def test_admin_invites_a_user(client, anon, monkeypatch):
    monkeypatch.setattr(mail, "configured", lambda: False)
    r = await client.post("/api/admin/invites", json={"email": "Bob@Example.com"})
    assert r.status_code == 201 and r.json()["emailed"] is False
    link = r.json()["link"]
    assert link.startswith(f"{settings.public_url}/invite/")
    token = link.rsplit("/", 1)[1]
    pending = (await client.get("/api/admin/invites")).json()
    assert [i["email"] for i in pending] == ["bob@example.com"]

    assert (await anon.get(f"/api/auth/invites/{token}")).json()["email"] == "bob@example.com"
    weak = await anon.post(f"/api/auth/invites/{token}/accept",
                           json={"name": "Bob", "password": "bob@example.com"})
    assert weak.status_code == 400
    r = await anon.post(f"/api/auth/invites/{token}/accept",
                        json={"name": "Bob", "password": PASSWORD, "email": "evil@x.com"})
    assert r.status_code == 201
    assert r.json()["email"] == "bob@example.com"  # the invite decides the email
    assert r.json()["role"] == "user"
    assert (await client.get("/api/admin/invites")).json() == []

    dup = await client.post("/api/admin/invites", json={"email": "bob@example.com"})
    assert dup.status_code == 400


async def test_admin_safety_rails(client):
    me = client.user_id  # type: ignore[attr-defined]
    assert (await client.patch(f"/api/admin/users/{me}", json={"role": "user"})).status_code == 400
    assert (await client.delete(f"/api/admin/users/{me}")).status_code == 400
    uid = await make_user("bob@example.com")
    r = await client.patch(f"/api/admin/users/{uid}", json={"role": "admin"})
    assert r.json()["role"] == "admin"
    assert (await client.delete(f"/api/admin/users/{uid}")).status_code == 204
    users = (await client.get("/api/admin/users")).json()
    assert [u["email"] for u in users] == [ADMIN_EMAIL]


# --- password reset --------------------------------------------------------------
async def test_reset_link_from_admin(client, anon, monkeypatch):
    monkeypatch.setattr(mail, "configured", lambda: False)
    uid = await make_user("bob@example.com")
    async with await signed_in("bob@example.com") as bob:
        link = (await client.post(f"/api/admin/users/{uid}/reset-link")).json()["link"]
        token = link.rsplit("/", 1)[1]
        assert (await anon.get(f"/api/auth/password-reset/{token}")).status_code == 204
        r = await anon.post(f"/api/auth/password-reset/{token}",
                            json={"password": "a fresh passphrase"})
        assert r.status_code == 204
        assert (await bob.get("/api/auth/me")).status_code == 401  # signed out everywhere
    assert (await _login(anon, "bob@example.com", "a fresh passphrase")).status_code == 200
    reused = await anon.post(f"/api/auth/password-reset/{token}", json={"password": "y" * 12})
    assert reused.status_code == 400


async def test_forgot_password_by_email(anon, client, monkeypatch):
    r = await anon.post("/api/auth/password-reset", json={"email": ADMIN_EMAIL})
    assert r.status_code == 400  # no email provider: ask the admin instead

    sent: list[mail.Email] = []

    async def fake_send(email):
        sent.append(email)
        return True

    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "send_quietly", fake_send)
    for email in (ADMIN_EMAIL, "ghost@example.com", ADMIN_EMAIL):
        r = await anon.post("/api/auth/password-reset", json={"email": email})
        assert r.status_code == 202  # same answer whether the account exists or not
    assert len(sent) == 1  # unknown email: nothing; repeat within 2 minutes: nothing
    assert sent[0].to == (ADMIN_EMAIL,) and "/reset/" in sent[0].text


# --- per-user data -------------------------------------------------------------------
async def test_users_have_separate_data(client):
    await make_user("bob@example.com")
    async with await signed_in("bob@example.com") as bob:
        await bob.put("/api/preferences", json={"investing_style": "trader"})
        assert (await client.get("/api/preferences")).json()["investing_style"] == "investor"

        assert (await client.post("/api/watchlist/BBCA")).status_code == 201
        assert (await bob.post("/api/watchlist/BBCA")).status_code == 201  # own list
        assert (await bob.delete("/api/watchlist/BBCA")).status_code == 204
        assert [w["ticker"] for w in (await client.get("/api/watchlist")).json()] == ["BBCA"]
        assert (await bob.get("/api/watchlist")).json() == []

        tx = {"ticker": "BBCA", "side": "buy", "quantity": 100, "price": 9000,
              "trade_date": "2026-01-02"}
        tx_id = (await client.post("/api/portfolio/transactions", json=tx)).json()["id"]
        assert (await bob.get("/api/portfolio/transactions")).json() == []
        assert (await bob.delete(f"/api/portfolio/transactions/{tx_id}")).status_code == 404

        alert = {"ticker": "BBCA", "type": "price_above", "threshold": 1}
        alert_id = (await client.post("/api/alerts", json=alert)).json()["id"]
        assert (await bob.get("/api/alerts")).json() == []
        assert (await bob.post(f"/api/alerts/{alert_id}/toggle")).status_code == 404


async def test_purge_expired(client):
    async with AsyncSessionLocal() as s:
        sess = (await s.execute(select(UserSession))).scalar_one()
        sess.expires_at = sess.created_at - timedelta(days=1)
        await s.commit()
    assert await auth.purge_expired() == 1


def test_verify_password():
    assert auth.verify_password(None, "anything") is False
    user = User(email="a@b.co", name="a", password_hash=auth.hash_password("pw pw pw pw"))
    assert auth.verify_password(user, "pw pw pw pw") and not auth.verify_password(user, "pw")
