"""
accounts/security_log.py
------------------------
The account activity log: sign-ins (and failed ones), password and 2FA changes,
signed-out devices and what an admin changed. Everyone sees their own
(Settings → Security), admins see all of it (Users & invites). Entries older
than SECURITY_LOG_DAYS go in the daily purge_auth job.

A "device" is a browser: a random id in a long-lived cookie, of which only the
hash is stored. A sign-in from a browser the account hasn't used before (after
its very first sign-in) is marked as a new device, and the owner gets an email
when email is set up.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.models import SecurityEvent, User
from accounts.schemas import AdminSecurityEventOut, SecurityEventKind, SecurityEventOut
from clock import utcnow


async def record(
    session: AsyncSession,
    user_id: int,
    kind: SecurityEventKind,
    *,
    ip: str | None,
    user_agent: str | None,
    detail: str | None = None,
    device_hash: str | None = None,
    new_device: bool = False,
) -> None:
    """Add an entry and commit."""
    session.add(SecurityEvent(
        user_id=user_id, kind=kind, at=utcnow(), ip=ip,
        user_agent=(user_agent or "")[:255] or None,
        device_hash=device_hash, new_device=new_device,
        detail=(detail or "")[:255] or None,
    ))
    await session.commit()


async def is_new_device(session: AsyncSession, user_id: int, device_hash: str) -> bool:
    """True when the account signed in before, but never from this browser."""
    signed_in = SecurityEvent.user_id == user_id, SecurityEvent.kind == "sign_in"
    if (await session.execute(select(SecurityEvent.id).where(*signed_in).limit(1))).first() is None:
        return False  # the first sign-in ever (the account was just created)
    seen = await session.execute(
        select(SecurityEvent.id)
        .where(*signed_in, SecurityEvent.device_hash == device_hash)
        .limit(1)
    )
    return seen.first() is None


def _out(event: SecurityEvent) -> SecurityEventOut:
    return SecurityEventOut(
        id=event.id, kind=event.kind, at=event.at, ip=event.ip,
        device=describe_device(event.user_agent), new_device=event.new_device,
        detail=event.detail,
    )


async def recent(session: AsyncSession, user_id: int, limit: int) -> list[SecurityEventOut]:
    rows = await session.execute(
        select(SecurityEvent)
        .where(SecurityEvent.user_id == user_id)
        .order_by(SecurityEvent.at.desc(), SecurityEvent.id.desc())
        .limit(limit)
    )
    return [_out(e) for e in rows.scalars()]


async def recent_all(session: AsyncSession, limit: int) -> list[AdminSecurityEventOut]:
    rows = await session.execute(
        select(SecurityEvent, User)
        .join(User, User.id == SecurityEvent.user_id)
        .order_by(SecurityEvent.at.desc(), SecurityEvent.id.desc())
        .limit(limit)
    )
    return [
        AdminSecurityEventOut(
            **_out(event).model_dump(), user_id=user.id, user_name=user.name,
            user_email=user.email,
        )
        for event, user in rows.tuples()
    ]


# Checked in order: several browsers carry "Chrome" or "Safari" in their name,
# and phones carry "Mac OS X" or "Linux".
_BROWSERS = [
    ("Edg", "Edge"), ("OPR", "Opera"), ("SamsungBrowser", "Samsung Internet"),
    ("FxiOS", "Firefox"), ("Firefox", "Firefox"), ("CriOS", "Chrome"),
    ("Chrome", "Chrome"), ("Safari", "Safari"),
]
_SYSTEMS = [
    ("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("CrOS", "ChromeOS"),
    ("Mac OS X", "macOS"), ("Macintosh", "macOS"), ("Windows", "Windows"), ("Linux", "Linux"),
]


def describe_device(user_agent: str | None) -> str:
    """'Chrome on macOS' from a User-Agent header (a hint, not proof: it's sent by
    the browser)."""
    ua = user_agent or ""
    browser = next((name for key, name in _BROWSERS if re.search(rf"\b{key}/", ua)), None)
    system = next((name for key, name in _SYSTEMS if key in ua), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "Unknown device"
