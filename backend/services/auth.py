"""
services/auth.py
----------------
Accounts for an invite-only deployment: passwords, sessions, invites and
password resets.

* Passwords are hashed with Argon2id (argon2-cffi defaults, RFC 9106 profile).
* Sessions, invites and resets use random 256-bit tokens. Only their SHA-256
  is stored, so a database leak doesn't hand out working links or sessions.
* There is no sign-up: an admin invites people. On a fresh install (no users)
  the app logs a one-time setup link for the first admin (`ensure_setup_invite`).
"""

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Any, Literal, cast

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import utcnow
from config import settings
from mail.base import is_valid_address
from models import (
    Invite,
    MfaChallenge,
    PasswordReset,
    TrustedDevice,
    User,
    UserSession,
)

log = logging.getLogger("bursa.auth")

Role = Literal["user", "admin"]
ROLES: tuple[Role, ...] = ("user", "admin")

_hasher = PasswordHasher()
# Verified against when the email is unknown, so a miss costs as much time as a
# wrong password and response timing doesn't reveal which emails have accounts.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))
# Writing last_seen on every request would mean a DB write per API call.
_TOUCH_INTERVAL = timedelta(minutes=5)


class AuthError(ValueError):
    """A user-facing problem (bad link, weak password, ...); the message is safe to show."""


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #
def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """(raw token for the cookie/link, hash for the database)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


async def check_password_policy(password: str, email: str = "", name: str = "") -> None:
    """Refuse weak or leaked passwords (services/passwords.py)."""
    from services.passwords import password_problem

    problem = await password_problem(password, email=normalize_email(email), name=name)
    if problem:
        raise AuthError(problem)


def _set_password(user: User, password: str) -> None:
    """Store a password that just passed the policy."""
    user.password_hash = hash_password(password)
    user.password_weak = False


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(user: User | None, password: str) -> bool:
    try:
        return _hasher.verify(user.password_hash if user else _DUMMY_HASH, password) and (
            user is not None
        )
    except (VerificationError, InvalidHashError):
        return False


def link(path: str) -> str:
    return f"{settings.public_url.rstrip('/')}{path}"


# --------------------------------------------------------------------------- #
# Sign-in throttling (in-process: the app runs as a single process)
# --------------------------------------------------------------------------- #
_failures: dict[str, deque[float]] = defaultdict(deque)


def _recent(key: str, now: float) -> deque[float]:
    window = settings.login_window_minutes * 60
    q = _failures[key]
    while q and now - q[0] > window:
        q.popleft()
    return q


def login_blocked(email: str, ip: str | None) -> bool:
    now = time.monotonic()
    limit = settings.login_max_failures
    if len(_recent(f"email:{normalize_email(email)}", now)) >= limit:
        return True
    return ip is not None and len(_recent(f"ip:{ip}", now)) >= limit * 3


def record_failure(email: str, ip: str | None) -> None:
    now = time.monotonic()
    _recent(f"email:{normalize_email(email)}", now).append(now)
    if ip is not None:
        _recent(f"ip:{ip}", now).append(now)


def clear_failures(email: str) -> None:
    _failures.pop(f"email:{normalize_email(email)}", None)


# --------------------------------------------------------------------------- #
# Users & sessions
# --------------------------------------------------------------------------- #
async def user_by_email(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(User.email == normalize_email(email)))
    ).scalar_one_or_none()


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await user_by_email(session, email)
    if not verify_password(user, password) or user is None or not user.is_active:
        return None
    if _hasher.check_needs_rehash(user.password_hash):  # parameters were raised since
        user.password_hash = hash_password(password)
    return user


async def create_session(
    session: AsyncSession, user: User, user_agent: str | None, ip: str | None
) -> str:
    raw, digest = new_token()
    now = utcnow()
    session.add(UserSession(
        token_hash=digest, user_id=user.id, created_at=now, last_seen_at=now,
        expires_at=now + timedelta(days=settings.session_days),
        user_agent=(user_agent or "")[:255] or None, ip=ip,
    ))
    user.last_login_at = now
    await session.commit()
    return raw


async def user_for_token(session: AsyncSession, raw: str) -> User | None:
    """The active user behind a session cookie; slides the expiry while in use."""
    row = (
        await session.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.token_hash == hash_token(raw))
        )
    ).one_or_none()
    if row is None:
        return None
    sess, user = row.tuple()
    now = utcnow()
    if sess.expires_at <= now or not user.is_active:
        return None
    if now - sess.last_seen_at > _TOUCH_INTERVAL:
        sess.last_seen_at = now
        sess.expires_at = now + timedelta(days=settings.session_days)
        await session.commit()
    return user


async def revoke_session(session: AsyncSession, raw: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.token_hash == hash_token(raw)))
    await session.commit()


async def revoke_sessions(
    session: AsyncSession, user_id: int, keep_raw: str | None = None
) -> None:
    """Sign a user out everywhere (optionally except the current browser)."""
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if keep_raw:
        stmt = stmt.where(UserSession.token_hash != hash_token(keep_raw))
    await session.execute(stmt)


async def change_password(
    session: AsyncSession, user: User, current: str, new: str, keep_raw: str | None
) -> None:
    if not verify_password(user, current):
        raise AuthError("Current password is incorrect")
    await check_password_policy(new, user.email, user.name)
    _set_password(user, new)
    await revoke_sessions(session, user.id, keep_raw)
    await session.commit()


async def active_admins(session: AsyncSession) -> int:
    return (await session.execute(
        select(func.count()).select_from(User)
        .where(User.role == "admin", User.is_active.is_(True))
    )).scalar_one()


# --------------------------------------------------------------------------- #
# Invites
# --------------------------------------------------------------------------- #
async def create_invite(
    session: AsyncSession, email: str, role: Role, invited_by: int | None
) -> str:
    """A fresh invite for `email` (earlier unused ones are replaced). Returns the raw token."""
    email = normalize_email(email)
    if not is_valid_address(email):
        raise AuthError("Enter a valid email address")
    if await user_by_email(session, email) is not None:
        raise AuthError("That email already has an account")
    await session.execute(
        delete(Invite).where(Invite.email == email, Invite.accepted_at.is_(None))
    )
    raw, digest = new_token()
    now = utcnow()
    session.add(Invite(
        email=email, role=role, token_hash=digest, invited_by=invited_by,
        created_at=now, expires_at=now + timedelta(days=settings.invite_days),
    ))
    await session.commit()
    return raw


async def open_invite(session: AsyncSession, raw: str) -> Invite:
    invite = (
        await session.execute(select(Invite).where(Invite.token_hash == hash_token(raw)))
    ).scalar_one_or_none()
    if invite is None or invite.accepted_at is not None:
        raise AuthError("This invite link is invalid or was already used")
    if invite.expires_at <= utcnow():
        raise AuthError("This invite link has expired; ask for a new one")
    return invite


async def accept_invite(
    session: AsyncSession, raw: str, name: str, password: str, email: str | None = None
) -> User:
    """Create the account. The setup invite (no email on it) takes the email here."""
    invite = await open_invite(session, raw)
    address = normalize_email(invite.email or email or "")
    if not is_valid_address(address):
        raise AuthError("Enter a valid email address")
    if await user_by_email(session, address) is not None:
        raise AuthError("That email already has an account")
    name = name.strip()
    if not name or len(name) > 80:
        raise AuthError("Enter your name (80 characters at most)")
    await check_password_policy(password, address, name)

    first = (await session.execute(select(func.count()).select_from(User))).scalar_one() == 0
    user = User(email=address, name=name, password_hash=hash_password(password),
                role="admin" if first else invite.role, is_active=True)
    session.add(user)
    invite.accepted_at = utcnow()
    await session.commit()
    log.info("Account created: %s (%s)", address, user.role)
    return user


async def ensure_setup_invite() -> None:
    """
    No accounts yet: log a one-time link to create the admin. Regenerated on
    every start until it is used, so an old link from the logs stops working.
    """
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        if (await session.execute(select(func.count()).select_from(User))).scalar_one():
            return
        await session.execute(delete(Invite).where(Invite.email == ""))
        raw, digest = new_token()
        now = utcnow()
        session.add(Invite(
            email="", role="admin", token_hash=digest, invited_by=None, created_at=now,
            expires_at=now + timedelta(days=settings.invite_days),
        ))
        await session.commit()
    log.warning("No accounts yet. Create the admin account here: %s", link(f"/invite/{raw}"))


# --------------------------------------------------------------------------- #
# Password resets
# --------------------------------------------------------------------------- #
async def create_reset(session: AsyncSession, user: User) -> str:
    await session.execute(
        delete(PasswordReset).where(
            PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)
        )
    )
    raw, digest = new_token()
    now = utcnow()
    session.add(PasswordReset(
        user_id=user.id, token_hash=digest, created_at=now,
        expires_at=now + timedelta(hours=settings.password_reset_hours),
    ))
    await session.commit()
    return raw


async def open_reset(session: AsyncSession, raw: str) -> tuple[PasswordReset, User]:
    row = (
        await session.execute(
            select(PasswordReset, User)
            .join(User, User.id == PasswordReset.user_id)
            .where(PasswordReset.token_hash == hash_token(raw))
        )
    ).one_or_none()
    if row is None or row[0].used_at is not None or not row[1].is_active:
        raise AuthError("This reset link is invalid or was already used")
    if row[0].expires_at <= utcnow():
        raise AuthError("This reset link has expired; request a new one")
    return row.tuple()


async def reset_password(session: AsyncSession, raw: str, password: str) -> User:
    reset, user = await open_reset(session, raw)
    await check_password_policy(password, user.email, user.name)
    _set_password(user, password)
    reset.used_at = utcnow()
    await revoke_sessions(session, user.id)  # sign out everywhere
    # Remembered devices must pass 2FA again. 2FA itself stays on: a reset link
    # only proves access to the inbox.
    await session.execute(delete(TrustedDevice).where(TrustedDevice.user_id == user.id))
    await session.commit()
    clear_failures(user.email)
    return user


async def purge_expired() -> int:
    """Delete expired sessions, invite / reset links, 2FA challenges and
    remembered devices (daily job)."""
    from database import AsyncSessionLocal

    now = utcnow()
    removed = 0
    async with AsyncSessionLocal() as session:
        for stmt in (
            delete(UserSession).where(UserSession.expires_at <= now),
            delete(Invite).where(Invite.accepted_at.is_(None), Invite.expires_at <= now),
            delete(PasswordReset).where(PasswordReset.expires_at <= now),
            delete(MfaChallenge).where(MfaChallenge.expires_at <= now),
            delete(TrustedDevice).where(TrustedDevice.expires_at <= now),
        ):
            removed += cast(CursorResult[Any], await session.execute(stmt)).rowcount or 0
        await session.commit()
    return removed
