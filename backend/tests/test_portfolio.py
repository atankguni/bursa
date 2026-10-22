"""Unit tests for portfolio average-cost math (no DB)."""

from types import SimpleNamespace

from services.portfolio import apply_transactions


def T(side, qty, price, fees=0.0, ticker="X"):
    return SimpleNamespace(
        ticker=ticker, side=side, quantity=qty, price=price, fees=fees
    )


def test_buy_only_tracks_quantity_and_cost():
    books = apply_transactions([T("buy", 100, 1000)])
    b = books["X"]
    assert b["quantity"] == 100
    assert b["cost_basis"] == 100_000
    assert b["realized_pl"] == 0


def test_weighted_average_cost():
    books = apply_transactions([T("buy", 100, 1000), T("buy", 100, 2000)])
    b = books["X"]
    assert b["quantity"] == 200
    assert b["cost_basis"] == 300_000
    assert b["cost_basis"] / b["quantity"] == 1500  # average cost


def test_sell_realizes_profit_and_reduces_basis():
    books = apply_transactions(
        [T("buy", 100, 1000), T("buy", 100, 2000), T("sell", 100, 2500, fees=1000)]
    )
    b = books["X"]
    # proceeds 100*2500 - 1000 fees ; cost 1500*100 -> 99000 realized
    assert b["realized_pl"] == 99_000
    assert b["quantity"] == 100
    assert b["cost_basis"] == 150_000


def test_oversell_clamps_to_held():
    books = apply_transactions([T("buy", 100, 1000), T("sell", 200, 1200)])
    b = books["X"]
    assert b["quantity"] == 0
    assert b["cost_basis"] == 0
    # only the 100 held shares realize: 100*1200 - 100*1000 = 20000
    assert b["realized_pl"] == 20_000


def test_multiple_tickers_are_independent():
    books = apply_transactions(
        [T("buy", 10, 100, ticker="A"), T("buy", 5, 200, ticker="B")]
    )
    assert books["A"]["cost_basis"] == 1000
    assert books["B"]["cost_basis"] == 1000


async def test_time_weighted_return_ignores_added_money(client, monkeypatch):
    """Doubling the position isn't profit: TWR stays at the price gain (+10%)."""
    from datetime import date, datetime

    from sqlalchemy import insert

    import services.indices as indices
    from database import AsyncSessionLocal
    from models import IndexBar, StockPrice, Transaction
    from services.portfolio import equity_curve

    async def no_fetch(session, code):  # IHSG bars are inserted below
        return None

    monkeypatch.setattr(indices, "ensure_full_history", no_fetch)
    closes = {1: 1000.0, 2: 1100.0, 3: 1100.0, 4: 1210.0}
    ihsg = {1: 7000.0, 2: 7070.0, 3: 6930.0, 4: 7140.0}
    uid = client.user_id
    async with AsyncSessionLocal() as s:
        await s.execute(insert(StockPrice).values([
            {"ticker": "BBCA.JK", "timestamp": datetime(2026, 1, d), "interval": "1d",
             "open": c, "high": c, "low": c, "close": c, "volume": 0} for d, c in closes.items()
        ]))
        await s.execute(insert(IndexBar).values([
            {"code": "COMPOSITE", "day": date(2026, 1, d), "close": c} for d, c in ihsg.items()
        ]))
        s.add_all([
            Transaction(user_id=uid, ticker="BBCA.JK", side="buy", quantity=100, price=1000.0,
                        fees=0.0, trade_date=date(2026, 1, 1)),
            # Day 3: add as much money again at 1100 (a deposit, not a gain).
            Transaction(user_id=uid, ticker="BBCA.JK", side="buy", quantity=100, price=1100.0,
                        fees=0.0, trade_date=date(2026, 1, 3)),
        ])
        await s.commit()
        curve = await equity_curve(s, client.user_id)

    by_day = {p["date"].day: p for p in curve}
    assert by_day[2]["return_pct"] == 10.0   # 1000 -> 1100
    assert by_day[3]["value"] == 220_000.0   # value doubled by the deposit...
    assert by_day[3]["return_pct"] == 10.0   # ...but the return didn't
    assert by_day[4]["return_pct"] == 21.0   # then +10% on everything: 1.1 * 1.1
    assert by_day[4]["benchmark_pct"] == 2.0  # IHSG 7000 -> 7140

    r = await client.get("/api/portfolio/history")
    assert r.status_code == 200 and r.json()[-1]["benchmark_pct"] == 2.0


def test_beta_and_drawdown_math():
    from datetime import date, timedelta

    from services.portfolio_risk import beta, max_drawdown

    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(60)]
    market, stock, calm = [], [], []
    m = s = c = 100.0
    for i, d in enumerate(days):
        step = 0.01 if i % 2 else -0.008
        m *= 1 + step
        s *= 1 + 2 * step  # moves twice as much as the market
        c *= 1 + 0.5 * step
        market.append((d, m))
        stock.append((d, s))
        calm.append((d, c))
    assert round(beta(stock, market), 2) == 2.0
    assert round(beta(calm, market), 2) == 0.5
    assert beta(stock[:10], market[:10]) is None  # too little history

    assert max_drawdown([0, 10, -1, 5]) == round((0.99 / 1.10 - 1) * 100, 2)
    assert max_drawdown([]) is None


