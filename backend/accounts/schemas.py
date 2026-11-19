"""
accounts/schemas.py
-------------------
API models (Pydantic) for users, sign-in and per-user settings.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from schemas import InvestingStyle, Schema

# What a pending second sign-in step is for (accounts/two_factor).
MfaPurpose = Literal["login", "enroll_email"]

# Entries of the account activity log (accounts/security_log).
SecurityEventKind = Literal[
    "account_created",
    "sign_in",
    "sign_in_failed",
    "session_revoked",
    "other_sessions_revoked",
    "password_changed",
    "password_reset",
    "reset_link_created",
    "two_factor_enabled",
    "two_factor_disabled",
    "two_factor_reset",
    "recovery_codes_regenerated",
    "trusted_devices_forgotten",
    "account_disabled",
    "account_enabled",
    "role_changed",
    "session_unlocked",
    "name_changed",
    "email_change_requested",
    "email_changed",
    "portfolio_cleared",
]

# Minutes without use before a browser locks (0 = never), see config.lock_*.
LockMinutes = Literal[0, 5, 15, 30, 60]


_Name = Annotated[str, StringConstraints(max_length=32)]


class HiddenColumns(Schema):
    home: list[_Name] = Field(default_factory=list, max_length=30)
    watchlist: list[_Name] = Field(default_factory=list, max_length=30)


class DisplaySettings(Schema):
    """
    The data/display part of the Settings menu, saved per user so it follows
    them across devices. Field names are camelCase on the wire, as the frontend
    keeps them. Appearance (theme, accent, ...) and "hide portfolio values" stay
    per device in the browser.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    default_indexes: list[_Name] = Field(default_factory=lambda: ["LQ45"], max_length=50)
    chart_type: Literal["candle", "line"] = "line"
    chart_range: Literal["1d", "1m"] = "1d"
    auto_refresh: bool = True
    refresh_seconds: int = Field(60, ge=10, le=3600)
    number_format: Literal["compact", "full"] = "compact"
    colorize_changes: bool = True
    hidden_columns: HiddenColumns = Field(default_factory=HiddenColumns)
    # 1,234.50 ("en") or the Indonesian 1.234,50 ("id").
    number_locale: Literal["en", "id"] = "en"
    # 16 Nov 2026 ("text") or 16/11/2026 ("numeric").
    date_style: Literal["text", "numeric"] = "text"
    # What opens after signing in.
    start_page: Literal["home", "watchlist", "portfolio"] = "home"
    # Portfolio amounts start hidden each time the page opens.
    hide_values_on_open: bool = False
    # The trade form's quantity unit.
    trade_unit: Literal["lots", "shares"] = "lots"


class TradingCosts(Schema):
    """
    The user's broker costs, in percent. Defaults are typical for Indonesian
    online brokers: 0.1513% to buy, 0.2513% to sell (including the 0.1% final tax
    on share sales), and the 10% final tax on dividends for residents.
    """

    buy_fee_pct: float = Field(default=0.1513, ge=0, le=5)
    sell_fee_pct: float = Field(default=0.2513, ge=0, le=5)
    dividend_tax_pct: float = Field(default=10.0, ge=0, le=50)


# Indices with a full daily history (market/indices.py), so a portfolio can be
# compared with them over any period.
Benchmark = Literal["COMPOSITE", "LQ45", "JII"]

_Clock = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class QuietHours(Schema):
    """No alert emails between `start` and `end` (Jakarta time; may cross midnight).
    Emails due in that time wait and are sent together when it ends."""

    start: _Clock = "22:00"
    end: _Clock = "07:00"


class RiskLimits(Schema):
    """The Risk tab warns when one stock / one sector is above these (% of the portfolio)."""

    stock_pct: float = Field(default=25.0, ge=5, le=100)
    sector_pct: float = Field(default=40.0, ge=5, le=100)


class PreferencesOut(Schema):
    """Server-side preferences of the signed-in user."""

    investing_style: InvestingStyle = "investor"
    # Opt-in: the AI assistant may read the watchlist and portfolio.
    assistant_personal_data: bool = False
    # Keep assistant chats (for ASSISTANT_CHAT_DAYS) so they can be continued.
    assistant_save_chats: bool = True
    # None until first saved (the browser then uploads what it had locally).
    display: DisplaySettings | None = None
    # Alert events up to this time were seen (the navbar bell's unread count).
    alerts_seen_at: datetime | None = None
    trading_costs: TradingCosts = Field(default_factory=TradingCosts)
    daily_digest: bool = False  # the summary email after the close (opt-in)
    # Lock this browser after this many minutes without use (0 = never).
    lock_minutes: int = 15
    # Email each triggered alert (opt-in), outside the quiet hours if set.
    alert_emails: bool = False
    quiet_hours: QuietHours | None = None
    benchmark: Benchmark = "COMPOSITE"
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)


