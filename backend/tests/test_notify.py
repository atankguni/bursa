"""Telegram delivery of alerts: setup, test endpoint, errors, alert -> message."""

from datetime import date

import alerts.notify as notify
from alerts.models import Alert
from config import settings
from database import AsyncSessionLocal
from tests.conftest import add_daily_bars


def _configure(monkeypatch, sent):
    monkeypatch.setattr(settings, "telegram_bot_token", "123:abc")
    monkeypatch.setattr(settings, "telegram_chat_id", "42")
    monkeypatch.setattr(notify, "_send_telegram", lambda text: sent.append(text))


async def test_not_configured(client):
    assert (await client.get("/api/alerts/notifications")).json() == {
        "telegram": False, "delivered": None}
    r = await client.post("/api/alerts/notifications/test")
    assert r.status_code == 400 and "TELEGRAM_BOT_TOKEN" in r.json()["detail"]


async def test_test_message_delivered(client, monkeypatch):
    sent: list[str] = []
    _configure(monkeypatch, sent)
    r = (await client.post("/api/alerts/notifications/test")).json()
    assert r == {"telegram": True, "delivered": True} and "test notification" in sent[0]


async def test_telegram_errors_are_explained(client, monkeypatch):
    _configure(monkeypatch, [])

    def refuse(text):
        raise notify.NotifyError("Telegram HTTP 400: Bad Request: chat not found")

    monkeypatch.setattr(notify, "_send_telegram", refuse)
    r = await client.post("/api/alerts/notifications/test")
    assert r.status_code == 502 and "chat not found" in r.json()["detail"]
    assert await notify.send_quietly("x") is False  # background use never raises


async def test_triggered_alert_is_sent(client, monkeypatch):
    from alerts.service import evaluate_alerts

    sent: list[str] = []
    _configure(monkeypatch, sent)
    async with AsyncSessionLocal() as s:
        await add_daily_bars(s, [
            {"ticker": "BBCA", "day": date(2026, 10, d),
             "open": 100.0, "high": 100.0, "low": 100.0, "close": c, "volume": 1}
            for d, c in ((15, 5000.0), (16, 5175.0))
        ])
        s.add(Alert(user_id=client.user_id, ticker="BBCA", type="price_above",
                    threshold=5100.0))
        await s.commit()

    assert await evaluate_alerts() == 1
    assert sent == ["🔔 Bursa: BBCA price 5175 ≥ 5100"]
    events = (await client.get("/api/alerts/events")).json()
    assert len(events) == 1  # recorded in-app as well
