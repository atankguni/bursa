"""
services/two_factor.py
----------------------
Two-factor authentication: a second step after the password.

Methods (a user may have both):
* **Authenticator app** (TOTP, RFC 6238: 6 digits, 30 s): works offline and
  without email. The secret is stored encrypted; each code works once.
* **Email code**: 6 digits sent to the account email (needs email set up).
* **Recovery codes**: 10 single-use backups, created when 2FA is first turned on.

Policy: required for admins (`User.mfa_setup_required`), optional for others.
A password reset does NOT turn 2FA off, so someone with access to the inbox alone
can't take over an account protected by an authenticator app. Only an admin can
reset another user's 2FA.

Brute force: each sign-in challenge allows `mfa_max_attempts` wrong codes, and
wrong codes count as failed sign-ins (services/auth throttling).
"""

import base64
import hashlib
import hmac
import html
import logging
import secrets
import struct
import time
from datetime import timedelta
from typing import Literal
from urllib.parse import quote

import segno
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from clock import utcnow
from config import settings
from mail.templates import layout
from models import MfaChallenge, RecoveryCode, TrustedDevice, User
from services import crypto
from services.auth import AuthError, hash_token, new_token, verify_password

log = logging.getLogger("bursa.2fa")

Method = Literal["totp", "email", "recovery"]

_PERIOD = 30
_DIGITS = 6
_RECOVERY_COUNT = 10
# No 0/O, 1/I/L: recovery codes are typed from paper.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_RESEND_INTERVAL = timedelta(seconds=60)


# --------------------------------------------------------------------------- #
# Authenticator app (TOTP)
# --------------------------------------------------------------------------- #
def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")  # 160 bits


def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 10**_DIGITS:0{_DIGITS}d}"


def totp_code(secret: str, at: float | None = None) -> str:
    return _hotp(secret, int((time.time() if at is None else at) // _PERIOD))


def match_totp(
    secret: str, code: str, last_step: int | None, at: float | None = None
) -> int | None:
    """The time step `code` belongs to (±1 step for clock drift), if not used before."""
    code = _digits(code)
    if len(code) != _DIGITS:
        return None
    now = int((time.time() if at is None else at) // _PERIOD)
    for step in (now - 1, now, now + 1):
        if hmac.compare_digest(_hotp(secret, step), code) and (
            last_step is None or step > last_step
        ):
            return step
    return None


def otpauth_uri(secret: str, email: str) -> str:
    issuer = settings.mfa_issuer
    label = quote(f"{issuer}:{email}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={_DIGITS}&period={_PERIOD}"
    )


def qr_svg(uri: str) -> str:
    """The setup QR code as an inline SVG (no image request leaves the page)."""
    return segno.make(uri, error="m").svg_inline(scale=5, border=2)


# --------------------------------------------------------------------------- #
# Codes
# --------------------------------------------------------------------------- #
def _digits(code: str) -> str:
    return "".join(ch for ch in code if ch.isdigit())


def _normalize_recovery(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _recovery_hash(user_id: int, code: str) -> str:
    return crypto.keyed_hash(f"{user_id}:{_normalize_recovery(code)}", "recovery")


def _email_code_hash(challenge_id: int, code: str) -> str:
    return crypto.keyed_hash(f"{challenge_id}:{_digits(code)}", "email-code")


async def replace_recovery_codes(session: AsyncSession, user: User) -> list[str]:
    """New set of recovery codes (old ones stop working). Shown to the user once."""
    await session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    now = utcnow()
    codes: list[str] = []
    for _ in range(_RECOVERY_COUNT):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))  # ~50 bits
        codes.append(f"{raw[:5]}-{raw[5:]}")
        session.add(RecoveryCode(
            user_id=user.id, code_hash=_recovery_hash(user.id, raw), created_at=now
        ))
    return codes


async def recovery_codes_left(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count()).select_from(RecoveryCode)
        .where(RecoveryCode.user_id == user_id, RecoveryCode.used_at.is_(None))
    )).scalar_one()


