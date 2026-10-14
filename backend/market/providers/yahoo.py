"""
market/providers/yahoo.py
-------------------------
Yahoo Finance adapter (via `yfinance`) — the default and only provider today.

This is the ONLY module that imports `yfinance`, so swapping providers later
means adding a sibling adapter and registering it, not touching the services.
"""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from config import settings
from market.providers.base import (
    DIVIDENDS,
    FUNDAMENTALS,
    FX,
    INTRADAY,
    PRICES,
    PROFILE,
    SEARCH,
    MarketDataProvider,
)

log = logging.getLogger("bursa.providers.yahoo")

# Candidate row labels across the various Yahoo statement layouts.
_INCOME_REVENUE = ["Total Revenue", "Operating Revenue"]
_INCOME_NET = [
    "Net Income",
    "Net Income Common Stockholders",
    "Net Income Including Noncontrolling Interests",
]
_BS_ASSETS = ["Total Assets"]
_BS_LIABILITIES = ["Total Liabilities Net Minority Interest", "Total Liabilities"]
_BS_EQUITY = [
    "Stockholders Equity",
    "Common Stock Equity",
    "Total Equity Gross Minority Interest",
]
_BS_SHARES = ["Ordinary Shares Number", "Share Issued"]


# --------------------------------------------------------------------------- #
# Price parsing helpers (module-level so they are easy to unit-test)
# --------------------------------------------------------------------------- #
def _download_batch(tickers: list[str], period: str, interval: str) -> pd.DataFrame:
    """Blocking batched download — one HTTP call for every symbol."""
    return yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        group_by="ticker",  # -> MultiIndex (ticker, field)
        auto_adjust=False,
        progress=False,
        threads=True,
        prepost=False,
    )


