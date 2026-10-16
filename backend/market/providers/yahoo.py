"""
market/providers/yahoo.py
-------------------------
Yahoo Finance adapter (via `yfinance`) — the default and only provider today.

This is the ONLY module that imports `yfinance`, so swapping providers later
means adding a sibling adapter and registering it, not touching the services.
"""

import logging
import math
from collections.abc import Hashable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yfinance as yf

from config import settings
from market.providers.base import (
    DIVIDENDS,
    FUNDAMENTALS,
    FX,
    INDEX_QUOTES,
    INTRADAY,
    PRICES,
    PROFILE,
    SEARCH,
    SPLITS,
    DividendRow,
    FundamentalRow,
    IndexQuote,
    MarketDataProvider,
    Officer,
    PriceBar,
    ProfileData,
    SplitRow,
    SymbolHit,
)

log = logging.getLogger("bursa.providers.yahoo")

# yfinance creates its cache folder lazily with a non-atomic "exists? else
# mkdir", which races under `yf.download(threads=True)`: a losing thread gets
# "[Errno 17] File exists" and the tz cache is disabled for the whole process
# (every download then re-fetches each symbol's timezone). Creating the folder
# up front, before any download thread starts, removes the race.
_CACHE_DIR = Path(settings.yfinance_cache_dir)
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(_CACHE_DIR))

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
def _download_batch(tickers: list[str], period: str, interval: str) -> pd.DataFrame | None:
    """
    Blocking grouped download. NOTE: yfinance still issues ~one HTTP request per
    symbol internally, so callers must pass reasonably sized chunks.
    """
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


def _frame_for_ticker(df: pd.DataFrame | None, ticker: str) -> pd.DataFrame:
    """Per-ticker sub-frame, tolerating MultiIndex and flat layouts."""
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        if ticker not in df.columns.get_level_values(0):
            return pd.DataFrame()
        df = cast(pd.DataFrame, df[ticker])
    return df.dropna(subset=["Close"])


_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _to_rows(df: pd.DataFrame, ticker: str, interval: str) -> list[PriceBar]:
    """Convert a per-ticker OHLCV frame into upsert-ready dicts."""
    if df.empty or any(c not in df.columns for c in _OHLCV):
        return []
    values = df[_OHLCV].to_numpy(dtype=float, na_value=math.nan)
    rows: list[PriceBar] = []
    for stamp, (o, h, lo, c, v) in zip(pd.DatetimeIndex(df.index), values, strict=True):
        if math.isnan(c):
            continue  # no close -> no bar
        dt = stamp.to_pydatetime()
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        rows.append(
            {
                "ticker": ticker,
                "timestamp": dt,
                "interval": interval,
                # A bar with a close but a missing open/high/low is drawn flat.
                "open": c if math.isnan(o) else float(o),
                "high": c if math.isnan(h) else float(h),
                "low": c if math.isnan(lo) else float(lo),
                "close": float(c),
                "volume": 0 if math.isnan(v) else int(v),
            }
        )
    return rows


def _pick(
    df: pd.DataFrame | None, labels: list[str], col: Hashable | None
) -> float | None:
    """First non-null value among `labels` at column `col`."""
    if df is None or df.empty or col is None or col not in df.columns:
        return None
    for label in labels:
        if label in df.index:
            val = df.loc[label, col]
            if pd.notna(val):
                return float(val)
    return None


def _col_for_year(df: pd.DataFrame | None, year: int) -> Hashable | None:
    """Return the statement column (a Timestamp) whose year matches."""
    if df is None or df.empty:
        return None
    for c in df.columns:
        if getattr(c, "year", None) == year:
            return c
    return None


def _shares_outstanding(info: Mapping[str, Any], balance: pd.DataFrame | None) -> float | None:
    """
    Current share count, from the most reliable source available.

    Yahoo's `sharesOutstanding` is wrong for some IDX listings (BBNI 0.58bn vs
    37.3bn actual, BCIC 0.28M vs 18.1bn), which made PBV ~0. The implied count
    (market cap ÷ price) and the balance-sheet count agree with reality, so
    they win; `sharesOutstanding` is only a last resort.
    """
    latest_col: Hashable | None = (
        cast(Hashable, balance.columns[0]) if balance is not None and not balance.empty else None
    )
    for candidate in (
        info.get("impliedSharesOutstanding"),
        _pick(balance, _BS_SHARES, latest_col),
        info.get("sharesOutstanding"),
    ):
        if candidate and candidate > 0:
            return float(candidate)
    return None


def _summary_row(
    ticker: str,
    info: Mapping[str, Any],
    shares: float | None,
    currency: str,
    rate: float,
) -> FundamentalRow | None:
    """
    Latest figures from Yahoo's summary metrics, for companies whose statement
    tables are empty (common for small IDX listings). Equity = book value per
    share x shares; income/revenue are trailing twelve months. Dated by the most
    recent quarter the book value comes from.
    """
    book_per_share = info.get("bookValue")
    if not shares or not book_per_share:
        return None
    stamp = info.get("mostRecentQuarter") or info.get("lastFiscalYearEnd")
    year = datetime.fromtimestamp(stamp, UTC).year if stamp else datetime.now(UTC).year

    def money(key: str) -> float | None:
        value = info.get(key)
        return None if value is None else float(value) * rate

    return {
        "ticker": ticker,
        "fiscal_year": year,
        "financial_currency": currency,
        "total_shares": shares,
        "revenue": money("totalRevenue"),
        "net_income": money("netIncomeToCommon"),
        "total_assets": None,
        "total_liabilities": None,
        "equity": float(book_per_share) * shares * rate,
        "source": "summary",
        "updated_at": datetime.utcnow(),
    }