async def test_risk_endpoint_concentration_and_warnings(client, monkeypatch):
    from datetime import date

    import services.indices as indices
    from database import AsyncSessionLocal
    from models import Transaction

    async def no_fetch(session, code):
        return None

    monkeypatch.setattr(indices, "ensure_full_history", no_fetch)
    uid = client.user_id
    async with AsyncSessionLocal() as s:
        s.add_all([
            Transaction(user_id=uid, ticker="BBCA.JK", side="buy", quantity=900, price=100.0,
                        fees=0.0, trade_date=date(2026, 1, 2)),
            Transaction(user_id=uid, ticker="TLKM.JK", side="buy", quantity=100, price=100.0,
                        fees=0.0, trade_date=date(2026, 1, 2)),
        ])
        await s.commit()
    r = (await client.get("/api/portfolio/risk")).json()
    assert r["top_weight"] == 90.0 and r["top3_weight"] == 100.0
    assert r["effective_holdings"] == round(1 / (0.9**2 + 0.1**2), 1)  # ~1.2 stocks
    assert any("BBCA is 90%" in w for w in r["warnings"])
    assert r["stress_ihsg_pct"] == -10.0


def test_dividend_projection():
    from datetime import date

    from services.dividend_calendar import project

    today = date(2026, 10, 17)
    history = [
        (date(2024, 11, 20), 50.0),   # two years ago (makes Nov "regular")
        (date(2025, 4, 10), 200.0),   # final dividend, already projected & paid
        (date(2025, 11, 21), 55.0),   # interim -> expected 2026-11-21
        (date(2026, 4, 9), 210.0),    # final -> expected 2027-04-09 (April 2025 too: regular)
        (date(2026, 7, 1), 30.0),     # one-off special: no July a year before
    ]
    got = project(history, today, horizon_days=300)
    assert got == [
        (date(2026, 11, 21), date(2025, 11, 21), 55.0, True),
        (date(2027, 4, 9), date(2026, 4, 9), 210.0, True),
        (date(2027, 7, 1), date(2026, 7, 1), 30.0, False),
    ]
    assert project(history, today, horizon_days=30) == []  # nothing in the next month


async def test_dividend_calendar_endpoint(client, monkeypatch):
    from datetime import date, timedelta

    import services.dividend_calendar as cal
    from database import AsyncSessionLocal
    from models import Dividend, Transaction, Watchlist

    async def no_sync(ticker):
        return 0

    monkeypatch.setattr(cal, "sync_dividends", no_sync)
    last_year = date.today() - timedelta(days=340)  # -> expected in ~25 days
    uid = client.user_id
    async with AsyncSessionLocal() as s:
        s.add(Transaction(user_id=uid, ticker="BBCA.JK", side="buy", quantity=1000, price=9000.0,
                          fees=0.0, trade_date=date(2026, 1, 2)))
        s.add(Watchlist(user_id=uid, ticker="TLKM.JK"))
        s.add_all([Dividend(ticker="BBCA.JK", ex_date=last_year, amount=50.0),
                   Dividend(ticker="TLKM.JK", ex_date=last_year, amount=100.0)])
        await s.commit()
    rows = (await client.get("/api/portfolio/dividend-calendar")).json()
    by = {r["ticker"]: r for r in rows}
    assert by["BBCA.JK"]["expected_income"] == 50_000.0 and by["BBCA.JK"]["in_portfolio"]
    assert by["TLKM.JK"]["expected_income"] is None and by["TLKM.JK"]["in_watchlist"]


def test_dividends_need_the_shares_before_the_ex_date():
    from datetime import date

    from services.portfolio import dividend_income

    def tx(side, qty, day):
        return SimpleNamespace(ticker="X", side=side, quantity=qty, trade_date=day)

    txs = [
        tx("buy", 100, date(2026, 1, 5)),
        tx("buy", 100, date(2026, 3, 10)),  # bought ON the ex-date: not entitled
        tx("sell", 200, date(2026, 6, 1)),
    ]
    divs = {"X": [(date(2026, 3, 10), 50.0), (date(2026, 4, 1), 10.0), (date(2026, 7, 1), 99.0)]}
    # 100 x 50 (March) + 200 x 10 (April); nothing after selling out.
    assert dividend_income(txs, divs) == {"X": 7_000.0}


async def test_portfolio_counts_costs_and_dividends(client):
    from datetime import date, datetime

    from sqlalchemy import insert

    from database import AsyncSessionLocal
    from models import Dividend, StockPrice, Transaction

    async with AsyncSessionLocal() as s:
        await s.execute(insert(StockPrice).values([
            {"ticker": "BBCA.JK", "timestamp": datetime(2026, 1, d), "interval": "1d",
             "open": 1000.0, "high": 1000.0, "low": 1000.0, "close": 1100.0, "volume": 0}
            for d in (5, 6)
        ]))
        s.add(Transaction(user_id=client.user_id, ticker="BBCA.JK", side="buy", quantity=1000,
                          price=1000.0, fees=1_500.0, trade_date=date(2025, 1, 2)))
        s.add(Dividend(ticker="BBCA.JK", ex_date=date(2025, 6, 1), amount=100.0))
        await s.commit()

    await client.put("/api/preferences", json={"trading_costs": {
        "buy_fee_pct": 0.15, "sell_fee_pct": 0.3, "dividend_tax_pct": 10}})
    t = (await client.get("/api/portfolio")).json()["totals"]
    assert t["unrealized_pl"] == 1_100_000 - 1_001_500
    assert t["exit_costs"] == 3_300            # 0.3% of 1.1m
    assert t["dividends_received"] == 90_000   # 1000 x 100, less 10% tax
    assert t["total_return"] == 98_500 - 3_300 + 90_000

    prefs = (await client.get("/api/preferences")).json()
    assert prefs["trading_costs"]["sell_fee_pct"] == 0.3
    bad = await client.put("/api/preferences", json={"trading_costs": {"sell_fee_pct": 40}})
    assert bad.status_code == 422
