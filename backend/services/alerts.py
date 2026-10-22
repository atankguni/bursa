"""
services/alerts.py
------------------
Evaluate alert rules and record in-app notifications.

`evaluate_alert` is pure (unit-tested); `evaluate_alerts` loads the data and
writes `AlertEvent` rows. Rating-change detection uses per-user `RatingState`
snapshots, scored with each user's own investing style.
"""

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from clock import utcnow
from config import settings
from database import AsyncSessionLocal
from models import Alert, AlertEvent, RatingState, User
from services.dividend_calendar import UpcomingDividend, next_expected
from services.notify import send_quietly
from services.preferences import styles_by_user
from services.prices import latest_daily
from services.recommendation import compute_universe_cached, rating_label

log = logging.getLogger("bursa.alerts")

THRESHOLD_TYPES = {"price_above", "price_below", "pct_change"}
DIVIDEND_DAYS_DEFAULT = 3
# One reminder per expected dividend (they're about a year apart).
_DIVIDEND_REPEAT = timedelta(days=30)


def dividend_due(
    upcoming: UpcomingDividend | None, today: date, days_ahead: float | None
) -> int | None:
    """Days until the expected cum date when it's within `days_ahead`, else None."""
    if upcoming is None:
        return None
    days = (upcoming["cum_date"] - today).days
    limit = DIVIDEND_DAYS_DEFAULT if days_ahead is None else days_ahead
    return days if 0 <= days <= limit else None


def _dividend_message(ticker: str, upcoming: UpcomingDividend) -> str:
    return (
        f"{ticker} dividend expected: last day to buy ≈ "
        f"{upcoming['cum_date']:%a %d %b} (ex-date ≈ {upcoming['expected_ex_date']:%d %b}), "
        f"about Rp {upcoming['amount_per_share']:,.0f}/share. Estimated from last year's "
        "dates; check the company's announcement."
    )


def evaluate_alert(
    alert_type: str,
    threshold: float | None,
    price: float | None,
    prev_close: float | None,
    rating: str | None,
    prev_rating: str | None,
) -> tuple[bool, float | None]:
    """Return (triggered, value) for a single rule."""
    if alert_type == "price_above":
        if price is not None and threshold is not None and price >= threshold:
            return True, price
    elif alert_type == "price_below":
        if price is not None and threshold is not None and price <= threshold:
            return True, price
    elif alert_type == "pct_change":
        if price is not None and prev_close:
            pct = (price - prev_close) / prev_close * 100
            if threshold is not None and abs(pct) >= abs(threshold):
                return True, round(pct, 2)
    elif alert_type == "rating_change":
        if rating and prev_rating and rating != prev_rating:
            return True, None
    return False, None


def _message(
    alert: Alert, value: float | None, rating: str | None, prev_rating: str | None
) -> str:
    t = alert.ticker
    if alert.type == "price_above":
        return f"{t} price {value:g} ≥ {alert.threshold:g}"
    if alert.type == "price_below":
        return f"{t} price {value:g} ≤ {alert.threshold:g}"
    if alert.type == "pct_change":
        return f"{t} moved {value:+.2f}% today"
    if alert.type == "rating_change":
        return f"{t} signal {rating_label(prev_rating or '')} → {rating_label(rating or '')}"
    return f"{t} alert"


async def evaluate_alerts() -> int:
    """Evaluate every active alert of every user; return the number of events created."""
    async with AsyncSessionLocal() as session:
        alerts = (
            await session.execute(
                select(Alert).where(Alert.active.is_(True), Alert.user_id.is_not(None))
            )
        ).scalars().all()
        if not alerts:
            return 0

        user_ids = {a.user_id for a in alerts if a.user_id is not None}
        tickers = sorted({a.ticker for a in alerts})
        today = datetime.now(ZoneInfo(settings.timezone)).date()
        upcoming = await next_expected(
            session, sorted({a.ticker for a in alerts if a.type == "dividend_soon"}), today
        )
        price_map = await latest_daily(session, tickers)
        # Ratings depend on each user's investing style: score once per style used.
        style_of = await styles_by_user(session, user_ids)
        recs = {st: await compute_universe_cached(session, st) for st in set(style_of.values())}
        states = {
            (s.user_id, s.ticker): s
            for s in (
                await session.execute(
                    select(RatingState).where(
                        RatingState.user_id.in_(user_ids), RatingState.ticker.in_(tickers)
                    )
                )
            ).scalars().all()
        }
        # Telegram is the operator's own chat (backend/.env): only admins' alerts go there.
        admins = set((
            await session.execute(
                select(User.id).where(User.id.in_(user_ids), User.role == "admin")
            )
        ).scalars().all())

        cooldown = timedelta(hours=settings.alert_cooldown_hours)
        outbox: list[str] = []  # sent after the events are safely committed (admins only)
        now = utcnow()
        created = 0

        for a in alerts:
            assert a.user_id is not None  # filtered in the query
            info = price_map.get(a.ticker, {})
            price = info.get("close")
            prev = info.get("prev_close")
            rec = recs[style_of[a.user_id]].get(a.ticker)
            rating = rec.rating if rec else None
            state = states.get((a.user_id, a.ticker))
            prev_rating = state.rating if state else None

            if a.type == "dividend_soon":
                due = dividend_due(upcoming.get(a.ticker), today, a.threshold)
                if due is None or (
                    a.last_triggered_at and now - a.last_triggered_at < _DIVIDEND_REPEAT
                ):
                    continue
                message = _dividend_message(a.ticker, upcoming[a.ticker])
                session.add(AlertEvent(user_id=a.user_id, alert_id=a.id, ticker=a.ticker,
                                       triggered_at=now, value=due, message=message))
                a.last_triggered_at = now
                created += 1
                if a.user_id in admins:
                    outbox.append(message)
                continue

            triggered, value = evaluate_alert(
                a.type, a.threshold, price, prev, rating, prev_rating
            )

            # Keep the rating snapshot current (also creates the baseline).
            if a.type == "rating_change" and rec is not None:
                if state is None:
                    state = RatingState(
                        user_id=a.user_id,
                        ticker=a.ticker,
                        rating=rec.rating,
                        strength=rec.strength,
                        updated_at=now,
                    )
                    states[(a.user_id, a.ticker)] = state  # two alerts on one ticker
                    session.add(state)
                elif state.rating != rec.rating:
                    state.rating = rec.rating
                    state.strength = rec.strength
                    state.updated_at = now

            if not triggered:
                continue
            # Throttle price/pct alerts; rating changes are event-based.
            if (
                a.type != "rating_change"
                and a.last_triggered_at
                and now - a.last_triggered_at < cooldown
            ):
                continue

            message = _message(a, value, rating, prev_rating)
            session.add(
                AlertEvent(
                    user_id=a.user_id,
                    alert_id=a.id,
                    ticker=a.ticker,
                    triggered_at=now,
                    value=value,
                    message=message,
                )
            )
            a.last_triggered_at = now
            created += 1
            if a.user_id in admins:
                outbox.append(message)

        await session.commit()

    if created:
        log.info("Alerts: %d event(s) created", created)
    for message in outbox:  # in-app events are recorded first; delivery is best-effort
        await send_quietly(f"🔔 Bursa: {message}")
    return created
