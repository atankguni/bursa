"""Tests for the provider registry and adapter contract."""

import pytest

from config import settings
from market.providers import registry
from market.providers.base import FUNDAMENTALS, PRICES, MarketDataProvider
from market.providers.yahoo import YahooProvider, _profile_from_info


def test_yahoo_is_registered_and_default():
    assert settings.price_provider == "yahoo"
    assert settings.fundamentals_provider == "yahoo"
    assert isinstance(registry.price_provider(), YahooProvider)
    assert isinstance(registry.fundamentals_provider(), YahooProvider)


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        MarketDataProvider()  # pyright: ignore[reportAbstractUsage] - the point of the test


def test_yahoo_capabilities():
    caps = YahooProvider().capabilities
    assert {PRICES, FUNDAMENTALS} <= caps


def test_available_lists_providers_and_capabilities():
    items = registry.available()
    names = {i["name"] for i in items}
    assert "yahoo" in names
    yahoo = next(i for i in items if i["name"] == "yahoo")
    assert "prices" in yahoo["capabilities"]
    assert "fundamentals" in yahoo["capabilities"]


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "price_provider", "does-not-exist")
    with pytest.raises(ValueError, match="Unknown data provider"):
        registry.price_provider()


def test_profile_from_info_maps_company_fields():
    info = {
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "longBusinessSummary": "A bank.",
        "fullTimeEmployees": 27_728,
        "website": "https://www.bca.co.id",
        "country": "Indonesia",
        "city": "Jakarta",
        "address1": "Menara BCA",
        "phone": "62 21 2358 8000",
        "companyOfficers": [
            {"name": "Mr. A", "title": "President Director"},
            {"name": None, "title": "ignored"},
        ],
    }
    p = _profile_from_info(info)
    assert p is not None
    assert p["description"] == "A bank."
    assert p["industry"] == "Banks - Regional"
    assert p["employees"] == 27_728
    assert p["address"] == "Menara BCA"
    assert p["officers"] == [{"name": "Mr. A", "title": "President Director"}]


def test_profile_from_info_none_when_all_empty():
    assert _profile_from_info({}) is None


class _FakeTicker:
    def __init__(self, income, balance, info):
        self.income_stmt, self.balance_sheet, self.info = income, balance, info


_SUMMARY_INFO = {
    "financialCurrency": "IDR", "bookValue": 232.68, "impliedSharesOutstanding": 1_333_334_556,
    "netIncomeToCommon": 20_824_385_536, "totalRevenue": 1_177_732_513_792,
    "mostRecentQuarter": 1782777600,  # 2026-06-30
}


def test_summary_fallback_when_statements_are_empty(monkeypatch):
    import pandas as pd

    import market.providers.yahoo as yahoo

    empty = pd.DataFrame()
    monkeypatch.setattr(yahoo.yf, "Ticker", lambda t: _FakeTicker(empty, empty, _SUMMARY_INFO))
    rows, _ = yahoo.YahooProvider().fetch_fundamentals("ZYRX.JK")

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "summary" and row["fiscal_year"] == 2026
    assert row["equity"] == 232.68 * 1_333_334_556  # book value/share x shares (IDR)
    assert row["net_income"] == 20_824_385_536 and row["total_assets"] is None


def test_no_summary_row_when_statements_exist_or_book_value_missing(monkeypatch):
    import pandas as pd

    import market.providers.yahoo as yahoo

    col = pd.Timestamp("2025-12-31")
    income = pd.DataFrame({col: [100.0, 10.0]}, index=["Total Revenue", "Net Income"])
    balance = pd.DataFrame({col: [500.0, 300.0, 200.0]},
                           index=["Total Assets", "Total Liabilities Net Minority Interest",
                                  "Stockholders Equity"])
    monkeypatch.setattr(yahoo.yf, "Ticker", lambda t: _FakeTicker(income, balance, _SUMMARY_INFO))
    rows, _ = yahoo.YahooProvider().fetch_fundamentals("X.JK")
    assert [r["source"] for r in rows] == ["statements"]

    no_book = {k: v for k, v in _SUMMARY_INFO.items() if k != "bookValue"}
    empty = pd.DataFrame()
    monkeypatch.setattr(yahoo.yf, "Ticker", lambda t: _FakeTicker(empty, empty, no_book))
    assert yahoo.YahooProvider().fetch_fundamentals("X.JK")[0] == []
