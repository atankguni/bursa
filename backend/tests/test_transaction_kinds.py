"""Rights issues and bonus shares: recorded as received shares, adjusting the average."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError


def tx(**over):
    base = {"ticker": "BBCA", "side": "buy", "quantity": 1000, "price": 1000.0,
            "fees": 1_000.0, "trade_date": "2026-03-02"}
    return {**base, **over}


async def holding(client, ticker="BBCA"):
    pf = (await client.get("/api/portfolio")).json()
    return next(h for h in pf["holdings"] if h["ticker"] == ticker)


async def test_bonus_shares_lower_the_average_cost(client):
    assert (await client.post("/api/portfolio/transactions", json=tx())).status_code == 201
    r = await client.post("/api/portfolio/transactions", json=tx(
        kind="bonus", quantity=200, price=0, fees=0, trade_date="2026-06-01"))
    assert r.status_code == 201 and r.json()["kind"] == "bonus"

    h = await holding(client)
    assert h["quantity"] == 1200
    assert h["invested"] == 1_001_000  # unchanged: the shares were free
    assert h["avg_cost"] == round(1_001_000 / 1200, 2)


async def test_exercised_rights_blend_in_at_the_exercise_price(client):
    await client.post("/api/portfolio/transactions", json=tx())
    r = await client.post("/api/portfolio/transactions", json=tx(
        kind="rights", quantity=200, price=500.0, fees=0, trade_date="2026-06-01"))
    assert r.status_code == 201

    h = await holding(client)
    assert (h["quantity"], h["invested"]) == (1200, 1_101_000)

    txs = (await client.get("/api/portfolio/transactions")).json()
    assert [t["kind"] for t in txs] == ["rights", "trade"]  # newest first


@pytest.mark.parametrize("bad", [
    {"kind": "bonus", "price": 100.0, "fees": 0},  # bonus shares are free
    {"kind": "bonus", "price": 0, "fees": 10.0},
    {"kind": "rights", "side": "sell"},  # received, never sold this way
    {"kind": "trade", "price": 0},  # a trade has a price
])
async def test_kind_rules_are_checked(client, bad):
    r = await client.post("/api/portfolio/transactions", json=tx(**bad))
    assert r.status_code == 422


async def test_bonus_already_in_the_market_data_as_a_split_is_refused(client):
    from database import AsyncSessionLocal
    from market.models import Split

    async with AsyncSessionLocal() as s:
        s.add(Split(ticker="BBCA", ex_date=date(2026, 6, 10), ratio=1.2))
        await s.commit()
    await client.post("/api/portfolio/transactions", json=tx())

    bonus = tx(kind="bonus", quantity=200, price=0, fees=0)
    url = "/api/portfolio/transactions"
    near = await client.post(url, json={**bonus, "trade_date": "2026-06-01"})
    assert near.status_code == 409 and "split" in near.json()["detail"]
    far = await client.post(url, json={**bonus, "trade_date": "2026-09-01"})
    assert far.status_code == 201


async def test_the_database_enforces_the_kind_rules(client):
    from database import AsyncSessionLocal
    from portfolio.models import Transaction

    async with AsyncSessionLocal() as s:
        s.add(Transaction(user_id=client.user_id, ticker="BBCA", side="buy", kind="bonus",
                          quantity=10, price=5.0, fees=0.0, trade_date=date(2026, 1, 5)))
        with pytest.raises(IntegrityError):
            await s.commit()
