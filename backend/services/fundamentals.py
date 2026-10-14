"""
services/fundamentals.py
------------------------
Yearly fundamentals ingestion via yfinance.

For each ticker we pull:
  * income statement  -> Total Revenue, Net Income                (yearly)
  * balance sheet     -> Total Assets, Total Liabilities, Equity  (yearly)
  * info              -> sharesOutstanding (fallback: shares issued)

Statements may be filed in a foreign currency (e.g. PGAS reports in USD); all
monetary values are converted to IDR so ratios vs the IDR market cap are valid.
yfinance has no batch endpoint for statements, so calls are per-ticker.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import settings
from database import AsyncSessionLocal
from models import Fundamental

log = logging.getLogger("bursa.fundamentals")

# Everything is normalised to IDR so PBV (IDR market cap / IDR book value) works.
PRICE_CURRENCY = "IDR"

# Cache FX rates (currency -> (rate, fetched_at)) to avoid a call per ticker.
_fx_cache: dict[str, tuple[float, datetime]] = {}

# Candidate row labels across the various Yahoo statement layouts.
_INCOME_REVENUE = ["Total Revenue", "Operating Revenue"]
_INCOME_NET = [
    "Net Income",
    "Net Income Common Stockholders",
    "Net Income Including Noncontrolling Interests",
]
_BS_ASSETS = ["Total Assets"]
_BS_LIABILITIES = [
    "Total Liabilities Net Minority Interest",
    "Total Liabilities",
]
_BS_EQUITY = [
    "Stockholders Equity",
    "Common Stock Equity",
    "Total Equity Gross Minority Interest",
]
_BS_SHARES = ["Ordinary Shares Number", "Share Issued"]


def _fx_rate(currency: str) -> float | None:
    """
    IDR per unit of `currency`. Returns 1.0 for IDR, a cached rate when fresh,
    or a freshly-fetched rate. Returns None if the rate cannot be determined.
    """
    currency = (currency or PRICE_CURRENCY).upper()
    if currency == PRICE_CURRENCY:
        return 1.0

    now = datetime.utcnow()
    ttl = timedelta(hours=settings.fx_cache_hours)
    cached = _fx_cache.get(currency)
    if cached and now - cached[1] < ttl:
        return cached[0]

    try:
        fx = yf.Ticker(f"{currency}{PRICE_CURRENCY}=X").fast_info
        rate = fx.get("lastPrice") or fx.get("last_price")
        if rate:
            rate = float(rate)
            _fx_cache[currency] = (rate, now)
            return rate
    except Exception as exc:  # noqa: BLE001 - network failure
        log.warning("FX fetch failed %s->%s: %s", currency, PRICE_CURRENCY, exc)

    # Fall back to a stale cached rate rather than producing a wrong ratio.
    if cached:
        return cached[0]
    return None


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


def is_stale(rows: list[Fundamental]) -> bool:
    """True if we have no cached rows or the newest one is older than the TTL."""
    if not rows:
        return True
    times = [r.updated_at for r in rows if r.updated_at is not None]
    if not times:
        return True
    ttl = timedelta(hours=settings.fundamentals_stale_hours)
    return datetime.utcnow() - max(times) > ttl


def fetch_rows(ticker: str) -> list[dict]:
    """Blocking fetch + parse of one ticker's yearly fundamentals (to IDR)."""
    try:
        t = yf.Ticker(ticker)
        income = t.income_stmt
        balance = t.balance_sheet
        info = t.info
    except Exception as exc:  # noqa: BLE001 - network / parse failure
        log.warning("Fundamentals fetch failed for %s: %s", ticker, exc)
        return []

    # Reporting currency vs the trading currency. Statements in a foreign
    # currency (e.g. PGAS reports in USD) must be converted before any ratio
    # against the IDR market cap is meaningful.
    currency = (info.get("financialCurrency") or PRICE_CURRENCY).upper()
    rate = _fx_rate(currency)
    if rate is None:
        log.warning(
            "Skipping %s: no FX rate %s->%s (statements cannot be converted)",
            ticker, currency, PRICE_CURRENCY,
        )
        return []

    # Shares outstanding (yfinance .info can be flaky -> fall back to BS).
    shares: float | None = info.get("sharesOutstanding")
    if shares is None:
        shares = _pick(
            balance,
            _BS_SHARES,
            balance.columns[0] if balance is not None and not balance.empty else None,
        )

    def money(value: float | None) -> float | None:
        """Convert a monetary statement figure into IDR."""
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
    return rows


async def sync_ticker(ticker: str) -> int:
    """Fetch and upsert one ticker's fundamentals. Returns rows written."""
    rows = await asyncio.to_thread(fetch_rows, ticker)
    if not rows:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = sqlite_insert(Fundamental).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "fiscal_year"],
            set_={
                "financial_currency": stmt.excluded.financial_currency,
                "total_shares": stmt.excluded.total_shares,
                "revenue": stmt.excluded.revenue,
                "net_income": stmt.excluded.net_income,
                "total_assets": stmt.excluded.total_assets,
                "total_liabilities": stmt.excluded.total_liabilities,
                "equity": stmt.excluded.equity,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def sync_many(tickers: list[str], throttle: float = 1.0) -> int:
    """Sync several tickers sequentially with a small delay between calls."""
    total = 0
    for i, ticker in enumerate(tickers):
        total += await sync_ticker(ticker)
        if throttle and i < len(tickers) - 1:
            await asyncio.sleep(throttle)
    if tickers:
        log.info("Fundamentals synced for %d tickers (%d rows)", len(tickers), total)
    return total
