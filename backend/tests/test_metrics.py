"""Unit tests for the PBV / RoE metric math."""

from market.metrics import derive_metrics
from market.models import Fundamental


def _f(**overrides) -> Fundamental:
    """A Fundamental ORM instance (not persisted) with sensible defaults."""
    base = {
        "ticker": "TEST",
        "fiscal_year": 2024,
        "financial_currency": "IDR",
        "total_shares": 1_000.0,
        "revenue": 10_000.0,
        "net_income": 1_000.0,
        "total_assets": 8_000.0,
        "total_liabilities": 3_000.0,
        "equity": 5_000.0,
    }
    base.update(overrides)
    return Fundamental(**base)


def test_pbv_and_roe_happy_path():
    # market cap = 10 * 1000 = 10_000 ; book = 8000 - 3000 = 5000 -> PBV 2.0
    # RoE = 1000 / 5000 = 0.2
    m = derive_metrics(price=10.0, f=_f())
    assert m.market_cap == 10_000.0
    assert m.book_value == 5_000.0
    assert m.pbv == 2.0
    assert m.roe == 0.2


def test_book_value_falls_back_to_equity():
    m = derive_metrics(price=10.0, f=_f(total_assets=None, total_liabilities=None))
    assert m.book_value == 5_000.0


def test_missing_equity_yields_no_roe():
    m = derive_metrics(price=10.0, f=_f(equity=0))
    assert m.roe is None


def test_missing_shares_yields_no_market_cap():
    m = derive_metrics(price=10.0, f=_f(total_shares=None))
    assert m.market_cap is None
    assert m.pbv is None


def test_no_price_yields_no_market_cap():
    m = derive_metrics(price=None, f=_f())
    assert m.market_cap is None
    assert m.pbv is None
    # RoE is independent of price.
    assert m.roe == 0.2


def test_none_fundamentals_is_all_none():
    m = derive_metrics(price=10.0, f=None)
    assert m.market_cap is None
    assert m.pbv is None
    assert m.roe is None


def test_roe_blank_on_negative_equity():
    from market.metrics import derive_metrics
    from market.models import Fundamental

    f = Fundamental(
        ticker="X", fiscal_year=2025, total_shares=1000.0, net_income=-500.0,
        total_assets=4_000.0, total_liabilities=5_000.0, equity=-1_000.0,
    )
    m = derive_metrics(100.0, f)
    assert m.roe is None  # was +0.5: a loss over negative equity
    assert m.pbv is None  # book value <= 0 -> PBV undefined
