"""Smoke tests for the HTTP API (no network, in-process ASGI)."""

from clock import local_today

EXPECTED_STOCK_KEYS = {
    "ticker",
    "name",
    "indices",
    "last_price",
    "previous_close",
    "change",
    "change_percent",
    "volume",
    "updated_at",
}


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_indexes(client):
    r = await client.get("/api/indexes")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert "LQ45" in body


async def test_stocks_shape(client):
    r = await client.get("/api/stocks")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and body
    assert EXPECTED_STOCK_KEYS <= set(body[0])


async def test_stocks_index_filter_is_intersection(client):
    both = (await client.get("/api/stocks", params=[("index", "LQ45"), ("index", "IDX30")])).json()
    lq45 = (await client.get("/api/stocks", params={"index": "LQ45"})).json()
    # Intersection of LQ45 and IDX30 must not exceed LQ45 alone.
    assert len(both) <= len(lq45)


async def test_unknown_ticker_history_404(client):
    r = await client.get("/api/stocks/NOPE/history")
    assert r.status_code == 404


async def test_watchlist_empty(client):
    r = await client.get("/api/watchlist")
    assert r.status_code == 200
    assert r.json() == []


async def test_add_unknown_ticker_404(client):
    r = await client.post("/api/watchlist/NOPE")
    assert r.status_code == 404


async def test_get_single_stock(client):
    r = await client.get("/api/stocks/BBCA")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "BBCA"
    assert "last_price" in body and "indices" in body


async def test_get_unknown_stock_404(client):
    r = await client.get("/api/stocks/NOPE")
    assert r.status_code == 404


async def test_status(client):
    r = await client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "server_time",
        "timezone",
        "session",
        "last_sync",
        "stocks_tracked",
        "providers",
        "calls_today",
        "lot_size",
    ):
        assert key in body
    assert body["stocks_tracked"] > 0
    assert body["lot_size"] == 100


async def test_catalog_paginates_whole_universe(client):
    first = (await client.get("/api/catalog", params={"limit": 200})).json()
    total = first["total"]
    assert total > 200  # the full IDX listing, not just one page
    assert len(first["items"]) == 200

    # Walking every page yields each stock exactly once, in ticker order.
    seen: list[str] = []
    for offset in range(0, total, 200):
        page = (await client.get("/api/catalog", params={"limit": 200, "offset": offset})).json()
        assert page["total"] == total and page["offset"] == offset
        seen += [r["ticker"] for r in page["items"]]
    assert len(seen) == total == len(set(seen))
    assert seen == sorted(seen)


async def test_catalog_total_respects_search(client):
    page = (await client.get("/api/catalog", params={"q": "BBCA"})).json()
    assert page["total"] == len(page["items"]) >= 1
    assert all("BBCA" in r["ticker"] or "bbca" in r["name"].lower() for r in page["items"])


async def test_preferences_default_and_switch(client):
    r = await client.get("/api/preferences")
    assert r.status_code == 200 and r.json()["investing_style"] == "investor"

    r = await client.put("/api/preferences", json={"investing_style": "trader"})
    assert r.status_code == 200 and r.json()["investing_style"] == "trader"
    assert (await client.get("/api/preferences")).json()["investing_style"] == "trader"

    bad = await client.put("/api/preferences", json={"investing_style": "gambler"})
    assert bad.status_code == 422


async def test_switching_style_resets_rating_alert_baselines(client):
    from sqlalchemy import func, select

    from alerts.models import RatingState
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        s.add(RatingState(user_id=client.user_id, ticker="BBCA", rating="Buy",
                          strength="Strong"))
        await s.commit()

    await client.put("/api/preferences", json={"investing_style": "trader"})
    async with AsyncSessionLocal() as s:
        left = (await s.execute(select(func.count()).select_from(RatingState))).scalar_one()
    assert left == 0  # no spurious "rating changed" alerts after a style switch


async def test_screener_paginates_whole_universe(client):
    first = (await client.get("/api/screener", params={"limit": 200})).json()
    total = first["total"]
    assert total > 200 and len(first["items"]) == 200

    seen: list[str] = []
    for offset in range(0, total, 200):
        page = (await client.get("/api/screener", params={"limit": 200, "offset": offset})).json()
        assert page["total"] == total and page["offset"] == offset
        seen += [r["ticker"] for r in page["items"]]
    assert len(seen) == total == len(set(seen))  # every stock exactly once


async def test_screener_total_counts_filtered_matches(client):
    page = (await client.get("/api/screener", params={"buy_only": True})).json()
    assert page["total"] == len(page["items"])  # no data in tests -> nothing is a Buy


