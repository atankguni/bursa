"""
fundamentals.py
---------------
Yearly fundamentals ingestion via yfinance.

For each ticker we pull:
  * income statement  -> Total Revenue, Net Income                (yearly)
  * balance sheet     -> Total Assets, Total Liabilities, Equity  (yearly)
  * info              -> sharesOutstanding (fallback: shares issued)

Numbers are stored raw (IDR). yfinance has no true batch endpoint for
statements, so calls are per-ticker and throttled when syncing many symbols.
"""

import asyncio
import logging
from datetime import datetime

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import AsyncSessionLocal
from models import Fundamental

log = logging.getLogger("bursa.fundamentals")

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


def fetch_rows(ticker: str) -> list[dict]:
    """Blocking fetch + parse of one ticker's yearly fundamentals."""
    try:
        t = yf.Ticker(ticker)
        income = t.income_stmt
        balance = t.balance_sheet
    except Exception as exc:  # noqa: BLE001 - network / parse failure
        log.warning("Fundamentals fetch failed for %s: %s", ticker, exc)
        return []

    # Shares outstanding (yfinance .info can be flaky -> fall back to BS).
    shares: float | None = None
    try:
        shares = t.info.get("sharesOutstanding")
    except Exception:  # noqa: BLE001
        shares = None
    if shares is None:
        shares = _pick(balance, _BS_SHARES, balance.columns[0] if balance is not None and not balance.empty else None)

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
                "total_shares": shares,
                "revenue": _pick(income, _INCOME_REVENUE, icol),
                "net_income": _pick(income, _INCOME_NET, icol),
                "total_assets": _pick(balance, _BS_ASSETS, bcol),
                "total_liabilities": _pick(balance, _BS_LIABILITIES, bcol),
                "equity": _pick(balance, _BS_EQUITY, bcol),
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
