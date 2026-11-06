"""Adding to the watchlist answers at once; fundamentals come in the background."""

import portfolio.routes.watchlist as watchlist_routes
from clock import utcnow
from database import AsyncSessionLocal
from market.models import Fundamental


async def _fresh_fundamentals(ticker: str) -> None:
    async with AsyncSessionLocal() as s:
        s.add(Fundamental(ticker=ticker, fiscal_year=2025, financial_currency="IDR",
                          source="statements", updated_at=utcnow()))
        await s.commit()


async def test_fresh_fundamentals_are_not_fetched_again(client, monkeypatch):
    calls: list[str] = []

    async def fake_sync(ticker: str) -> int:
        calls.append(ticker)
        return 0

    monkeypatch.setattr(watchlist_routes, "sync_ticker", fake_sync)
    await _fresh_fundamentals("BBCA")
    r = await client.post("/api/watchlist/BBCA")
    assert r.status_code == 201 and r.json()["syncing"] is False
    assert calls == []


async def test_missing_fundamentals_are_fetched_after_the_response(client, monkeypatch):
    calls: list[str] = []

    async def fake_sync(ticker: str) -> int:
        calls.append(ticker)
        return 1

    monkeypatch.setattr(watchlist_routes, "sync_ticker", fake_sync)
    r = await client.post("/api/watchlist/TLKM")
    assert r.status_code == 201
    assert r.json()["ticker"] == "TLKM" and r.json()["syncing"] is True
    assert calls == ["TLKM"]  # the test client waits for background tasks


async def test_a_failed_fetch_keeps_the_stock_on_the_watchlist(client, monkeypatch):
    async def broken_sync(ticker: str) -> int:
        raise RuntimeError("provider down")

    monkeypatch.setattr(watchlist_routes, "sync_ticker", broken_sync)
    assert (await client.post("/api/watchlist/BMRI")).status_code == 201
    tickers = [w["ticker"] for w in (await client.get("/api/watchlist")).json()]
    assert "BMRI" in tickers
