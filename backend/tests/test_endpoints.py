"""Smoke tests for the HTTP API (no network, in-process ASGI)."""

EXPECTED_STOCK_KEYS = {
    "id",
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
    r = await client.get("/api/stocks/NOPE.JK/history")
    assert r.status_code == 404


async def test_watchlist_empty(client):
    r = await client.get("/api/watchlist")
    assert r.status_code == 200
    assert r.json() == []


async def test_add_unknown_ticker_404(client):
    r = await client.post("/api/watchlist/NOPE.JK")
    assert r.status_code == 404


async def test_get_single_stock(client):
    r = await client.get("/api/stocks/BBCA.JK")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "BBCA.JK"
    assert "last_price" in body and "indices" in body


async def test_get_unknown_stock_404(client):
    r = await client.get("/api/stocks/NOPE.JK")
    assert r.status_code == 404
