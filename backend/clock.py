"""
clock.py
--------
The current time. Points in time are always timezone-aware UTC in the app and
stored as UTC (`db.types.UTCDateTime`); market-local dates and times use
`settings.timezone` (market/trading_clock).
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from config import settings


def utcnow() -> datetime:
    """Now, as an aware UTC datetime."""
    return datetime.now(UTC)


def local_today() -> date:
    """Today's date at the exchange (settings.timezone), not the server's: the
    container runs in UTC, which is still "yesterday" before 07:00 in Jakarta."""
    return datetime.now(ZoneInfo(settings.timezone)).date()


def as_utc(value: datetime) -> datetime:
    """`value` in UTC; a naive value (old stored text, a lenient client) is taken as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def day_key(day: date) -> datetime:
    """The timestamp a daily bar is stored under: midnight (UTC) of its trading date.
    A label for the exchange-local date, not the instant the session opened."""
    return datetime.combine(day, time(), UTC)
