"""
accounts/models.py
------------------
Tables for users, sign-in and per-user settings. Conventions: models.py.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from accounts.schemas import MfaPurpose, Role, SecurityEventKind
from database import Base
from db.columns import created_at_column, updated_at_column, user_fk
from db.types import UTCDateTime, one_of
from schemas import InvestingStyle


# --------------------------------------------------------------------------- #
# Users and sign-in
# --------------------------------------------------------------------------- #
class User(Base):
    """An account. Invite-only: created by accepting an Invite."""

    __tablename__ = "users"
    __table_args__ = (one_of("role", Role),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Stored lower-cased (accounts/auth.normalize_email).
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(String(8), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Two-factor authentication (accounts/two_factor.py). Either or both methods.
    mfa_email: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Authenticator-app secret, encrypted (accounts/crypto.py). Pending = shown
    # as a QR code but not confirmed with a code yet.
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_pending: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Last accepted time step: each authenticator code works only once.
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # The password failed today's policy (too guessable or leaked) when last
    # checked: at sign-in, the only time the plain password is seen. Cleared by
    # changing it.
    password_weak: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    @property
    def has_2fa(self) -> bool:
        return self.mfa_email or self.totp_secret is not None

    @property
    def mfa_setup_required(self) -> bool:
        """2FA is required for admins: until set up, they can only reach the setup."""
        return self.role == "admin" and not self.has_2fa

    @property
    def password_change_required(self) -> bool:
        """Admins with a weak password must change it before anything else."""
        return self.role == "admin" and self.password_weak

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.email} ({self.role})>"


class UserSettings(Base):
    """
    One row per user (created on first save; missing = all defaults). Background
    work (alerts, digest) reads the same settings as the user's pages.
    """

    __tablename__ = "user_settings"
    __table_args__ = (one_of("investing_style", InvestingStyle),)

    user_id: Mapped[int] = user_fk(primary_key=True)
    investing_style: Mapped[InvestingStyle] = mapped_column(
        String(8), default="investor", server_default="investor", nullable=False
    )
    # NULL = not chosen yet: the `assistant_personal_data` server setting applies.
    assistant_personal_data: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assistant_save_chats: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    daily_digest: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Newest alert event the user has seen (only ever moves forward).
    alerts_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Documents validated by their Pydantic models (accounts.schemas.DisplaySettings,
    # TradingCosts); NULL = never saved (defaults apply).
    display: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trading_costs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = updated_at_column()


class RecoveryCode(Base):
    """A single-use backup code for 2FA (keyed hash only: accounts/crypto.py)."""

    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = user_fk(index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class MfaChallenge(Base):
    """
    A pending second step: after the password at sign-in (`purpose="login"`,
    found by its token), or confirming email as a 2FA method ("enroll_email").
    Holds the emailed code's keyed hash and counts wrong attempts.
    """

    __tablename__ = "mfa_challenges"
    __table_args__ = (one_of("purpose", MfaPurpose),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    user_id: Mapped[int] = user_fk(index=True)
    purpose: Mapped[MfaPurpose] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class TrustedDevice(Base):
    """A browser that skips the 2FA step for a while (cookie token, hash stored)."""

    __tablename__ = "trusted_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = user_fk(index=True)
    created_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class UserSession(Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = user_fk(index=True)
    created_at: Mapped[datetime] = created_at_column()
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


class Invite(Base):
    """A one-time sign-up link for an email address (only the token's hash is stored)."""

    __tablename__ = "invites"
    __table_args__ = (one_of("role", Role),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    role: Mapped[Role] = mapped_column(String(8), default="user", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class PasswordReset(Base):
    """A one-time password-reset link (only the token's hash is stored)."""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = user_fk(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class LoginFailure(Base):
    """A failed sign-in, counted per email and per IP for throttling
    (accounts/auth.py). Rows older than the window are purged."""

    __tablename__ = "login_failures"
    __table_args__ = (Index("ix_login_failures_key_at", "key", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(300), nullable=False)  # "email:..." / "ip:..."
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class SecurityEvent(Base):
    """
    One entry of an account's activity log (accounts/security_log): sign-ins,
    password and 2FA changes, signed-out devices, admin changes. Deleted with the
    account, or after SECURITY_LOG_DAYS.
    """

    __tablename__ = "security_events"
    __table_args__ = (
        one_of("kind", SecurityEventKind),
        Index("ix_security_events_user_id_at", "user_id", "at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = user_fk()
    kind: Mapped[SecurityEventKind] = mapped_column(String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # SHA-256 of the browser's device cookie (sign-ins only).
    device_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_device: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # Short context: the 2FA method, "by <admin>", "wrong password", ...
    detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
