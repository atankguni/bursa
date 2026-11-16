"""
alerts/emails.py
----------------
Email triggered alerts to the users who turned it on (Settings → Notifications).

New alert events of those users are marked `email_pending` (alerts/service.py).
`send_alert_emails` sends each user's pending events as one email, unless it is
inside their quiet hours: then they wait, and go out together on the first run
after the quiet hours end. Events that waited longer than a day are dropped
(still on the Alerts page), so nobody gets yesterday's price moves by email.

Best effort, like every outgoing message: a failed send stays pending and is
tried again on the next run.
"""

import logging
from collections import defaultdict
from datetime import datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

import mail
from accounts.models import User
from accounts.preferences import alert_email_settings
from accounts.schemas import QuietHours
from alerts.models import AlertEvent
from clock import as_utc, utcnow
from config import settings
from database import AsyncSessionLocal
from mail import Email
from mail.templates import layout

log = logging.getLogger("bursa.alert_emails")

MAX_AGE = timedelta(hours=24)


def _clock(hhmm: str) -> time:
    hours, minutes = hhmm.split(":")
    return time(int(hours), int(minutes))


def in_quiet_hours(quiet: QuietHours | None, now: time) -> bool:
    """Whether `now` (local time) falls in the quiet hours; they may cross midnight."""
    if quiet is None:
        return False
    start, end = _clock(quiet.start), _clock(quiet.end)
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def render(user: User, events: list[AlertEvent]) -> Email:
    """One email for a user's waiting alerts, oldest first."""
    tz = ZoneInfo(settings.timezone)
    link = f"{settings.public_url.rstrip('/')}/alerts"
    off = "Turn these emails off in Settings → Notifications."
    first = events[0]
    title = first.message if len(events) == 1 else f"{len(events)} Bursa alerts"
    lines = [
        (as_utc(e.triggered_at).astimezone(tz).strftime("%H:%M"), e.message) for e in events
    ]
    name = user.name or user.email.split("@")[0]
    text = "\n".join(
        [f"Hi {name},", ""]
        + [f"- {at}  {message}" for at, message in lines]
        + ["", f"See them in Bursa: {link}", off]
    )
    body = f'<p style="margin:0 0 12px;">Hi {escape(name)},</p>' + "".join(
        f'<div style="margin:0 0 6px;"><span style="color:#64748b;">{escape(at)}</span>'
        f"&nbsp; {escape(message)}</div>"
        for at, message in lines
    )
    body += (
        f'<p style="margin:16px 0 0;"><a href="{escape(link)}">Open your alerts</a></p>'
        f'<p style="margin:12px 0 0;font-size:12px;color:#64748b;">{escape(off)}</p>'
    )
    return Email(subject=title, text=text, html=layout(title, body), to=(user.email,))


async def send_alert_emails(now: datetime | None = None) -> int:
    """Send every user's pending alert emails that may go out now; returns emails sent."""
    if not mail.configured():
        return 0
    now = now or utcnow()
    local = now.astimezone(ZoneInfo(settings.timezone)).time()
    sent = 0
    async with AsyncSessionLocal() as session:
        # Too old to be worth an email now (still listed on the Alerts page).
        await session.execute(
            update(AlertEvent)
            .where(AlertEvent.email_pending.is_(True), AlertEvent.triggered_at < now - MAX_AGE)
            .values(email_pending=False)
        )
        pending = (
            await session.execute(
                select(AlertEvent)
                .where(AlertEvent.email_pending.is_(True))
                .order_by(AlertEvent.triggered_at, AlertEvent.id)
            )
        ).scalars().all()
        by_user: dict[int, list[AlertEvent]] = defaultdict(list)
        for event in pending:
            by_user[event.user_id].append(event)
        if not by_user:
            await session.commit()
            return 0

        prefs = await alert_email_settings(session, set(by_user))
        users = {
            u.id: u
            for u in (
                await session.execute(select(User).where(User.id.in_(by_user)))
            ).scalars().all()
        }
        for user_id, events in by_user.items():
            user = users.get(user_id)
            wanted, quiet = prefs[user_id]
            if user is None or not user.is_active or not wanted:
                for e in events:  # turned off (or disabled) since: nothing to send
                    e.email_pending = False
                continue
            if in_quiet_hours(quiet, local):
                continue  # waits for the end of the quiet hours
            if await mail.send_quietly(render(user, events)):
                sent += 1
                for e in events:
                    e.email_pending = False
        await session.commit()
    if sent:
        log.info("Alert emails: %d sent", sent)
    return sent
