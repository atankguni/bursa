"""Dividend reminders (estimated cum dates) and the daily summary email."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

import mail
import routers.alerts as alerts_router
from config import settings
from database import AsyncSessionLocal
from models import AlertEvent, Dividend, RatingSnapshot, User, Watchlist
from services import digest
from services.alerts import dividend_due, evaluate_alerts
from services.dividend_calendar import UpcomingDividend, cum_date
from services.market_clock import is_trading_day
from tests.conftest import add_daily_bars


def test_cum_date_is_the_trading_day_before_the_ex_date():
    assert cum_date(date(2026, 3, 9)) == date(2026, 3, 6)   # Monday ex -> Friday cum
    assert cum_date(date(2026, 3, 11)) == date(2026, 3, 10)


def test_dividend_due_window():
    up = UpcomingDividend(cum_date=date(2026, 3, 6), expected_ex_date=date(2026, 3, 9),
                          amount_per_share=100.0, regular=True)
    assert dividend_due(up, date(2026, 3, 3), None) == 3      # default: 3 days ahead
    assert dividend_due(up, date(2026, 3, 2), None) is None   # too early
    assert dividend_due(up, date(2026, 3, 2), 7) == 4
    assert dividend_due(up, date(2026, 3, 7), 7) is None      # cum date has passed
    assert dividend_due(None, date(2026, 3, 3), 7) is None


async def test_dividend_alert_fires_once_with_the_estimate(client, monkeypatch):
    fetched: list[str] = []

    async def fake_sync(ticker):
        fetched.append(ticker)
        return 0

    monkeypatch.setattr(alerts_router, "sync_dividends", fake_sync)
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    ex = today + timedelta(days=3)
    while not is_trading_day(ex):
        ex += timedelta(days=1)

    r = await client.post("/api/alerts", json={"ticker": "BBRI", "type": "dividend_soon",
                                               "threshold": 10})
    assert r.status_code == 201 and fetched == ["BBRI"]  # history fetched once
    bad = await client.post("/api/alerts", json={"ticker": "BBRI",
                                                 "type": "dividend_soon", "threshold": 99})
    assert bad.status_code == 400

    async with AsyncSessionLocal() as s:
        s.add(Dividend(ticker="BBRI", ex_date=ex.replace(year=ex.year - 1), amount=208.0))
        await s.commit()
    assert await evaluate_alerts() == 1
    assert await evaluate_alerts() == 0  # once per expected dividend
    async with AsyncSessionLocal() as s:
        event = (await s.execute(select(AlertEvent))).scalar_one()
    assert "BBRI dividend expected" in event.message
    assert f"{cum_date(ex):%a %d %b}" in event.message and "Rp 208/share" in event.message


async def test_digest_content_and_preview(client, monkeypatch):
    day = date(2026, 3, 10)  # a Tuesday
    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.id == client.user_id))).scalar_one()
        assert await digest.build_digest(s, user, day) is None  # follows nothing yet
        s.add(Watchlist(user_id=client.user_id, ticker="BBCA"))
        await add_daily_bars(s, [
            {"ticker": "BBCA", "day": date(2026, 3, d),
             "open": c, "high": c, "low": c, "close": c, "volume": 0}
            for d, c in ((9, 1000.0), (10, 1050.0))
        ])
        s.add_all([
            RatingSnapshot(day=date(2026, 3, 9), style="investor", ticker="BBCA",
                           rating="Hold", score=50, liquid=True),
            RatingSnapshot(day=day, style="investor", ticker="BBCA",
                           rating="Buy", score=66, liquid=True),
        ])
        await s.commit()
        d = await digest.build_digest(s, user, day)

    assert d is not None and d.totals is None  # watchlist only: no portfolio section
    text = digest.render(d, "Ana").text
    assert "BBCA +5.00%" in text
    assert "BBCA: Neutral → Positive" in text
    assert digest.subject(d) == "Bursa · Tue 10 Mar: 1 signal change"

    # Preview: refused without email, sent with it.
    monkeypatch.setattr(mail, "configured", lambda: False)
    assert (await client.post("/api/preferences/digest/preview")).status_code == 409
    sent = []

    async def fake_send(email):
        sent.append(email)
        return True

    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "send_quietly", fake_send)
    assert (await client.post("/api/preferences/digest/preview")).status_code == 202
    assert sent and sent[0].to == ("admin@example.com",)

    p = (await client.put("/api/preferences", json={"daily_digest": True})).json()
    assert p["daily_digest"] is True
