"""Stock splits: transaction adjustment, portfolio, sell validation, history reset."""

from datetime import UTC, date, datetime

import services.corporate_actions as ca
from config import settings
from database import AsyncSessionLocal
from models import Split, Transaction
from services import sync_state
from tests.conftest import add_daily_bars


def test_split_factor_only_counts_splits_after_the_trade():
    splits = [(date(2008, 1, 28), 2.0), (date(2021, 10, 13), 5.0)]
    assert ca.split_factor(splits, date(2007, 1, 1), today=date(2026, 1, 1)) == 10.0
    assert ca.split_factor(splits, date(2015, 1, 1), today=date(2026, 1, 1)) == 5.0
    assert ca.split_factor(splits, date(2022, 1, 1), today=date(2026, 1, 1)) == 1.0
    # A split announced for the future isn't applied yet.
    future = [(date(2030, 1, 1), 2.0)]
    assert ca.split_factor(future, date(2025, 1, 1), today=date(2026, 1, 1)) == 1.0


async def _setup_bbca_split(user_id: int):
    async with AsyncSessionLocal() as s:
        s.add(Split(ticker="BBCA", ex_date=date(2021, 10, 13), ratio=5.0))
        # Bought 100 shares at 5,000 before the 5:1 split.
        s.add(Transaction(user_id=user_id, ticker="BBCA", side="buy", quantity=100, price=5000.0,
                          fees=0.0, trade_date=date(2021, 1, 4)))
        await add_daily_bars(s, [
            {"ticker": "BBCA", "day": date(2026, 1, d),
             "open": 1000.0, "high": 1000.0, "low": 1000.0, "close": 1000.0, "volume": 0}
            for d in (5, 6)
        ])
        await s.commit()


async def test_portfolio_is_split_adjusted(client):
    await _setup_bbca_split(client.user_id)
    pf = (await client.get("/api/portfolio")).json()
    h = pf["holdings"][0]
    # 100 @ 5,000 became 500 @ 1,000: same capital, no fake -80% loss.
    assert h["quantity"] == 500 and h["avg_cost"] == 1000.0
    assert h["unrealized_pl"] == 0.0 and h["split_adjusted"] is True
    assert pf["totals"]["invested"] == 500_000.0


async def test_sell_validation_uses_post_split_shares(client):
    await _setup_bbca_split(client.user_id)
    sell = {"ticker": "BBCA", "side": "sell", "price": 1100.0, "fees": 0.0,
            "trade_date": "2026-01-06"}
    assert (await client.post("/api/portfolio/transactions",
                              json=sell | {"quantity": 501})).status_code == 400
    assert (await client.post("/api/portfolio/transactions",
                              json=sell | {"quantity": 500})).status_code == 201


async def test_new_split_resets_stored_full_history(client, monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)

    class _P:
        name = "fake"

        def fetch_splits(self, ticker):
            return [{"ex_date": date(2004, 1, 1), "ratio": 2.0},   # long ago
                    {"ex_date": date(2026, 3, 2), "ratio": 5.0}]   # after history stored

    monkeypatch.setattr(ca, "price_provider", lambda: _P())
    async with AsyncSessionLocal() as s:
        await sync_state.mark_done(s, "full_history", ["BBCA"],
                                   at=datetime(2026, 1, 15, tzinfo=UTC))
        await s.commit()

    assert await ca.sync_splits(["BBCA"]) == 2
    async with AsyncSessionLocal() as s:
        # re-fetched on next 5Y/Max view
        assert await sync_state.done_at(s, "full_history", "BBCA") is None
        assert await sync_state.done_at(s, "splits", "BBCA") is not None

    h = (await client.get("/api/stocks/BBCA/history", params={"interval": "1d"})).json()
    assert [(x["ex_date"], x["ratio"]) for x in h["splits"]] == [("2004-01-01", 2.0),
                                                                 ("2026-03-02", 5.0)]
