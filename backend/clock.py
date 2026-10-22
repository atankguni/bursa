"""
clock.py
--------
The current time, as the database stores it: naive datetimes in UTC (the
columns have no time zone). Use this instead of `datetime.utcnow()`, which is
deprecated. Market-local dates use `settings.timezone` (services/market_clock).
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Now in UTC, without tzinfo (comparable with stored timestamps)."""
    return datetime.now(UTC).replace(tzinfo=None)