def _frame_for_ticker(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Per-ticker sub-frame, tolerating MultiIndex and flat layouts."""
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        if ticker not in df.columns.get_level_values(0):
            return pd.DataFrame()
        return df[ticker].dropna(subset=["Close"])
    return df.dropna(subset=["Close"])


def _to_rows(df: pd.DataFrame, ticker: str, interval: str) -> list[dict]:
    """Convert a per-ticker OHLCV frame into upsert-ready dicts."""
    rows: list[dict] = []
    for ts, row in df.iterrows():
        try:
            dt = ts.to_pydatetime()
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)
            close = float(row["Close"])
            if pd.isna(close):
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "timestamp": dt,
                    "interval": interval,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": close,
                    "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                }
            )
        except (KeyError, TypeError, ValueError) as exc:  # skip malformed bars
            log.debug("Skipping bar for %s at %s: %s", ticker, ts, exc)
    return rows


def _pick(df: pd.DataFrame | None, labels: list[str], col) -> float | None:
    """First non-null value among `labels` at column `col`."""
    if df is None or df.empty or col is None or col not in df.columns:
        return None
    for label in labels:
        if label in df.index:
            val = df.loc[label, col]
            if pd.notna(val):
                return float(val)
    return None


def _col_for_year(df: pd.DataFrame | None, year: int):
    """Return the statement column (a Timestamp) whose year matches."""
    if df is None or df.empty:
        return None
    for c in df.columns:
        if getattr(c, "year", None) == year:
            return c
    return None


def _profile_from_info(info: dict) -> dict | None:
    """Extract optional info-derived metrics + company profile (may all be None)."""
    officers = [
        {"name": o.get("name"), "title": o.get("title")}
        for o in (info.get("companyOfficers") or [])
        if o.get("name")
    ]
    keys = {
        # Company profile
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "description": info.get("longBusinessSummary"),
        "employees": info.get("fullTimeEmployees"),
        "website": info.get("website"),
        "country": info.get("country"),
        "city": info.get("city"),
        "address": info.get("address1"),
        "phone": info.get("phone"),
        "officers": officers or None,
        # Metrics
        "trailing_pe": info.get("trailingPE"),
        "profit_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
    }
    if all(v is None for v in keys.values()):
        return None
    return keys


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
class YahooProvider(MarketDataProvider):
    name = "yahoo"
    capabilities = {PRICES, INTRADAY, FUNDAMENTALS, FX, PROFILE, SEARCH, DIVIDENDS}

    def __init__(self) -> None:
        self._fx_cache: dict[str, tuple[float, datetime]] = {}

    # --- Prices -------------------------------------------------------------
    def fetch_price_rows(
        self, tickers: list[str], period: str, interval: str
    ) -> dict[str, list[dict]]:
        df = _download_batch(tickers, period, interval)
        out: dict[str, list[dict]] = {}
        for ticker in tickers:
            sub = _frame_for_ticker(df, ticker)
            if not sub.empty:
                out[ticker] = _to_rows(sub, ticker, interval)
        return out

    # --- FX -----------------------------------------------------------------
    def fetch_fx_rate(self, currency: str, base: str) -> float | None:
        """`base` per 1 unit of `currency`, cached for `fx_cache_hours`."""
        currency = (currency or base).upper()
        base = (base or "IDR").upper()
        if currency == base:
            return 1.0

        now = datetime.utcnow()
        ttl = timedelta(hours=settings.fx_cache_hours)
        cached = self._fx_cache.get(currency)
        if cached and now - cached[1] < ttl:
            return cached[0]

        try:
            fx = yf.Ticker(f"{currency}{base}=X").fast_info
            rate = fx.get("lastPrice") or fx.get("last_price")
            if rate:
                rate = float(rate)
                self._fx_cache[currency] = (rate, now)
                return rate
        except Exception as exc:  # noqa: BLE001 - network failure
            log.warning("FX fetch failed %s->%s: %s", currency, base, exc)

        # Fall back to a stale cached rate rather than producing a wrong ratio.
        return cached[0] if cached else None

    # --- Fundamentals -------------------------------------------------------
    def fetch_fundamentals(self, ticker: str) -> tuple[list[dict], dict | None]:
        """Fetch + parse one ticker's yearly fundamentals (normalized to base)."""
        base = settings.base_currency
        try:
            t = yf.Ticker(ticker)
            income = t.income_stmt
            balance = t.balance_sheet
            info = t.info
        except Exception as exc:  # noqa: BLE001 - network / parse failure
            log.warning("Fundamentals fetch failed for %s: %s", ticker, exc)
            return [], None

        profile = _profile_from_info(info)

        # Statements in a foreign currency (e.g. PGAS reports in USD) must be
        # converted before any ratio against the base-currency market cap works.
        currency = (info.get("financialCurrency") or base).upper()
        rate = self.fetch_fx_rate(currency, base)
        if rate is None:
            log.warning(
                "Skipping %s: no FX rate %s->%s (statements cannot be converted)",
                ticker, currency, base,
            )
            return [], profile

        shares: float | None = info.get("sharesOutstanding")
        if shares is None:
            shares = _pick(
                balance,
                _BS_SHARES,
                balance.columns[0]
                if balance is not None and not balance.empty
                else None,
            )

        def money(value: float | None) -> float | None:
            return None if value is None else value * rate

        years: set[int] = set()
        for df in (income, balance):
            if df is not None and not df.empty:
                years |= {c.year for c in df.columns if getattr(c, "year", None)}

        rows: list[dict] = []
        for year in sorted(years):
            icol = _col_for_year(income, year)
            bcol = _col_for_year(balance, year)
            rows.append(
                {
                    "ticker": ticker,
                    "fiscal_year": year,
                    "financial_currency": currency,
                    "total_shares": shares,
                    "revenue": money(_pick(income, _INCOME_REVENUE, icol)),
                    "net_income": money(_pick(income, _INCOME_NET, icol)),
                    "total_assets": money(_pick(balance, _BS_ASSETS, bcol)),
                    "total_liabilities": money(_pick(balance, _BS_LIABILITIES, bcol)),
                    "equity": money(_pick(balance, _BS_EQUITY, bcol)),
                    "updated_at": datetime.utcnow(),
                }
            )
        return rows, profile

    # --- Search -------------------------------------------------------------
    def search_symbols(self, query: str) -> list[dict]:
        """Resolve a free-text query to candidate symbols via Yahoo search."""
        try:
            quotes = yf.Search(query, max_results=10).quotes
        except Exception as exc:  # noqa: BLE001 - network / parse failure
            log.warning("Symbol search failed for %r: %s", query, exc)
            return []

        out: list[dict] = []
        for q in quotes or []:
            symbol = q.get("symbol")
            if not symbol:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "name": q.get("shortname") or q.get("longname") or symbol,
                    "exchange": q.get("exchDisp") or q.get("exchange") or "",
                    "type": q.get("quoteType") or "",
                }
            )
        return out

    # --- Dividends ----------------------------------------------------------
    def fetch_dividends(self, ticker: str) -> list[dict]:
        """Historical cash dividends as [{ex_date, amount}]."""
        try:
            divs = yf.Ticker(ticker).dividends
        except Exception as exc:  # noqa: BLE001 - network / parse failure
            log.warning("Dividend fetch failed for %s: %s", ticker, exc)
            return []

        out: list[dict] = []
        if divs is not None:
            for ts, amount in divs.items():
                try:
                    ex_date = ts.date() if hasattr(ts, "date") else ts
                    out.append({"ex_date": ex_date, "amount": float(amount)})
                except (AttributeError, TypeError, ValueError):
                    continue
        return out