def _profile_from_info(info: Mapping[str, Any]) -> ProfileData | None:
    """Extract optional info-derived metrics + company profile (may all be None)."""
    officers: list[Officer] = [
        {"name": o.get("name"), "title": o.get("title")}
        for o in (info.get("companyOfficers") or [])
        if o.get("name")
    ]
    keys: ProfileData = {
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
    capabilities = {
        PRICES, INTRADAY, FUNDAMENTALS, FX, PROFILE, SEARCH, DIVIDENDS, INDEX_QUOTES, SPLITS,
    }

    def __init__(self) -> None:
        self._fx_cache: dict[str, tuple[float, datetime]] = {}

    # --- Prices -------------------------------------------------------------
    def fetch_price_rows(
        self, tickers: list[str], period: str, interval: str
    ) -> dict[str, list[PriceBar]]:
        df = _download_batch(tickers, period, interval)
        out: dict[str, list[PriceBar]] = {}
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
    def fetch_fundamentals(
        self, ticker: str
    ) -> tuple[list[FundamentalRow], ProfileData | None]:
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

        shares = _shares_outstanding(info, balance)

        def money(value: float | None) -> float | None:
            return None if value is None else value * rate

        years: set[int] = set()
        for df in (income, balance):
            if df is not None and not df.empty:
                years |= {c.year for c in df.columns if getattr(c, "year", None)}

        rows: list[FundamentalRow] = []
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
                    "source": "statements",
                    "updated_at": datetime.utcnow(),
                }
            )
        if not rows:
            # No statement tables: fall back to the summary metrics so PBV/RoE
            # aren't blank for small caps Yahoo only summarises.
            summary = _summary_row(ticker, info, shares, currency, rate)
            if summary is not None:
                rows.append(summary)
        return rows, profile

    # --- Search -------------------------------------------------------------
    def search_symbols(self, query: str) -> list[SymbolHit]:
        """Resolve a free-text query to candidate symbols via Yahoo search."""
        try:
            quotes = yf.Search(query, max_results=10).quotes
        except Exception as exc:  # noqa: BLE001 - network / parse failure
            log.warning("Symbol search failed for %r: %s", query, exc)
            return []

        out: list[SymbolHit] = []
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

    # --- Index quotes -------------------------------------------------------
    def fetch_index_quotes(self, symbols: list[str]) -> list[IndexQuote]:
        """
        Latest value + previous close per index. `fast_info` is used because
        Yahoo's IDX `.JK` index symbols return only today's bar from history,
        so the previous close can't be derived from bars.
        """
        def num(info: Any, key: str) -> float | None:
            v = info.get(key)
            return float(v) if v else None

        out: list[IndexQuote] = []
        for symbol in symbols:
            try:
                fi = yf.Ticker(symbol).fast_info
                last = num(fi, "lastPrice")
                if last is None:
                    continue
                out.append({
                    "symbol": symbol, "last": last,
                    "previous_close": num(fi, "previousClose"),
                    "open": num(fi, "open"), "high": num(fi, "dayHigh"), "low": num(fi, "dayLow"),
                })
            except Exception as exc:  # noqa: BLE001 - one bad symbol mustn't stop the rest
                log.warning("Index quote failed for %s: %s", symbol, exc)
        return out

    # --- Splits -------------------------------------------------------------
    def fetch_splits(self, ticker: str) -> list[SplitRow]:
        """Historical stock splits (ratio = new shares per old share)."""
        try:
            splits = yf.Ticker(ticker).splits
        except Exception as exc:  # noqa: BLE001 - network / parse failure
            log.warning("Split fetch failed for %s: %s", ticker, exc)
            return []
        out: list[SplitRow] = []
        if splits is not None:
            for ts, ratio in splits.items():
                stamp = pd.Timestamp(cast(Any, ts))
                if isinstance(stamp, pd.Timestamp) and float(ratio) > 0:
                    out.append({"ex_date": stamp.date(), "ratio": float(ratio)})
        return out

    # --- Dividends ----------------------------------------------------------
    def fetch_dividends(self, ticker: str) -> list[DividendRow]:
        """Historical cash dividends as [{ex_date, amount}]."""
        try:
            divs = yf.Ticker(ticker).dividends
        except Exception as exc:  # noqa: BLE001 - network / parse failure
            log.warning("Dividend fetch failed for %s: %s", ticker, exc)
            return []

        out: list[DividendRow] = []
        if divs is not None:
            for ts, amount in divs.items():
                try:
                    stamp = pd.Timestamp(cast(Any, ts))
                    if not isinstance(stamp, pd.Timestamp):  # NaT: unusable date
                        continue
                    out.append({"ex_date": stamp.date(), "amount": float(amount)})
                except (TypeError, ValueError):
                    continue
        return out
