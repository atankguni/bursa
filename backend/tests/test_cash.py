"""Cash in the trading account (RDN): balance, settling sales, return on deposits."""

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from portfolio.cash import balance, money_weighted_return
from tests.conftest import add_daily_bars


@dataclass
class M:
    kind: str
    amount: float
    day: date


@dataclass
class T:
    side: str
    quantity: float
    price: float
    fees: float
    trade_date: date


def plus_two(d: date) -> date:  # settlement without the holiday calendar
    return d + timedelta(days=2)


def test_balance_follows_deposits_trades_and_settlement():
    moves = [
        M("deposit", 10_000_000, date(2026, 1, 2)),
        M("withdrawal", 1_000_000, date(2026, 4, 1)),
        M("deposit", 5_000_000, date(2026, 7, 1)),  # after "today": not counted yet
    ]
    trades = [
        T("buy", 1000, 5000.0, 7_565.0, date(2026, 1, 5)),
        T("sell", 500, 6000.0, 7_539.0, date(2026, 6, 10)),  # settles on the 12th
        T("buy", 100, 0.0, 0.0, date(2026, 6, 1)),  # bonus shares: free
    ]
    b = balance(moves, trades, dividends_net=50_000, today=date(2026, 6, 11), settle=plus_two)
    assert b.net_deposits == 9_000_000
    assert b.available == 9_000_000 - 5_007_565 + 50_000
    assert (b.settling, b.settles_on) == (2_992_461, date(2026, 6, 12))

    settled = balance(moves, trades, 50_000, today=date(2026, 6, 12), settle=plus_two)
    assert settled.settling == 0 and settled.available == b.available + 2_992_461


def test_money_weighted_return():
    t0 = date(2024, 1, 1)
    one_year = money_weighted_return([(t0, -100), (date(2025, 1, 1), 110)], date(2025, 1, 1))
    assert one_year == pytest.approx(0.10, abs=0.002)
    # 100 in, another 100 a year later, 231 out after two years: 10% a year.
    two = money_weighted_return(
        [(t0, -100), (date(2025, 1, 1), -100), (date(2026, 1, 1), 231)], date(2026, 1, 1)
    )
    assert two == pytest.approx(0.10, abs=0.002)
    assert money_weighted_return([(t0, -100)], t0) is None  # nothing came back


async def test_cash_endpoints(client):
    from clock import local_today
    from database import AsyncSessionLocal

    today = local_today()

    async with AsyncSessionLocal() as s:
        await add_daily_bars(s, [{"ticker": "BBCA", "day": today, "open": 1000.0,
                                   "high": 1000.0, "low": 1000.0, "close": 1200.0,
                                   "volume": 0}])
        await s.commit()

    empty = (await client.get("/api/portfolio/cash")).json()
    assert empty["tracked"] is False and empty["balance"] == 0

    dep = await client.post("/api/portfolio/cash", json={
        "kind": "deposit", "amount": 2_000_000, "day": (today - timedelta(days=30)).isoformat()})
    assert dep.status_code == 201
    await client.post("/api/portfolio/transactions", json={
        "ticker": "BBCA", "side": "buy", "quantity": 1000, "price": 1000.0, "fees": 1_500.0,
        "trade_date": (today - timedelta(days=20)).isoformat()})

    c = (await client.get("/api/portfolio/cash")).json()
    assert c["tracked"] and c["available"] == 2_000_000 - 1_001_500
    assert c["market_value"] == 1_200_000
    assert c["account_value"] == 1_200_000 + 998_500
    assert c["gain"] == c["account_value"] - 2_000_000
    assert c["annual_return_pct"] is None  # less than a year of history

    future = await client.post("/api/portfolio/cash", json={
        "kind": "deposit", "amount": 1, "day": (today + timedelta(days=1)).isoformat()})
    assert future.status_code == 400
    bad = await client.post("/api/portfolio/cash", json={
        "kind": "deposit", "amount": -5, "day": today.isoformat()})
    assert bad.status_code == 422

    mid = dep.json()["id"]
    assert (await client.delete(f"/api/portfolio/cash/{mid}")).status_code == 204
    assert (await client.delete(f"/api/portfolio/cash/{mid}")).status_code == 404
