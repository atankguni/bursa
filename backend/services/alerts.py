"""
services/alerts.py
------------------
Evaluate alert rules and record in-app notifications.

`evaluate_alert` is pure (unit-tested); `evaluate_alerts` loads the data and
writes `AlertEvent` rows. Rating-change detection uses `RatingState` snapshots.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal
from models import Alert, AlertEvent, RatingState
from services.prices import latest_daily
from services.recommendation import compute_universe_cached

log = logging.getLogger("bursa.alerts")

THRESHOLD_TYPES = {"price_above", "price_below", "pct_change"}


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
        return f"{t} rating {prev_rating} → {rating}"
    return f"{t} alert"


async def evaluate_alerts() -> int:
    """Evaluate every active alert; return the number of events created."""
    async with AsyncSessionLocal() as session:
        alerts = (
            await session.execute(select(Alert).where(Alert.active.is_(True)))
        ).scalars().all()
        if not alerts:
            return 0

        tickers = sorted({a.ticker for a in alerts})
        price_map = await latest_daily(session, tickers)
        rec_map = await compute_universe_cached(session)
        states = {
            s.ticker: s
            for s in (
                await session.execute(
                    select(RatingState).where(RatingState.ticker.in_(tickers))
                )
            ).scalars().all()
        }

        cooldown = timedelta(hours=settings.alert_cooldown_hours)
        now = datetime.utcnow()
        created = 0

        for a in alerts:
            info = price_map.get(a.ticker, {})
            price = info.get("close")
            prev = info.get("prev_close")
            rec = rec_map.get(a.ticker)
            rating = rec.rating if rec else None
            state = states.get(a.ticker)
            prev_rating = state.rating if state else None

            triggered, value = evaluate_alert(
                a.type, a.threshold, price, prev, rating, prev_rating
            )

            # Keep the rating snapshot current (also creates the baseline).
            if a.type == "rating_change" and rec is not None:
                if state is None:
                    session.add(
                        RatingState(
                            ticker=a.ticker,
                            rating=rec.rating,
                            strength=rec.strength,
                            updated_at=now,
                        )
                    )
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

            session.add(
                AlertEvent(
                    alert_id=a.id,
                    ticker=a.ticker,
                    triggered_at=now,
                    value=value,
                    message=_message(a, value, rating, prev_rating),
                )
            )
            a.last_triggered_at = now
            created += 1

        await session.commit()

    if created:
        log.info("Alerts: %d event(s) created", created)
    return created
