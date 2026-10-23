"""Tests for screener filtering and sector aggregation (pure functions)."""

from market.overview import aggregate_sectors
from signals.schemas import ScreenerRow
from signals.screener import filter_rows

ROWS = [
    ScreenerRow(ticker="A", name="A", score=80, pbv=1.0, roe=0.20, rating="Strong Buy",
                sector="Banks", change_percent=1.0),
    ScreenerRow(ticker="B", name="B", score=50, pbv=3.0, roe=0.05, rating="Hold",
                sector="Banks", change_percent=-1.0),
    ScreenerRow(ticker="C", name="C"),
]


def _keys(rows: list[ScreenerRow]) -> set[str]:
    return {r.ticker for r in rows}


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
        ScreenerRow(ticker="A", name="A", sector="Banks", change_percent=1.0),
        ScreenerRow(ticker="B", name="B", sector="Banks", change_percent=-1.0),
        ScreenerRow(ticker="C", name="C", sector="Mining", change_percent=2.0),
        ScreenerRow(ticker="D", name="D"),  # ignored: no change
    ]
    agg = aggregate_sectors(rows)
    assert agg[0].sector == "Mining"  # highest avg first
    banks = next(s for s in agg if s.sector == "Banks")
    assert banks.count == 2
    assert banks.avg_change_percent == 0.0
