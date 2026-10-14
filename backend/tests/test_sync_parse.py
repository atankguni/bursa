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
