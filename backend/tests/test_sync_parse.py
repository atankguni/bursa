"""Tests for the batched-download parsing (now in the Yahoo provider adapter)."""

import numpy as np
import pandas as pd

from market.providers.yahoo import _frame_for_ticker, _to_rows


def _batched_df():
    """Mimic yf.download(group_by='ticker') MultiIndex columns for one ticker."""
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    cols = pd.MultiIndex.from_product(
        [["BBCA.JK"], ["Open", "High", "Low", "Close", "Volume"]]
    )
    data = [
        [9000, 9100, 8950, 9050, 1_000_000],
        [9050, 9200, 9000, 9150, 1_200_000],
    ]
    return pd.DataFrame(data, index=idx, columns=cols)


def test_frame_for_ticker_multiindex():
    sub = _frame_for_ticker(_batched_df(), "BBCA.JK")
    assert not sub.empty
    assert list(sub.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_frame_for_ticker_missing_symbol():
    sub = _frame_for_ticker(_batched_df(), "NOPE.JK")
    assert sub.empty


def test_to_rows_builds_ohlcv_rows():
    rows = _to_rows(_frame_for_ticker(_batched_df(), "BBCA.JK"), "BBCA.JK", "1d")
    assert len(rows) == 2
    first = rows[0]
    assert first["ticker"] == "BBCA.JK"
    assert first["interval"] == "1d"
    assert first["open"] == 9000.0
    assert first["close"] == 9050.0
    assert first["volume"] == 1_000_000
    assert first["timestamp"].year == 2024


def test_to_rows_skips_nan_close():
    sub = _frame_for_ticker(_batched_df(), "BBCA.JK").copy()
    sub.iloc[0, sub.columns.get_loc("Close")] = np.nan
    rows = _to_rows(sub, "BBCA.JK", "1d")
    assert len(rows) == 1


def _bar(ticker, utc, open_, high, low, close, volume):
    from datetime import datetime

    return {
        "ticker": ticker,
        "timestamp": datetime.fromisoformat(utc),
        "interval": "1m",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def test_rollup_daily_aggregates_todays_minutes():
    from datetime import date, datetime

    from market.sync import rollup_daily

    bars = [
        # out of order on purpose; 02:00 UTC = 09:00 WIB
        _bar("BBCA.JK", "2026-10-16T02:05:00", 6060, 6100, 6055, 6090, 300),
        _bar("BBCA.JK", "2026-10-16T02:00:00", 6050, 6070, 6040, 6060, 100),
        _bar("BBCA.JK", "2026-10-16T08:40:00", 6090, 6095, 6020, 6030, 50),
        _bar("TLKM.JK", "2026-10-16T03:00:00", 2900, 2910, 2890, 2905, 10),
    ]
    out = {r["ticker"]: r for r in rollup_daily(bars, date(2026, 10, 16))}

    bbca = out["BBCA.JK"]
    # Same key shape as provider daily bars -> upsert hits today's row.
    assert bbca["timestamp"] == datetime(2026, 10, 16)
    assert bbca["interval"] == "1d"
    assert (bbca["open"], bbca["high"], bbca["low"], bbca["close"]) == (6050, 6100, 6020, 6030)
    assert bbca["volume"] == 450
    assert out["TLKM.JK"]["close"] == 2905


def test_rollup_daily_ignores_other_days():
    from datetime import date

    from market.sync import rollup_daily

    # 2026-10-15T08:40 UTC is still the 15th in WIB -> must not touch the 16th.
    bars = [_bar("BBCA.JK", "2026-10-15T08:40:00", 6000, 6000, 6000, 6000, 1)]
    assert rollup_daily(bars, date(2026, 10, 16)) == []


async def test_sync_batch_records_wall_clock_sync_time(monkeypatch):
    from datetime import UTC, datetime

    import market.sync as sync
    from config import settings

    class _Fake:
        name = "fake"

        def __init__(self, rows):
            self.rows = rows

        def fetch_price_rows(self, tickers, period, interval):
            return self.rows

    async def fake_upsert(rows):
        return len(rows)

    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    monkeypatch.setattr(sync, "_upsert_rows", fake_upsert)
    monkeypatch.setattr(sync, "_last_synced_at", None)

    # Nothing written -> no sync time recorded.
    monkeypatch.setattr(sync, "price_provider", lambda: _Fake({}))
    await sync.sync_batch(["BBCA.JK"], period="1y", interval="1d")
    assert sync.last_synced_at() is None

    # A midnight-dated daily bar must still report *now*, timezone-aware.
    bar = _bar("BBCA.JK", "2020-01-02T00:00:00", 1, 1, 1, 1, 1) | {"interval": "1d"}
    monkeypatch.setattr(sync, "price_provider", lambda: _Fake({"BBCA.JK": [bar]}))
    before = datetime.now(UTC)
    await sync.sync_batch(["BBCA.JK"], period="1y", interval="1d")
    synced = sync.last_synced_at()
    assert synced is not None and synced.tzinfo is not None
    assert synced >= before


def test_shares_outstanding_prefers_implied_then_balance_sheet():
    from market.providers.yahoo import _shares_outstanding

    col = pd.Timestamp("2025-12-31")
    balance = pd.DataFrame({col: [37.26e9]}, index=["Ordinary Shares Number"])

    # Real BBNI shape: sharesOutstanding is off by ~64x; implied is right.
    info = {"sharesOutstanding": 5.787e8, "impliedSharesOutstanding": 3.726e10}
    assert _shares_outstanding(info, balance) == 3.726e10
    # No implied count -> balance sheet, still not the broken field.
    assert _shares_outstanding({"sharesOutstanding": 5.787e8}, balance) == 37.26e9
    # Nothing better available -> sharesOutstanding as a last resort.
    assert _shares_outstanding({"sharesOutstanding": 5.787e8}, None) == 5.787e8
    # Zero / missing values are skipped.
    assert _shares_outstanding({"impliedSharesOutstanding": 0}, None) is None


async def test_concurrent_price_requests_get_distinct_single_flight_keys(monkeypatch):
    import market.sync as sync

    keys: list[str] = []

    async def fake_call(provider, key, fn, *args):
        keys.append(key)
        return {}

    monkeypatch.setattr(sync.governor, "call", fake_call)
    provider = type("P", (), {"name": "fake", "fetch_price_rows": None})()
    await sync._fetch_with_retry(provider, ["BBCA.JK"], "max", "1d")
    await sync._fetch_with_retry(provider, ["BBCA.JK", "TLKM.JK"], "1d", "1m")
    # Previously both used the key "prices", so one could receive the other's bars.
    assert len(set(keys)) == 2
