"""Tests for screener filtering and sector aggregation (pure functions)."""

from services.market_overview import aggregate_sectors
from services.screener import filter_rows

ROWS = [
    {"ticker": "A", "score": 80, "pbv": 1.0, "roe": 0.20, "rating": "Strong Buy",
     "sector": "Banks", "change_percent": 1.0},
    {"ticker": "B", "score": 50, "pbv": 3.0, "roe": 0.05, "rating": "Hold",
     "sector": "Banks", "change_percent": -1.0},
    {"ticker": "C", "score": None, "pbv": None, "roe": None, "rating": None,
     "sector": None, "change_percent": None},
]


def _keys(rows):
    return {r["ticker"] for r in rows}


def test_no_filters_keeps_all():
    assert _keys(filter_rows(ROWS)) == {"A", "B", "C"}


def test_min_score_excludes_missing():
    assert _keys(filter_rows(ROWS, min_score=60)) == {"A"}


def test_max_pbv():
    assert _keys(filter_rows(ROWS, max_pbv=2.0)) == {"A"}


def test_min_roe():
    assert _keys(filter_rows(ROWS, min_roe=0.1)) == {"A"}


def test_buy_only():
    assert _keys(filter_rows(ROWS, buy_only=True)) == {"A"}


def test_rating_exact():
    assert _keys(filter_rows(ROWS, rating="Hold")) == {"B"}


def test_sector():
    assert _keys(filter_rows(ROWS, sector="Banks")) == {"A", "B"}


def test_aggregate_sectors_averages_and_sorts():
    rows = [
        {"sector": "Banks", "change_percent": 1.0},
        {"sector": "Banks", "change_percent": -1.0},
        {"sector": "Mining", "change_percent": 2.0},
        {"sector": None, "change_percent": None},  # ignored
    ]
    agg = aggregate_sectors(rows)
    assert agg[0]["sector"] == "Mining"  # highest avg first
    banks = next(s for s in agg if s["sector"] == "Banks")
    assert banks["count"] == 2
    assert banks["avg_change_percent"] == 0.0
