"""
services/market_clock.py
------------------------
Single source of truth for "is the IDX open?".

Both the scheduler (which decides when to sync intraday data) and the
`/api/market-status` endpoint use this, so the UI indicator always agrees with
the background worker.

Sessions (local exchange time): pre-open 08:45-09:00, Session 1 09:00-12:00,
lunch break 12:00-13:30, Session 2 13:30-15:50. Weekends and IDX holidays are
closed.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from config import settings
from market.holidays import IDX_HOLIDAYS

WIB = ZoneInfo(settings.timezone)

PRE_OPEN_START = time.fromisoformat(settings.pre_open_start)
SESSION1_START = time.fromisoformat(settings.session1_start)
SESSION1_END = time.fromisoformat(settings.session1_end)
SESSION2_START = time.fromisoformat(settings.session2_start)
SESSION2_END = time.fromisoformat(settings.session2_end)

_BOUNDARIES = (
    PRE_OPEN_START,
    SESSION1_START,
    SESSION1_END,
    SESSION2_START,
    SESSION2_END,
)


def is_trading_day(d: date) -> bool:
    """Weekday and not a listed IDX holiday."""
    return d.weekday() < 5 and d.isoformat() not in IDX_HOLIDAYS


def session(now: datetime | None = None) -> str:
    """One of: pre_open, open, break, closed."""
    now = (now or datetime.now(WIB)).astimezone(WIB)
    if not is_trading_day(now.date()):
        return "closed"
    t = now.time()
    if PRE_OPEN_START <= t < SESSION1_START:
        return "pre_open"
    if SESSION1_START <= t < SESSION1_END:
        return "open"
    if SESSION1_END <= t < SESSION2_START:
        return "break"
    if SESSION2_START <= t < SESSION2_END:
        return "open"
    return "closed"


def is_open(now: datetime | None = None) -> bool:
    """True while the exchange is actively trading (either session)."""
    return session(now) == "open"


def _human(delta: timedelta) -> str:
    total = max(0, int(delta.total_seconds()))
    hours, minutes = divmod(total // 60, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _next_transition(now: datetime) -> datetime | None:
    """The next session boundary strictly after `now` (scanning ~10 days)."""
    candidates: list[datetime] = []
    for offset in range(0, 10):
        d = (now + timedelta(days=offset)).date()
        if is_trading_day(d):
            candidates.extend(datetime.combine(d, b, tzinfo=WIB) for b in _BOUNDARIES)
    future = [c for c in candidates if c > now]
    return min(future) if future else None


def status(now: datetime | None = None) -> dict:
    """Snapshot used by the API: state + when it next changes."""
    now = (now or datetime.now(WIB)).astimezone(WIB)
    current = session(now)
    nxt = _next_transition(now)

    label = ""
    if nxt is not None:
        # Which state does the transition lead into?
        into = session(nxt + timedelta(seconds=1))
        verb = "opens" if into in ("pre_open", "open") else "closes"
        label = f"{verb} in {_human(nxt - now)}"

    return {
        "is_open": current == "open",
        "session": current,
        "timezone": settings.timezone,
        "server_time": now,
        "next_change_at": nxt,
        "next_change_label": label,
    }
