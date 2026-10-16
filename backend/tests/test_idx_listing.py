"""IDX listing sync (boards / special monitoring / IPOs) and its effects."""

from datetime import date

import services.idx_listing as idx_listing
from config import settings


def _rows(n_extra: int = 0, board_bbca: str = "Main"):
    rows = [
        {"ticker": "BBCA.JK", "name": "Bank Central Asia", "board": board_bbca,
         "listed_on": date(2000, 5, 31), "shares": 1.23e11},
        {"ticker": "NEWIPO.JK", "name": "Fresh Listing Tbk", "board": "Acceleration",
         "listed_on": date(2026, 10, 1), "shares": 1e9},
    ]
    rows += [{"ticker": f"X{i:04d}.JK", "name": f"Filler {i}", "board": "Development",
              "listed_on": None, "shares": None} for i in range(n_extra)]
    return rows


async def test_sync_applies_boards_and_adds_ipos(client, monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    monkeypatch.setattr(idx_listing, "fetch_listing", lambda: _rows(600, "Watchlist"))
    assert await idx_listing.sync_listing() == 602
    assert not await idx_listing.is_stale()

    bbca = (await client.get("/api/stocks/BBCA.JK")).json()
    assert bbca["board"] == "Watchlist"
    ipo = (await client.get("/api/stocks/NEWIPO.JK")).json()  # auto-added to the catalog
    assert ipo["name"] == "Fresh Listing Tbk" and ipo["board"] == "Acceleration"
    page = (await client.get("/api/screener", params={"limit": 200})).json()
    assert any(r["ticker"] == "BBCA.JK" and r["board"] == "Watchlist" for r in page["items"])


async def test_partial_listing_is_not_applied(client, monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    monkeypatch.setattr(idx_listing, "fetch_listing", lambda: _rows(10))  # blocked/partial
    assert await idx_listing.sync_listing() == 0
    assert (await client.get("/api/stocks/NEWIPO.JK")).status_code == 404


async def test_fetch_failure_is_swallowed(client, monkeypatch):
    def boom():
        raise RuntimeError("cloudflare says no")

    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    monkeypatch.setattr(idx_listing, "fetch_listing", boom)
    assert await idx_listing.sync_listing() == 0


def test_special_monitoring_caps_buy_at_hold():
    from services.recommendation import score_universe

    keys = ["roe", "net_margin", "pbv", "per", "revenue_yoy", "earnings_yoy",
            "ret_3m", "price_vs_sma50", "pos_52w", "der", "equity_ratio"]

    def raw(**kw):
        return {k: kw.get(k) for k in keys}

    good = {"roe": 0.3, "net_margin": 0.3, "pbv": 0.8, "per": 6, "revenue_yoy": 0.2}
    bad = {"roe": 0.01, "net_margin": 0.01, "pbv": 5.0, "per": 40, "revenue_yoy": -0.2}
    universe = {"OK.JK": raw(**good), "PPK.JK": raw(**good), "BAD.JK": raw(**bad)}
    rec = score_universe(universe, special_monitoring={"PPK.JK"})
    assert rec["OK.JK"].rating in ("Buy", "Strong Buy")
    assert rec["PPK.JK"].rating == "Hold"
    assert any("special monitoring" in r for r in rec["PPK.JK"].reasons)