async def _insert_daily_bars(ticker: str, days: int) -> None:
    from datetime import timedelta

    from database import AsyncSessionLocal
    from db.upsert import upsert
    from market.models import DailyBar

    today = local_today()
    rows = [
        {"ticker": ticker, "day": today - timedelta(days=d),
         "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0 + d, "volume": 1000}
        for d in range(days)
    ]
    async with AsyncSessionLocal() as s:
        await upsert(s, DailyBar, rows, keys=["ticker", "day"], update=[])
        await s.commit()


async def test_history_ranges_fetch_full_history_once(client, monkeypatch):
    import market.history as history

    await _insert_daily_bars("BBCA", 400)  # ~1y+ like the regular sync stores
    calls: list[tuple] = []

    async def fake_sync(tickers, period, interval):
        calls.append((tuple(tickers), period, interval))
        await _insert_daily_bars("BBCA", 3000)  # "since listing"
        return 3000

    monkeypatch.setattr(history, "sync_batch", fake_sync)

    short = (await client.get("/api/stocks/BBCA/history", params={"range": "1m"})).json()
    assert 28 <= len(short["points"]) <= 32 and calls == []  # stored data, no provider call
    pts = [p["timestamp"] for p in short["points"]]
    assert pts == sorted(pts)  # ascending for the chart

    full = (await client.get("/api/stocks/BBCA/history", params={"range": "max"})).json()
    assert len(full["points"]) == 3000
    assert calls == [(("BBCA",), "max", "1d")]

    five = (await client.get("/api/stocks/BBCA/history", params={"range": "5y"})).json()
    assert 1820 <= len(five["points"]) <= 1832
    assert len(calls) == 1  # full history is fetched once, then kept


async def test_history_range_is_validated(client):
    r = await client.get("/api/stocks/BBCA/history", params={"range": "10y"})
    assert r.status_code == 422


async def test_assistant_personal_data_is_opt_in_and_partial_updates(client):
    p = (await client.get("/api/preferences")).json()
    assert p == {"investing_style": "investor", "assistant_personal_data": False,
                 "assistant_save_chats": True, "display": None, "alerts_seen_at": None,
                 "trading_costs": {"buy_fee_pct": 0.15, "sell_fee_pct": 0.25,
                                   "dividend_tax_pct": 10.0},
                 "daily_digest": False, "lock_minutes": 15}
    assert (await client.get("/api/assistant/status")).json()["personal_data"] is False

    p = (await client.put("/api/preferences", json={"assistant_personal_data": True})).json()
    assert p["investing_style"] == "investor" and p["assistant_personal_data"] is True
    p = (await client.put("/api/preferences", json={"investing_style": "trader"})).json()
    assert p["assistant_personal_data"] is True  # not reset by an unrelated update
    assert (await client.get("/api/assistant/status")).json()["personal_data"] is True


async def test_display_settings_are_saved_per_user(client):
    from tests.conftest import make_user, signed_in

    display = {"defaultIndexes": ["LQ45", "IDX30"], "chartType": "line", "chartRange": "1m",
               "autoRefresh": False, "refreshSeconds": 120, "numberFormat": "full",
               "colorizeChanges": False,
               "hiddenColumns": {"home": ["volume"], "watchlist": ["pbv", "roe"]}}
    p = (await client.put("/api/preferences", json={"display": display})).json()
    assert p["display"] == display  # camelCase on the wire, like the frontend
    assert (await client.get("/api/preferences")).json()["display"] == display

    # Long lists fit (the value column holds more than 255 characters).
    many = [f"INDEX{i:02d}" for i in range(40)]
    r = await client.put("/api/preferences", json={"display": {**display, "defaultIndexes": many}})
    assert r.json()["display"]["defaultIndexes"] == many

    bad = await client.put("/api/preferences", json={"display": {"refreshSeconds": 1}})
    assert bad.status_code == 422

    await make_user("bob@example.com")
    async with await signed_in("bob@example.com") as bob:
        assert (await bob.get("/api/preferences")).json()["display"] is None


async def test_alerts_seen_marker_only_moves_forward(client):
    put = lambda t: client.put("/api/preferences", json={"alerts_seen_at": t})  # noqa: E731
    # A time without an offset (an old client) is taken as UTC; replies always carry "Z".
    assert (await put("2026-10-17T10:00:00")).json()["alerts_seen_at"] == "2026-10-17T10:00:00Z"
    # An older device can't mark alerts unread again.
    assert (await put("2026-10-16T09:00:00Z")).json()["alerts_seen_at"] == "2026-10-17T10:00:00Z"
    # Offsets are converted to UTC (how event times are stored).
    p = (await put("2026-10-17T19:00:00+07:00")).json()
    assert p["alerts_seen_at"] == "2026-10-17T12:00:00Z"