async def _use_recovery_code(session: AsyncSession, user: User, code: str) -> bool:
    row = (await session.execute(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == _recovery_hash(user.id, code),
            RecoveryCode.used_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        return False
    row.used_at = utcnow()
    return True


# --------------------------------------------------------------------------- #
# Email
# --------------------------------------------------------------------------- #
def email_hint(email: str) -> str:
    """'lalu@example.com' -> 'l***@example.com' (shown before sign-in completes)."""
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


async def _send(user: User, subject: str, text: str, body_html: str) -> None:
    await mail.send(mail.Email(
        subject=subject, text=text, html=layout(subject, body_html), to=(user.email,)
    ))


async def notify(user: User, subject: str, message: str) -> None:
    """Security notice to the user (best effort; only when email is set up)."""
    if not mail.configured():
        return
    text = (
        f"Hi {user.name},\n\n{message}\n\nIf this wasn't you, change your password and "
        "tell your Bursa admin."
    )
    body = (
        f"<p>Hi {html.escape(user.name)},</p><p>{html.escape(message)}</p>"
        "<p>If this wasn't you, change your password and tell your Bursa admin.</p>"
    )
    await mail.send_quietly(mail.Email(
        subject=subject, text=text, html=layout(subject, body), to=(user.email,)
    ))


async def _send_email_code(
    session: AsyncSession, challenge: MfaChallenge, user: User, why: str
) -> None:
    if not mail.configured():
        raise AuthError("Email isn't set up on this server")
    now = utcnow()
    if challenge.email_sent_at and now - challenge.email_sent_at < _RESEND_INTERVAL:
        raise AuthError("A code was just sent. Wait a minute before asking for another.")
    code = f"{secrets.randbelow(10**_DIGITS):0{_DIGITS}d}"
    challenge.email_code_hash = _email_code_hash(challenge.id, code)
    challenge.email_sent_at = now
    await session.commit()
    minutes = settings.mfa_code_minutes
    try:
        await _send(
            user,
            f"Your Bursa code: {code}",
            f"Your Bursa code is {code}. It {why} and expires in {minutes} minutes.\n\n"
            "If you didn't try to sign in, someone may know your password: change it.",
            f"<p>Your Bursa code is</p><p style=\"font-size:28px;font-weight:700;"
            f"letter-spacing:6px\">{code}</p><p>It {html.escape(why)} and expires in "
            f"{minutes} minutes.</p><p>If you didn't try to sign in, someone may know your "
            "password: change it.</p>",
        )
    except mail.MailError as exc:
        log.warning("2FA email to user %d failed: %s", user.id, exc)
        raise AuthError("Couldn't send the email. Try again, or use another method.") from exc


def _email_code_ok(challenge: MfaChallenge, code: str) -> bool:
    if challenge.email_code_hash is None or challenge.email_sent_at is None:
        return False
    if utcnow() - challenge.email_sent_at > timedelta(minutes=settings.mfa_code_minutes):
        return False
    return hmac.compare_digest(challenge.email_code_hash, _email_code_hash(challenge.id, code))


# --------------------------------------------------------------------------- #
# Sign-in challenge
# --------------------------------------------------------------------------- #
def login_methods(user: User) -> list[Method]:
    """What the user can use right now (email needs a working mail setup)."""
    methods: list[Method] = []
    if user.totp_secret:
        methods.append("totp")
    if user.mfa_email and mail.configured():
        methods.append("email")
    methods.append("recovery")
    return methods


async def start_login(session: AsyncSession, user: User) -> tuple[str, MfaChallenge]:
    """After a correct password: a challenge for the second step (raw token, row).
    When email is the user's main method, the code is sent right away."""
    await session.execute(delete(MfaChallenge).where(
        MfaChallenge.user_id == user.id, MfaChallenge.purpose == "login"
    ))
    raw, digest = new_token()
    now = utcnow()
    challenge = MfaChallenge(
        token_hash=digest, user_id=user.id, purpose="login", created_at=now,
        expires_at=now + timedelta(minutes=settings.mfa_code_minutes), attempts=0,
    )
    session.add(challenge)
    await session.commit()
    if login_methods(user)[0] == "email":
        try:
            await _send_email_code(session, challenge, user, "signs you in")
        except AuthError:
            pass  # the user can press "send again" or use a recovery code
    return raw, challenge


async def _open_login(session: AsyncSession, raw: str) -> tuple[MfaChallenge, User]:
    row = (await session.execute(
        select(MfaChallenge, User)
        .join(User, User.id == MfaChallenge.user_id)
        .where(MfaChallenge.token_hash == hash_token(raw), MfaChallenge.purpose == "login")
    )).one_or_none()
    if row is None or row[0].expires_at <= utcnow() or not row[1].is_active:
        raise AuthError("This sign-in has expired. Sign in again.")
    return row.tuple()


async def challenge_user(session: AsyncSession, raw: str) -> User:
    return (await _open_login(session, raw))[1]


async def resend_login_email(session: AsyncSession, raw: str) -> None:
    challenge, user = await _open_login(session, raw)
    if "email" not in login_methods(user):
        raise AuthError("Email codes aren't available for this account")
    await _send_email_code(session, challenge, user, "signs you in")


async def verify_login(session: AsyncSession, raw: str, method: Method, code: str) -> User:
    """Check the second step; the challenge is used up on success."""
    challenge, user = await _open_login(session, raw)
    ok = False
    if method == "totp" and user.totp_secret:
        step = match_totp(crypto.decrypt(user.totp_secret), code, user.totp_last_step)
        if step is not None:
            user.totp_last_step = step
            ok = True
    elif method == "email" and user.mfa_email:
        ok = _email_code_ok(challenge, code)
    elif method == "recovery":
        ok = await _use_recovery_code(session, user, code)
        if ok:
            await session.flush()  # count without the code just used
            left = await recovery_codes_left(session, user.id)
            await notify(user, "A Bursa recovery code was used",
                         f"A recovery code was used to sign in. {left} codes are left.")

    if not ok:
        challenge.attempts += 1
        if challenge.attempts >= settings.mfa_max_attempts:
            await session.delete(challenge)
            await session.commit()
            raise AuthError("Too many wrong codes. Sign in again.")
        await session.commit()
        raise AuthError("That code isn't right. Check it and try again.")

    await session.delete(challenge)
    await session.commit()
    return user


# --------------------------------------------------------------------------- #
# Remembered devices
# --------------------------------------------------------------------------- #
async def trust_device(session: AsyncSession, user: User, user_agent: str | None) -> str:
    raw, digest = new_token()
    now = utcnow()
    session.add(TrustedDevice(
        token_hash=digest, user_id=user.id, created_at=now,
        expires_at=now + timedelta(days=settings.trusted_device_days),
        user_agent=(user_agent or "")[:255] or None,
    ))
    await session.commit()
    return raw


async def is_trusted(session: AsyncSession, user: User, raw: str | None) -> bool:
    if not raw:
        return False
    found = (await session.execute(
        select(TrustedDevice.id).where(
            TrustedDevice.token_hash == hash_token(raw),
            TrustedDevice.user_id == user.id,
            TrustedDevice.expires_at > utcnow(),
        )
    )).first()
    return found is not None


async def forget_devices(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(delete(TrustedDevice).where(TrustedDevice.user_id == user_id))
    return result.rowcount or 0  # type: ignore[attr-defined]


async def trusted_device_count(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count()).select_from(TrustedDevice).where(
            TrustedDevice.user_id == user_id, TrustedDevice.expires_at > utcnow()
        )
    )).scalar_one()


# --------------------------------------------------------------------------- #
# Turning methods on and off
# --------------------------------------------------------------------------- #
async def _first_method_codes(session: AsyncSession, user: User, had_2fa: bool) -> list[str] | None:
    """Recovery codes are created with the first method (shown once)."""
    if had_2fa and await recovery_codes_left(session, user.id):
        return None
    return await replace_recovery_codes(session, user)


async def begin_totp(session: AsyncSession, user: User) -> str:
    """A new secret to scan; it becomes active once a code from it is confirmed."""
    secret = new_totp_secret()
    user.totp_pending = crypto.encrypt(secret)
    await session.commit()
    return secret


async def confirm_totp(session: AsyncSession, user: User, code: str) -> list[str] | None:
    if not user.totp_pending:
        raise AuthError("Start the authenticator setup again")
    secret = crypto.decrypt(user.totp_pending)
    step = match_totp(secret, code, None)
    if step is None:
        raise AuthError("That code doesn't match. Check the time on your phone and try again.")
    had_2fa = user.has_2fa
    user.totp_secret, user.totp_pending, user.totp_last_step = user.totp_pending, None, step
    codes = await _first_method_codes(session, user, had_2fa)
    await session.commit()
    await notify(user, "Authenticator app added to Bursa",
                 "An authenticator app was set up for two-factor sign-in on your account.")
    return codes


async def begin_email(session: AsyncSession, user: User) -> None:
    """Send a code to the account email; entering it turns email codes on."""
    await session.execute(delete(MfaChallenge).where(
        MfaChallenge.user_id == user.id, MfaChallenge.purpose == "enroll_email"
    ))
    now = utcnow()
    challenge = MfaChallenge(
        token_hash=None, user_id=user.id, purpose="enroll_email", created_at=now,
        expires_at=now + timedelta(minutes=settings.mfa_code_minutes), attempts=0,
    )
    session.add(challenge)
    await session.flush()
    await _send_email_code(session, challenge, user, "turns on email codes for Bursa")


async def confirm_email(session: AsyncSession, user: User, code: str) -> list[str] | None:
    challenge = (await session.execute(
        select(MfaChallenge).where(
            MfaChallenge.user_id == user.id, MfaChallenge.purpose == "enroll_email",
            MfaChallenge.expires_at > utcnow(),
        )
    )).scalar_one_or_none()
    if challenge is None:
        raise AuthError("The code expired. Send a new one.")
    if not _email_code_ok(challenge, code):
        challenge.attempts += 1
        if challenge.attempts >= settings.mfa_max_attempts:
            await session.delete(challenge)
            await session.commit()
            raise AuthError("Too many wrong codes. Send a new one.")
        await session.commit()
        raise AuthError("That code isn't right")
    had_2fa = user.has_2fa
    user.mfa_email = True
    await session.delete(challenge)
    codes = await _first_method_codes(session, user, had_2fa)
    await session.commit()
    return codes


async def _check_password(user: User, password: str) -> None:
    if not verify_password(user, password):
        raise AuthError("Password is incorrect")


async def _after_removal(session: AsyncSession, user: User) -> None:
    if user.role == "admin" and not user.has_2fa:
        raise AuthError("Admins must keep two-factor authentication on")
    if not user.has_2fa:  # fully off: nothing left to fall back on
        await session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
        await forget_devices(session, user.id)


async def disable_method(
    session: AsyncSession, user: User, method: Literal["totp", "email"], password: str
) -> None:
    await _check_password(user, password)
    if method == "totp":
        user.totp_secret = user.totp_pending = user.totp_last_step = None
    else:
        user.mfa_email = False
    await _after_removal(session, user)
    await session.commit()
    label = "Authenticator app" if method == "totp" else "Email codes"
    await notify(user, f"{label} removed from Bursa sign-in",
                 f"{label} can no longer be used for two-factor sign-in on your account.")


async def regenerate_codes(session: AsyncSession, user: User, password: str) -> list[str]:
    await _check_password(user, password)
    if not user.has_2fa:
        raise AuthError("Turn on two-factor authentication first")
    codes = await replace_recovery_codes(session, user)
    await session.commit()
    await notify(user, "New Bursa recovery codes",
                 "New recovery codes were created; the old ones no longer work.")
    return codes


async def admin_reset(session: AsyncSession, user: User) -> None:
    """For a user who lost every method: turn 2FA off so they can sign in and set it up."""
    user.mfa_email = False
    user.totp_secret = user.totp_pending = user.totp_last_step = None
    await session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    await session.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user.id))
    await forget_devices(session, user.id)
    await session.commit()
    await notify(user, "Two-factor sign-in was reset",
                 "An admin turned off two-factor authentication on your account. "
                 "Set it up again from the account menu.")
