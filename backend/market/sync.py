"""
market/sync.py
--------------
Batched yfinance ingestion (anti rate-limit).

Strategy: instead of one HTTP request per ticker we issue a SINGLE batched call
to `yf.download()` covering every symbol, then upsert the parsed OHLCV bars.
"""

import asyncio
import logging
from datetime import UTC

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import AsyncSessionLocal
from models import StockPrice

log = logging.getLogger("bursa.market.sync")


def _download_batch(tickers: list[str], period: str, interval: str) -> pd.DataFrame:
    """Blocking batched download. Runs in a thread via `asyncio.to_thread`."""
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
    """
    Extract the per-ticker sub-frame from a batched download, tolerating both
    the MultiIndex layout and the flat single-ticker layout.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        first_level = df.columns.get_level_values(0)
        if ticker not in first_level:
            return pd.DataFrame()
        return df[ticker].dropna(subset=["Close"])
    # Single ticker -> flat columns.
    return df.dropna(subset=["Close"])


def _to_rows(df: pd.DataFrame, ticker: str, interval: str) -> list[dict]:
    """Convert a per-ticker OHLCV frame into a list of upsert-ready dicts."""
    rows: list[dict] = []
    for ts, row in df.iterrows():
        try:
            # Normalise pandas Timestamp -> naive UTC datetime.
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


async def _upsert_rows(rows: list[dict]) -> int:
    """Idempotent bulk upsert keyed on (ticker, timestamp, interval)."""
    if not rows:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = sqlite_insert(StockPrice).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "timestamp", "interval"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def _download_with_retry(
    tickers: list[str], period: str, interval: str, attempts: int = 3
) -> pd.DataFrame:
    """Batch download with a few retries + backoff to survive transient blocks."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await asyncio.to_thread(_download_batch, tickers, period, interval)
        except Exception as exc:  # noqa: BLE001 - log and retry
            last_exc = exc
            log.warning(
                "Download attempt %d/%d failed (%s/%s): %s",
                attempt, attempts, period, interval, exc,
            )
            if attempt < attempts:
                await asyncio.sleep(2 ** attempt)  # 2s, 4s backoff
    log.error("All %d download attempts failed (%s/%s)", attempts, period, interval)
    if last_exc:
        raise last_exc
    return pd.DataFrame()


async def sync_batch(tickers: list[str], period: str, interval: str) -> int:
    """Download a batch, parse every ticker, upsert all rows. Returns rows written."""
    try:
        df = await _download_with_retry(tickers, period, interval)
    except Exception as exc:  # network / yfinance failure -> never crash the job
        log.warning("Batch download failed (%s/%s): %s", period, interval, exc)
        return 0

    all_rows: list[dict] = []
    for ticker in tickers:
        sub = _frame_for_ticker(df, ticker)
        if not sub.empty:
            all_rows.extend(_to_rows(sub, ticker, interval))

    written = await _upsert_rows(all_rows)
    log.info(
        "[%s] synced %d bars across %d tickers",
        interval, written, len(tickers),
    )
    return written
