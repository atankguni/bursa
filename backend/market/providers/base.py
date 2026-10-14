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

# Capability flags a provider may declare in `capabilities`.
PRICES = "prices"
INTRADAY = "intraday"
FUNDAMENTALS = "fundamentals"
FX = "fx"
PROFILE = "profile"
SEARCH = "search"
DIVIDENDS = "dividends"


class MarketDataProvider(ABC):
    """Base class every data-source adapter implements."""

    name: str = "base"
    capabilities: set[str] = set()

    @abstractmethod
    def fetch_price_rows(
        self, tickers: list[str], period: str, interval: str
    ) -> dict[str, list[dict]]:
        """Return {ticker: [bar, ...]} for the requested period/interval."""

    @abstractmethod
    def fetch_fundamentals(self, ticker: str) -> tuple[list[dict], dict | None]:
        """Return (yearly fundamental rows in base currency, optional profile)."""

    @abstractmethod
    def fetch_fx_rate(self, currency: str, base: str) -> float | None:
        """Return `base` per 1 unit of `currency` (1.0 when equal)."""

    def search_symbols(self, query: str) -> list[dict]:
        """Optional: resolve a free-text query to symbols. Defaults to none."""
        return []

    def fetch_dividends(self, ticker: str) -> list[dict]:
        """Optional: historical dividends as [{ex_date, amount}]. Defaults to none."""
        return []
