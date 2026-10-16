"""IDX stock indices: catalog, trading-day dating, quote refresh, history, API."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import services.indices as indices
from market.indices import GROUPS, INDICES
from services.market_clock import last_trading_day

WIB = ZoneInfo("Asia/Jakarta")


def test_catalog_is_consistent():
    assert len(INDICES) == 33
    assert len({i.code for i in INDICES}) == len({i.symbol for i in INDICES}) == 33
    assert {i.group for i in INDICES} == set(GROUPS)
    assert sum(i.group == "Sector" for i in INDICES) == 11  # all IDX-IC sectors
    assert {i.code for i in INDICES if i.history} == {"COMPOSITE", "LQ45", "JII"}


def test_last_trading_day():
    fri = datetime(2026, 10, 16, 10, 0, tzinfo=WIB)
    assert last_trading_day(fri) == date(2026, 10, 16)  # during the session
    assert last_trading_day(fri.replace(hour=8)) == date(2026, 10, 15)  # before pre-open
    sat = datetime(2026, 10, 17, 12, tzinfo=WIB)
    mon_early = datetime(2026, 10, 19, 7, tzinfo=WIB)
    assert last_trading_day(sat) == date(2026, 10, 16)
    assert last_trading_day(mon_early) == date(2026, 10, 16)
    # Holidays are skipped too: 2026-08-17 (Mon) is Independence Day.
    assert last_trading_day(datetime(2026, 8, 17, 12, tzinfo=WIB)) == date(2026, 8, 14)


class _Provider:
    name = "fake"

    def __init__(self):
        self.history_calls = 0

    def fetch_index_quotes(self, symbols):
        return [
            {"symbol": "^JKSE", "last": 5185.1, "previous_close": 5863.78,
             "open": 5800.0, "high": 5900.0, "low": 5150.0},
            {"symbol": "IDX30.JK", "last": 283.66, "previous_close": 328.8,
             "open": None, "high": None, "low": None},
            {"symbol": "NOT-AN-INDEX", "last": 1.0, "previous_close": None,
             "open": None, "high": None, "low": None},
        ]

    def fetch_price_rows(self, tickers, period, interval):
        self.history_calls += 1
        rows = [
            {"ticker": tickers[0], "timestamp": datetime(2004, 6, 8 + d), "interval": "1d",
             "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.0 + d, "volume": 10}
            for d in range(3)
        ]
        return {tickers[0]: rows}


async def test_refresh_list_and_history(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    fake = _Provider()
    monkeypatch.setattr(indices, "price_provider", lambda: fake)

    assert await indices.refresh_quotes() == 3
    rows = {r["code"]: r for r in (await client.get("/api/indices")).json()}
    assert len(rows) == 33
    assert rows["COMPOSITE"]["last"] == 5185.1
    assert rows["COMPOSITE"]["change_percent"] == round((5185.1 - 5863.78) / 5863.78 * 100, 2)
    assert rows["IDX30"]["change_percent"] is not None and rows["IDX30"]["has_history"] is False
    assert rows["KOMPAS100"]["last"] is None  # no quote yet -> still listed

    # IHSG: provider history fetched once, then served from storage.
    h = (await client.get("/api/indices/COMPOSITE/history", params={"range": "max"})).json()
    assert h["has_history"] and len(h["points"]) >= 3
    assert h["points"][0]["timestamp"] == "2004-06-08"
    await client.get("/api/indices/COMPOSITE/history", params={"range": "max"})
    assert fake.history_calls == 1

    # IDX30: no provider history -> only the app's own daily close (flat OHLC).
    h30 = (await client.get("/api/indices/idx30/history", params={"range": "max"})).json()
    assert fake.history_calls == 1 and len(h30["points"]) == 1
    p = h30["points"][0]
    assert p["open"] == p["high"] == p["low"] == p["close"] == 283.66


async def test_index_api_validation(client):
    assert (await client.get("/api/indices/NOPE/history")).status_code == 404
    bad = await client.get("/api/indices/LQ45/history", params={"range": "10y"})
    assert bad.status_code == 422