class PreferencesIn(Schema):
    """Partial update: only the fields that are sent change."""

    investing_style: InvestingStyle | None = None
    assistant_personal_data: bool | None = None
    assistant_save_chats: bool | None = None  # False also deletes saved chats
    display: DisplaySettings | None = None  # replaces the saved settings
    # Only ever moves forward, so a device with an older list can't un-read alerts.
    alerts_seen_at: datetime | None = None
    trading_costs: TradingCosts | None = None
    daily_digest: bool | None = None
    lock_minutes: LockMinutes | None = None
    alert_emails: bool | None = None
    # Sending the field with null turns quiet hours off (see quiet_hours_set).
    quiet_hours: QuietHours | None = None
    benchmark: Benchmark | None = None
    risk_limits: RiskLimits | None = None

    @property
    def quiet_hours_set(self) -> bool:
        """Whether quiet_hours was sent (null included), not just left out."""
        return "quiet_hours" in self.model_fields_set


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
Role = Literal["user", "admin"]


class MeOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: Role
    has_2fa: bool
    # Admin without 2FA: everything but the 2FA setup answers 403 until it's done.
    mfa_setup_required: bool
    # The password is too guessable or was leaked (checked at sign-in).
    password_weak: bool
    # Admin with a weak password: everything but changing it answers 403.
    password_change_required: bool
    # Idle too long: everything but /me, unlock, lock and sign-out answers 423
    # until the password is entered again.
    locked: bool = False
    created_at: datetime


class UnlockIn(Schema):
    password: str = Field(max_length=1024)


TwoFactorMethod = Literal["totp", "email", "recovery"]


class TwoFactorChallengeOut(Schema):
    """The password was right; a second step is needed."""

    token: str  # identifies this sign-in attempt for /api/auth/2fa/verify
    methods: list[TwoFactorMethod]  # usable now, preferred first
    email_hint: str  # "l***@example.com"
    email_sent: bool  # a code was emailed already


class LoginOut(Schema):
    """Either signed in (`user`) or a second step is needed (`two_factor`)."""

    user: MeOut | None = None
    two_factor: TwoFactorChallengeOut | None = None


class TwoFactorVerifyIn(Schema):
    token: str = Field(max_length=64)
    method: TwoFactorMethod
    code: str = Field(max_length=32)
    remember_device: bool = False


class TwoFactorTokenIn(Schema):
    token: str = Field(max_length=64)


class TwoFactorStatusOut(Schema):
    totp: bool
    email: bool
    email_available: bool  # email is set up on the server
    recovery_codes_left: int
    trusted_devices: int
    required: bool  # admins must keep 2FA on


class TotpSetupOut(Schema):
    secret: str  # for typing into the app when the QR can't be scanned
    uri: str  # otpauth:// link (opens the app on a phone)
    qr_svg: str


class CodeIn(Schema):
    code: str = Field(max_length=32)


class PasswordConfirmIn(Schema):
    password: str = Field(max_length=256)


class RecoveryCodesOut(Schema):
    """Shown once: only keyed hashes are stored."""

    recovery_codes: list[str] | None = None


class LoginIn(Schema):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class PasswordChangeIn(Schema):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class AuthOptionsOut(Schema):
    """What the sign-in screens can offer (public)."""

    password_reset_by_email: bool  # "Forgot password?" needs email to be set up
    password_min_length: int
    password_min_score: int  # zxcvbn score 0-4


class InviteInfoOut(Schema):
    email: str | None  # None = setup invite: the first admin chooses the email
    role: Role


class AcceptInviteIn(Schema):
    name: str = Field(max_length=80)
    password: str = Field(max_length=256)
    email: str | None = Field(None, max_length=254)  # setup invite only


class ResetRequestIn(Schema):
    email: str = Field(max_length=254)


class ResetPasswordIn(Schema):
    password: str = Field(max_length=256)


class UserOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: Role
    is_active: bool
    has_2fa: bool
    created_at: datetime
    last_login_at: datetime | None


class UserUpdateIn(Schema):
    role: Role | None = None
    is_active: bool | None = None


class InviteIn(Schema):
    email: str = Field(max_length=254)
    role: Role = "user"


class PendingInviteOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
    created_at: datetime
    expires_at: datetime


class LinkOut(Schema):
    """A one-time invite / reset link, shown once to the admin who made it."""

    link: str
    emailed: bool  # also sent by email (when email is set up)


# --------------------------------------------------------------------------- #
# Signed-in devices and account activity
# --------------------------------------------------------------------------- #
class SessionOut(Schema):
    id: int
    device: str  # "Chrome on macOS"
    ip: str | None
    created_at: datetime  # signed in
    last_seen_at: datetime  # last used (updated every few minutes)
    current: bool  # the browser asking


class SecurityEventOut(Schema):
    id: int
    kind: SecurityEventKind
    at: datetime
    ip: str | None
    device: str
    new_device: bool  # a sign-in from a browser this account hadn't used
    detail: str | None


class AdminSecurityEventOut(SecurityEventOut):
    user_id: int
    user_name: str
    user_email: str


# --------------------------------------------------------------------------- #
# Your profile and account (accounts/routes/account.py)
# --------------------------------------------------------------------------- #
class NameIn(Schema):
    name: str = Field(max_length=200)


class EmailChangeIn(Schema):
    new_email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class EmailChangeOut(Schema):
    """A change waiting for its confirmation link to be opened."""

    new_email: str


class DeleteAccountIn(Schema):
    password: str = Field(max_length=256)
    # Typed by the user, so a stray click can't delete an account.
    confirm: Literal["DELETE"]


class ClearPortfolioIn(Schema):
    password: str = Field(max_length=256)
