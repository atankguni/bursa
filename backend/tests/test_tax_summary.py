"""The yearly tax summary (SPT): holdings on 31 December, sales and dividends."""

from datetime import date

from market.corporate_actions import AdjustedTx
from portfolio.tax import build, summarize
from tests.conftest import add_daily_bars

TODAY = date(2026, 11, 13)
SPLITS = {"X": [(date(2026, 3, 1), 2.0)]}  # 1:2 split after the 2025 year-end


def T(side, raw_qty, raw_price, fees, day, factor=2.0):
    """A trade in today's shares, recorded as `raw_qty` at `raw_price` before the split."""
    return AdjustedTx(
        id=0, ticker="X", side=side, quantity=raw_qty * factor, price=raw_price / factor,
        fees=fees, trade_date=day, split_factor=factor,
    )


def test_year_figures_in_the_shares_of_then():
    txs = [
        T("buy", 1000, 2000.0, 3_000.0, date(2023, 5, 1)),
        T("sell", 400, 2500.0, 2_513.0, date(2025, 6, 2)),
        T("buy", 200, 2200.0, 0.0, date(2025, 8, 1)),
    ]
    # Amounts per today's share: Rp 25 now = Rp 50 per share then.
    divs = {"X": [(date(2024, 7, 1), 20.0), (date(2025, 7, 1), 25.0)]}
    end = date(2025, 12, 31)
    out = build(
        summarize(txs, 2025, end, divs),
        year=2025, end=end, today=TODAY, years=[2026, 2025, 2024, 2023], splits=SPLITS,
        closes={"X": 1200.0}, names={"X": "Example"}, dividend_tax_pct=10,
    )
    assert out.final and out.as_of == end

    (h,) = out.holdings
    assert h.shares == 800  # 1000 - 400 + 200, before the split
    assert h.acquired_year == 2023
    assert h.cost == 1_641_800  # 2,003,000 - 400 x 2,003 average + 440,000
    assert h.close == 2400 and h.market_value == 1_920_000

    (s,) = out.sales
    assert (s.shares, s.proceeds, s.sales_tax, s.fees) == (400, 1_000_000, 1_000, 2_513)
    assert s.realized_pl == 1_000_000 - 2_513 - 400 * 2_003

    (d,) = out.dividends  # the 2024 one is another year's
    assert (d.ex_date, d.shares, d.per_share) == (date(2025, 7, 1), 600, 50)
    assert (d.gross, d.tax, d.net) == (30_000, 3_000, 27_000)
    assert out.totals.dividends_net == 27_000 and out.totals.cost == 1_641_800


def test_a_position_sold_out_and_rebought_is_acquired_again():
    txs = [
        T("buy", 100, 1000.0, 0.0, date(2022, 1, 3), factor=1.0),
        T("sell", 100, 1000.0, 0.0, date(2023, 1, 3), factor=1.0),
        T("buy", 100, 1000.0, 0.0, date(2024, 1, 3), factor=1.0),
    ]
    end = date(2024, 12, 31)
    out = build(
        summarize(txs, 2024, end, {}), year=2024, end=end, today=TODAY, years=[2024],
        splits={}, closes={}, names={}, dividend_tax_pct=10,
    )
    (h,) = out.holdings
    assert h.acquired_year == 2024 and h.close is None and h.market_value is None
    assert out.sales == []  # the 2023 sale is another year's


async def test_tax_summary_endpoint(client, monkeypatch):
    import portfolio.tax as tax
    from database import AsyncSessionLocal
    from market.models import Dividend
    from portfolio.models import Transaction

    async def no_sync(ticker):
        return 0

    monkeypatch.setattr(tax, "sync_dividends", no_sync)
    async with AsyncSessionLocal() as s:
        await add_daily_bars(s, [
            {"ticker": "BBCA", "day": date(2025, 12, d),
             "open": 1000.0, "high": 1000.0, "low": 1000.0, "close": c, "volume": 0}
            for d, c in ((30, 1100.0), (31, 1150.0))
        ])
        s.add(Transaction(user_id=client.user_id, ticker="BBCA", side="buy", quantity=1000,
                          price=1000.0, fees=1_513.0, trade_date=date(2025, 1, 2)))
        s.add(Dividend(ticker="BBCA", ex_date=date(2025, 6, 2), amount=100.0))
        await s.commit()

    r = await client.get("/api/portfolio/tax-summary", params={"year": 2025})
    assert r.status_code == 200
    out = r.json()
    assert out["years"][-1] == 2025
    (h,) = out["holdings"]
    assert (h["shares"], h["cost"]) == (1000, 1_001_513)
    assert (h["close"], h["market_value"]) == (1150, 1_150_000)
    assert out["totals"]["dividends_gross"] == 100_000
    assert out["totals"]["dividends_tax"] == 10_000  # the default 10%

    # Before the first trade: nothing held.
    empty = (await client.get("/api/portfolio/tax-summary", params={"year": 2024})).json()
    assert empty["holdings"] == [] and empty["totals"]["cost"] == 0

    future = await client.get("/api/portfolio/tax-summary", params={"year": 2100})
    assert future.status_code == 400
