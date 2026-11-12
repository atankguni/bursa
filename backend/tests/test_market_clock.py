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


def test_sale_settles_two_trading_days_later():
    from datetime import date

    from market.trading_clock import next_trade_date, settlement_date

    # Monday during trading: today, settles Wednesday.
    s = status(at(2026, 1, 5, 10, 0))
    assert (s.trade_date, s.settlement_date) == (date(2026, 1, 5), date(2026, 1, 7))
    # Wednesday before Christmas (Thu cuti bersama, Fri Christmas, weekend): Tuesday.
    assert settlement_date(date(2026, 12, 23)) == date(2026, 12, 29)
    # After Wednesday's close: trades Monday the 28th.
    assert next_trade_date(at(2026, 12, 23, 16, 30)) == date(2026, 12, 28)
    # Before Nyepi and Lebaran (closed 18-24 March 2026): settles the 26th.
    assert settlement_date(date(2026, 3, 17)) == date(2026, 3, 26)
    # Weekend / New Year's Day: the next trading day.
    assert next_trade_date(at(2026, 1, 3, 10, 0)) == date(2026, 1, 5)
    assert next_trade_date(at(2025, 12, 31, 17, 0)) == date(2026, 1, 2)


def test_holiday_calendar_matches_idx():
    """IDX's announced trading-day totals: catches a dropped or mistyped date."""
    from datetime import date, timedelta

    from market.holidays import IDX_HOLIDAYS
    from market.trading_clock import is_trading_day

    days = [date.fromisoformat(d) for d in IDX_HOLIDAYS]
    assert all(d.weekday() < 5 for d in days)  # weekend holidays aren't listed

    def trading_days(year: int) -> int:
        d, n = date(year, 1, 1), 0
        while d.year == year:
            n += is_trading_day(d)
            d += timedelta(days=1)
        return n

    assert trading_days(2026) == 239
    assert trading_days(2027) == 241
