"""
market/providers/base.py
------------------------
Provider interface for market data sources.

Prices and fundamentals can be served by *different* providers (free price
feeds are common; fundamentals are scarce), so consumers resolve a provider per
capability — see `registry.py`.

An adapter is responsible for its own transport/parsing and for returning data
in the app's canonical shape:
  * price bars  -> list of {ticker, timestamp, interval, open, high, low, close, volume}
  * fundamentals-> list of {ticker, fiscal_year, financial_currency, total_shares,
                            revenue, net_income, total_assets, total_liabilities,
                            equity, updated_at}  (monetary values in base currency)
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import TypedDict

# Capability flags a provider may declare in `capabilities`.
PRICES = "prices"
INTRADAY = "intraday"
FUNDAMENTALS = "fundamentals"
FX = "fx"
PROFILE = "profile"
SEARCH = "search"
DIVIDENDS = "dividends"
INDEX_QUOTES = "index_quotes"
SPLITS = "splits"


# --------------------------------------------------------------------------- #
# Canonical shapes every adapter returns (keys match the ORM columns, so rows
# can be passed straight to `sqlite_insert(...).values(...)`).
# --------------------------------------------------------------------------- #
class PriceBar(TypedDict):
    ticker: str
    timestamp: datetime
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class FundamentalRow(TypedDict):
    ticker: str
    fiscal_year: int
    financial_currency: str
    total_shares: float | None
    revenue: float | None
    net_income: float | None
    total_assets: float | None
    total_liabilities: float | None
    equity: float | None
    # "statements" (yearly statement tables) or "summary" (Yahoo's summary
    # metrics, used when a company has no statement tables).
    source: str
    updated_at: datetime


class Officer(TypedDict):
    name: str
    title: str | None


class ProfileData(TypedDict):
    """Company profile + point-in-time metrics (StockProfile columns)."""

    sector: str | None
    industry: str | None
    description: str | None
    employees: int | None
    website: str | None
    country: str | None
    city: str | None
    address: str | None
    phone: str | None
    officers: list[Officer] | None
    trailing_pe: float | None
    profit_margin: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    dividend_yield: float | None
    beta: float | None


class SymbolHit(TypedDict):
    symbol: str
    name: str
    exchange: str
    type: str


class IndexQuote(TypedDict):
    """Latest value of a market index (provider symbol)."""

    symbol: str
    last: float
    previous_close: float | None
    open: float | None
    high: float | None
    low: float | None


class SplitRow(TypedDict):
    """A stock split: `ratio` new shares per old share (5.0 = 5-for-1)."""

    ex_date: date
    ratio: float


class DividendRow(TypedDict):
    ex_date: date
    amount: float


class MarketDataProvider(ABC):
    """Base class every data-source adapter implements."""

    name: str = "base"
    capabilities: set[str] = set()

    @abstractmethod
    def fetch_price_rows(
        self, tickers: list[str], period: str, interval: str
    ) -> dict[str, list[PriceBar]]:
        """Return {ticker: [bar, ...]} for the requested period/interval."""

    @abstractmethod
    def fetch_fundamentals(
        self, ticker: str
    ) -> tuple[list[FundamentalRow], ProfileData | None]:
        """Return (yearly fundamental rows in base currency, optional profile)."""

    @abstractmethod
    def fetch_fx_rate(self, currency: str, base: str) -> float | None:
        """Return `base` per 1 unit of `currency` (1.0 when equal)."""

    def search_symbols(self, query: str) -> list[SymbolHit]:
        """Optional: resolve a free-text query to symbols. Defaults to none."""
        return []

    def fetch_index_quotes(self, symbols: list[str]) -> list[IndexQuote]:
        """Optional: latest value + previous close per index symbol. Defaults to none."""
        return []

    def fetch_splits(self, ticker: str) -> list[SplitRow]:
        """Optional: historical stock splits. Defaults to none."""
        return []

    def fetch_dividends(self, ticker: str) -> list[DividendRow]:
        """Optional: historical dividends as [{ex_date, amount}]. Defaults to none."""
        return []
