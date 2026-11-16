"""Settings additions: notifications (alert emails, quiet hours), benchmark and risk
limits, and your own account (name, email change, clearing the portfolio,
deleting the account)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

import mail
from accounts.models import SecurityEvent
from accounts.schemas import QuietHours
from alerts.emails import in_quiet_hours, send_alert_emails
from alerts.models import Alert, AlertEvent
from clock import utcnow
from config import settings
from database import AsyncSessionLocal
from portfolio.models import Watchlist
from tests.conftest import PASSWORD, add_daily_bars, make_user, signed_in


@pytest.fixture
def outbox(monkeypatch):
    sent: list[mail.Email] = []

    async def send_quietly(email):
        sent.append(email)
        return True

    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "send_quietly", send_quietly)
    return sent


async def _kinds(user_id: int) -> list[str]:
    async with AsyncSessionLocal() as s:
        return list((await s.execute(
            select(SecurityEvent.kind).where(SecurityEvent.user_id == user_id)
        )).scalars().all())


# --- preferences ---------------------------------------------------------------
async def test_notification_and_investing_preferences(client):
    put = lambda body: client.put("/api/preferences", json=body)  # noqa: E731
    p = (await put({"alert_emails": True, "benchmark": "LQ45",
                    "quiet_hours": {"start": "21:30", "end": "06:00"},
                    "risk_limits": {"stock_pct": 30, "sector_pct": 50}})).json()
    assert p["alert_emails"] is True and p["benchmark"] == "LQ45"
    assert p["quiet_hours"] == {"start": "21:30", "end": "06:00"}
    assert p["risk_limits"] == {"stock_pct": 30.0, "sector_pct": 50.0}

    # Leaving quiet_hours out keeps it; sending null turns it off.
    assert (await put({"benchmark": "JII"})).json()["quiet_hours"] is not None
    assert (await put({"quiet_hours": None})).json()["quiet_hours"] is None

    for bad in ({"quiet_hours": {"start": "25:00", "end": "06:00"}},
                {"benchmark": "IDX30"},  # no full history to compare with
                {"risk_limits": {"stock_pct": 2, "sector_pct": 40}}):
        assert (await put(bad)).status_code == 422

    # The risk view uses the limits.
    await put({"risk_limits": {"stock_pct": 20, "sector_pct": 35}})
    risk = (await client.get("/api/portfolio/risk")).json()
    assert risk["stock_limit_pct"] == 20.0 and risk["sector_limit_pct"] == 35.0


@pytest.mark.parametrize(("start", "end", "now", "quiet"), [
    ("22:00", "07:00", "23:15", True),   # across midnight: evening
    ("22:00", "07:00", "06:59", True),   # ... and early morning
    ("22:00", "07:00", "07:00", False),  # the end is no longer quiet
    ("22:00", "07:00", "12:00", False),
    ("12:00", "13:00", "12:30", True),   # within one day
    ("12:00", "13:00", "13:30", False),
    ("09:00", "09:00", "09:00", False),  # start = end: never quiet
])
def test_in_quiet_hours(start, end, now, quiet):
    h, m = map(int, now.split(":"))
    assert in_quiet_hours(QuietHours(start=start, end=end), time(h, m)) is quiet
    assert in_quiet_hours(None, time(h, m)) is False


# --- alert emails --------------------------------------------------------------
async def _price_alert(user_id: int) -> None:
    async with AsyncSessionLocal() as s:
        await add_daily_bars(s, [
            {"ticker": "BBCA", "day": date(2026, 10, d),
             "open": 100.0, "high": 100.0, "low": 100.0, "close": c, "volume": 1}
            for d, c in ((15, 5000.0), (16, 5175.0))
        ])
        s.add(Alert(user_id=user_id, ticker="BBCA", type="price_above", threshold=5100.0))
        await s.commit()


async def test_alert_emails_are_opt_in(client, outbox):
    from alerts.service import evaluate_alerts

    await _price_alert(client.user_id)
    assert await evaluate_alerts() == 1
    assert outbox == []  # off by default: the Alerts page only
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(AlertEvent.email_pending))).scalar_one() is False


async def test_alert_email_sent_and_held_in_quiet_hours(client, outbox):
    from alerts.service import evaluate_alerts

    # Quiet from an hour ago to an hour from now (Jakarta time).
    local = datetime.now(ZoneInfo(settings.timezone))
    quiet = {"start": (local - timedelta(hours=1)).strftime("%H:%M"),
             "end": (local + timedelta(hours=1)).strftime("%H:%M")}
    await client.put("/api/preferences", json={"alert_emails": True, "quiet_hours": quiet})
    await _price_alert(client.user_id)

    assert await evaluate_alerts() == 1
    assert outbox == []  # held: quiet hours
    # After the quiet hours: sent (one email), and only once.
    later = utcnow() + timedelta(hours=2)
    assert await send_alert_emails(later) == 1
    assert await send_alert_emails(later) == 0
    assert len(outbox) == 1
    email = outbox[0]
    assert email.subject == "BBCA price 5175 ≥ 5100"
    assert email.to == ("admin@example.com",) and "/alerts" in email.text


async def test_old_or_unwanted_alert_emails_are_dropped(client, outbox):
    from alerts.service import evaluate_alerts

    await client.put("/api/preferences", json={
        "alert_emails": True, "quiet_hours": {"start": "00:00", "end": "23:59"}})
    await _price_alert(client.user_id)
    assert await evaluate_alerts() == 1
    # A day and more later the price move is old news: dropped, not emailed.
    assert await send_alert_emails(utcnow() + timedelta(hours=25)) == 0
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(AlertEvent.email_pending))).scalar_one() is False
    assert outbox == []


# --- profile -------------------------------------------------------------------
async def test_change_name(client):
    r = await client.put("/api/account/name", json={"name": "  Atank   Guni "})
    assert r.status_code == 200 and r.json()["name"] == "Atank Guni"
    assert (await client.put("/api/account/name", json={"name": "   "})).status_code == 400
    assert "name_changed" in await _kinds(client.user_id)
    me = (await client.get("/api/auth/me")).json()
    assert me["name"] == "Atank Guni" and me["created_at"]


async def test_email_change_needs_email_set_up(client, monkeypatch):
    monkeypatch.setattr(mail, "configured", lambda: False)
    r = await client.post("/api/account/email-change",
                          json={"new_email": "new@example.com", "password": PASSWORD})
    assert r.status_code == 409


async def test_email_change_by_link(client, anon, outbox):
    ask = lambda email, pw=PASSWORD: client.post(  # noqa: E731
        "/api/account/email-change", json={"new_email": email, "password": pw})
    await make_user("taken@example.com")
    assert (await ask("new@example.com", "wrong")).status_code == 400
    assert (await ask("taken@example.com")).status_code == 400
    assert (await ask("Name <x@example.com>")).status_code == 400
    assert (await ask("admin@example.com")).status_code == 400  # the same address
    assert outbox == []

    r = await ask("  New@Example.com ")
    assert r.status_code == 202 and r.json() == {"new_email": "new@example.com"}
    confirm, notice = outbox
    assert confirm.to == ("new@example.com",) and notice.to == ("admin@example.com",)
    token = confirm.text.split("/confirm-email/")[1].split()[0]
    pending = (await client.get("/api/account/email-change")).json()
    assert pending == {"new_email": "new@example.com"}
    # Nothing changes until the link is opened.
    assert (await client.get("/api/auth/me")).json()["email"] == "admin@example.com"

    # The link works signed out (another device).
    assert (await anon.get(f"/api/account/email-change/{token}")).json() == {
        "new_email": "new@example.com"}
    r = await anon.post(f"/api/account/email-change/{token}")
    assert r.status_code == 200
    assert (await client.get("/api/auth/me")).json()["email"] == "new@example.com"
    assert outbox[-1].to == ("admin@example.com",)  # the old address is told
    assert (await anon.post(f"/api/account/email-change/{token}")).status_code == 400
    assert (await client.get("/api/account/email-change")).json() is None
    kinds = await _kinds(client.user_id)
    assert "email_change_requested" in kinds and "email_changed" in kinds


async def test_cancel_email_change(client, outbox):
    await client.post("/api/account/email-change",
                      json={"new_email": "new@example.com", "password": PASSWORD})
    token = outbox[0].text.split("/confirm-email/")[1].split()[0]
    assert (await client.delete("/api/account/email-change")).status_code == 204
    assert (await client.post(f"/api/account/email-change/{token}")).status_code == 400


# --- your data -----------------------------------------------------------------
async def test_clear_portfolio_keeps_watchlist(client):
    tx = {"ticker": "BBCA", "side": "buy", "quantity": 100, "price": 1000.0, "fees": 0.0,
          "trade_date": "2026-10-01"}
    assert (await client.post("/api/portfolio/transactions", json=tx)).status_code == 201
    async with AsyncSessionLocal() as s:
        s.add(Watchlist(user_id=client.user_id, ticker="TLKM"))
        await s.commit()

    r = await client.post("/api/account/clear-portfolio", json={"password": "wrong"})
    assert r.status_code == 400
    assert len((await client.get("/api/portfolio/transactions")).json()) == 1

    r = await client.post("/api/account/clear-portfolio", json={"password": PASSWORD})
    assert r.status_code == 204
    assert (await client.get("/api/portfolio/transactions")).json() == []
    assert [w["ticker"] for w in (await client.get("/api/watchlist")).json()] == ["TLKM"]
    assert "portfolio_cleared" in await _kinds(client.user_id)


async def test_delete_account(client):
    # The only admin can't leave (nobody could run the app).
    r = await client.post("/api/account/delete", json={"password": PASSWORD, "confirm": "DELETE"})
    assert r.status_code == 400 and "only admin" in r.json()["detail"]

    await make_user("bob@example.com")
    async with await signed_in("bob@example.com") as bob:
        bad = await bob.post("/api/account/delete", json={"password": PASSWORD, "confirm": "yes"})
        assert bad.status_code == 422  # must type DELETE
        wrong = await bob.post("/api/account/delete",
                               json={"password": "wrong", "confirm": "DELETE"})
        assert wrong.status_code == 400
        r = await bob.post("/api/account/delete", json={"password": PASSWORD, "confirm": "DELETE"})
        assert r.status_code == 204
        assert settings.session_cookie_name in r.headers.get("set-cookie", "")
        assert (await bob.get("/api/auth/me")).status_code == 401

    users = (await client.get("/api/admin/users")).json()
    assert [u["email"] for u in users] == ["admin@example.com"]
