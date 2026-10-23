"""Tests for the IDX market clock."""

from datetime import datetime
from zoneinfo import ZoneInfo

from market.trading_clock import is_open, session, status

WIB = ZoneInfo("Asia/Jakarta")


def at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=WIB)


# 2026-01-05 is a Monday; 2026-01-03 is a Saturday; 2026-01-01 is a holiday.
def test_pre_open():
    assert session(at(2026, 1, 5, 8, 50)) == "pre_open"
    assert is_open(at(2026, 1, 5, 8, 50)) is False


def test_session1_open():
    assert session(at(2026, 1, 5, 10, 0)) == "open"
    assert is_open(at(2026, 1, 5, 10, 0)) is True


def test_lunch_break():
    assert session(at(2026, 1, 5, 12, 30)) == "break"
    assert is_open(at(2026, 1, 5, 12, 30)) is False


def test_session2_open():
    assert session(at(2026, 1, 5, 14, 0)) == "open"


def test_after_close():
    assert session(at(2026, 1, 5, 17, 0)) == "closed"
    assert is_open(at(2026, 1, 5, 17, 0)) is False


def test_weekend_closed():
    assert session(at(2026, 1, 3, 10, 0)) == "closed"


def test_holiday_closed():
    assert session(at(2026, 1, 1, 10, 0)) == "closed"


def test_status_shape_and_next_change():
    now = at(2026, 1, 5, 10, 0)
    s = status(now)
    assert s.is_open is True
    assert s.session == "open"
    assert s.next_change_at is not None and s.next_change_at > now
    assert s.next_change_label  # e.g. "closes in 2h 0m"
