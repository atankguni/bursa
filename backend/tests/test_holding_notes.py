"""Holding notes: thesis, target / stop, review date, and reminders in the daily email."""

from datetime import date, timedelta

from sqlalchemy import select

from accounts.models import User
from alerts import digest
from clock import local_today
from database import AsyncSessionLocal
from portfolio.notes import note_flags
from tests.conftest import add_daily_bars

DAY = date(2026, 3, 10)


def test_note_flags():
    assert note_flags(None, None, None, 1000.0, DAY) == []
    assert note_flags(1200.0, 900.0, DAY, 1000.0, DAY) == ["review_due"]
    assert note_flags(1000.0, None, DAY + timedelta(days=1), 1000.0, DAY) == ["target_reached"]
    assert note_flags(None, 1000.0, None, 990.0, DAY) == ["stop_hit"]
    assert note_flags(1000.0, 500.0, None, None, DAY) == []  # no price yet


async def bars(close: float, day: date) -> None:
    async with AsyncSessionLocal() as s:
        await add_daily_bars(s, [{"ticker": "BBCA", "day": day, "open": close, "high": close,
                                  "low": close, "close": close, "volume": 0}])
        await s.commit()


async def test_notes_endpoints(client):
    today = local_today()
    await bars(1250.0, today)
    url = "/api/portfolio/notes/bbca"  # the code is normalized

    assert (await client.get("/api/portfolio/notes")).json() == []
    r = await client.put(url, json={"thesis": "  Cheap bank  ", "target": 1200, "stop": 900,
                                    "review_on": (today + timedelta(days=90)).isoformat()})
    assert r.status_code == 200
    note = r.json()
    assert (note["ticker"], note["thesis"], note["last_price"]) == ("BBCA", "Cheap bank", 1250)
    assert note["flags"] == ["target_reached"]

    r = await client.put(url, json={"thesis": "", "target": 1500})  # replaces everything
    assert r.json()["thesis"] is None and r.json()["stop"] is None and r.json()["flags"] == []

    assert (await client.put(url, json={"target": 900, "stop": 1000})).status_code == 422
    assert (await client.put("/api/portfolio/notes/ZZZZ", json={})).status_code == 404

    assert len((await client.get("/api/portfolio/notes")).json()) == 1
    assert (await client.delete(url)).status_code == 204
    assert (await client.delete(url)).status_code == 404


async def test_the_daily_email_lists_held_stocks_that_need_a_look(client):
    await bars(1250.0, DAY)
    await client.post("/api/portfolio/transactions", json={
        "ticker": "BBCA", "side": "buy", "quantity": 100, "price": 1000.0,
        "trade_date": "2026-03-02"})
    await client.put("/api/portfolio/notes/BBCA", json={"target": 1200, "review_on": "2026-03-10"})

    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.id == client.user_id))).scalar_one()
        d = await digest.build_digest(s, user, DAY)
    assert d is not None
    text = digest.render(d, "Ana").text
    assert "BBCA: reached your target Rp 1,200, review date 10 Mar (last Rp 1,250)" in text
    assert digest.subject(d).endswith("1 to review")
