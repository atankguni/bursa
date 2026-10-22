"""
schemas.py
----------
Pydantic v2 response models for the public API surface.
"""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

# How the user invests: long-term fundamentals vs short-term (swing) price action.
InvestingStyle = Literal["investor", "trader"]


class StockBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    # IDX listing board; "Watchlist" = special monitoring (Papan Pemantauan Khusus).
    board: str | None = None


class RecommendationSummary(BaseModel):
    """Compact recommendation, attached to stock + watchlist rows."""

    score: float
    rating: str
    strength: str


class MarketStatusOut(BaseModel):
    """Current IDX trading state for the navbar indicator."""

    is_open: bool
    session: str
    timezone: str
    server_time: datetime
    next_change_at: datetime | None = None
    next_change_label: str = ""


class ProviderInfo(BaseModel):
    """A registered market-data provider and what it supports."""

    name: str
    capabilities: list[str]


class ProviderStat(BaseModel):
    """Lightweight outbound-call metrics per provider."""

    calls: int = 0
    calls_today: int = 0
    errors: int = 0
    last_error: str | None = None
    last_call_at: float | None = None


class ProvidersOut(BaseModel):
    """Active data providers (price + fundamentals are selected separately)."""

    price: str
    fundamentals: str
    available: list[ProviderInfo]
    metrics: dict[str, ProviderStat] = {}


class StatusOut(BaseModel):
    """Global status for the app footer."""

    server_time: datetime
    timezone: str
    session: str
    last_sync: datetime | None = None
    stocks_tracked: int = 0
    providers: dict[str, str] = {}
    calls_today: dict[str, int] = {}
    lot_size: int = 100


# --------------------------------------------------------------------------- #
# Portfolio
# --------------------------------------------------------------------------- #


class TransactionIn(BaseModel):
    """Payload for recording a buy/sell."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(default=0.0, ge=0)
    trade_date: date
    note: str | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    side: str
    quantity: float
    price: float
    fees: float
    trade_date: date
    note: str | None = None


class HoldingOut(BaseModel):
    board: str | None = None
    split_adjusted: bool = False
    """A current position with average-cost P/L."""

    ticker: str
    name: str
    quantity: float
    avg_cost: float
    price: float | None = None
    market_value: float | None = None
    invested: float
    unrealized_pl: float | None = None
    unrealized_pl_pct: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    weight: float | None = None
    projected_income: float | None = None  # after dividend tax
    dividends_received: float = 0.0  # since the first trade, after tax


class PortfolioTotals(BaseModel):
    invested: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float | None = None
    day_change: float
    day_change_pct: float | None = None
    realized_pl: float
    projected_income: float = 0.0  # after dividend tax
    # Selling everything now would cost about this (sell fee + tax).
    exit_costs: float = 0.0
    # Cash dividends the trades were entitled to (held before the ex-date), after tax.
    dividends_received: float = 0.0
    # Unrealized P/L after exit costs + realized P/L + dividends received.
    total_return: float = 0.0


class PortfolioOut(BaseModel):
    totals: PortfolioTotals
    holdings: list[HoldingOut]


class EquityPoint(BaseModel):
    date: date
    value: float
    return_pct: float | None = None  # cumulative time-weighted return, %
    benchmark_pct: float | None = None  # IHSG cumulative change over the same days, %


# --------------------------------------------------------------------------- #
# Screener / search / market overview
# --------------------------------------------------------------------------- #


class SearchResultOut(BaseModel):
    symbol: str
    name: str
    exchange: str = ""
    type: str = ""


class TrackStockIn(BaseModel):
    ticker: str
    name: str | None = None


class ScreenerRow(BaseModel):
    ticker: str
    name: str
    indices: list[str] = []
    sector: str | None = None
    price: float | None = None
    change_percent: float | None = None
    pbv: float | None = None
    roe: float | None = None
    score: float | None = None
    rating: str | None = None
    strength: str | None = None
    has_fundamentals: bool = False
    board: str | None = None


class ScreenerPage(BaseModel):
    """One page of screener results plus the total match count (for pagination)."""

    items: list[ScreenerRow]
    total: int
    limit: int
    offset: int


class SyncStatusOut(BaseModel):
    """Progress of the background 'sync missing data' job."""

    running: bool
    mode: str = "batch"  # "batch" | "all"
    note: str | None = None
    total: int = 0
    done: int = 0
    remaining: int = 0
    last_error: str | None = None
    # Stocks that still have no fundamentals (across the whole universe).
    missing: int = 0


class SyncStartOut(BaseModel):
    """Response of starting a screener sync."""

    running: bool
    queued: int = 0
    total: int = 0
    remaining: int = 0


class MoverOut(BaseModel):
    ticker: str
    name: str
    price: float | None = None
    change_percent: float | None = None


class SectorOut(BaseModel):
    sector: str
    count: int
    avg_change_percent: float


class MarketOverviewOut(BaseModel):
    up: int
    down: int
    flat: int
    top_gainers: list[MoverOut]
    top_losers: list[MoverOut]
    sectors: list[SectorOut]


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #

AlertType = Literal[
    "price_above", "price_below", "pct_change", "rating_change",
    # Expected dividend: threshold = days ahead of the (estimated) cum date, default 3.
    "dividend_soon",
]


class AlertIn(BaseModel):
    ticker: str
    type: AlertType
    threshold: float | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    type: str
    threshold: float | None = None
    active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime


class AlertEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    ticker: str
    triggered_at: datetime
    value: float | None = None
    message: str


# --------------------------------------------------------------------------- #
# Valuation & dividends
# --------------------------------------------------------------------------- #


class ValuationOut(BaseModel):
    ticker: str
    pbv: float | None = None
    pbv_min: float | None = None
    pbv_max: float | None = None
    pbv_percentile: float | None = None
    roe: float | None = None
    roe_percentile: float | None = None
    years: list[int] = []
    window_days: int = 0


class DividendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ex_date: date
    amount: float


class DividendSummary(BaseModel):
    ticker: str
    trailing_dps: float = 0.0
    yield_percent: float | None = None
    history: list[DividendOut] = []


class OfficerOut(BaseModel):
    name: str
    title: str | None = None


class CompanyOut(BaseModel):
    """Company profile / board information for the detail modal."""

    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    employees: int | None = None
    website: str | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    officers: list[OfficerOut] = []


class StockOut(StockBase):
    """A tracked stock enriched with its latest quote + daily change."""

    id: int
    indices: list[str] = []
    last_price: float | None = None
    previous_close: float | None = None
    change: float | None = None          # absolute point change vs prev close
    change_percent: float | None = None  # percentage change vs prev close
    volume: int | None = None
    updated_at: datetime | None = None
    recommendation: RecommendationSummary | None = None


class CatalogRow(BaseModel):
    """A row in the full IDX catalog browse list."""

    ticker: str
    name: str
    board: str | None = None
    tracked: bool = False
    indices: list[str] = []
    last_price: float | None = None
    change_percent: float | None = None


class CatalogPage(BaseModel):
    """One page of the catalog plus the total match count (for pagination)."""

    items: list[CatalogRow]
    total: int
    limit: int
    offset: int


class PricePoint(BaseModel):
    """A single OHLCV bar for charting."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class SplitOut(BaseModel):
    ex_date: date
    ratio: float


class StockHistory(BaseModel):
    """Full history payload for one ticker."""

    ticker: str
    name: str
    indices: list[str]
    interval: str
    points: list[PricePoint]
    splits: list[SplitOut] = []  # for chart markers


class FundamentalOut(BaseModel):
    """One fiscal year of financial figures, converted to IDR (raw units)."""

    model_config = ConfigDict(from_attributes=True)

    fiscal_year: int
    financial_currency: str | None = None
    total_shares: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    equity: float | None = None
    source: str | None = None  # "statements" | "summary" (None = statements)


class DerivedMetrics(BaseModel):
    """Valuation ratios computed against the latest price."""

    market_cap: float | None = None
    book_value: float | None = None
    pbv: float | None = None   # price-to-book value
    roe: float | None = None   # return on equity (latest year, fraction)


# --------------------------------------------------------------------------- #
# Recommendation
# --------------------------------------------------------------------------- #


class FactorOut(BaseModel):
    """One scored factor: raw value + cross-sectional percentile score."""

    name: str
    value: float | None = None
    score: float | None = None   # 0-100 percentile (higher = better)
    label: str = ""              # human-readable value


class CategoryOut(BaseModel):
    """A weighted group of factors."""

    name: str
    weight: float
    score: float | None = None


class RecommendationOut(BaseModel):
    """Full buy-signal breakdown for one ticker."""

    ticker: str
    score: float                 # 0-100 composite
    rating: str                  # Strong Buy / Buy / Hold / Reduce / Avoid
    strength: str                # Weak / Moderate / Strong / Very Strong
    coverage: float              # fraction of factors with data
    categories: list[CategoryOut] = []
    reasons: list[str] = []
    disclaimer: str = ""
    style: InvestingStyle = "investor"  # which model produced this score


class RatingRecordOut(BaseModel):
    rating: str      # internal code (Strong Buy ... Avoid)
    n: int           # stock-dates with this rating
    beat: float      # share that beat that date's median stock (0.5 = coin flip)


class BacktestRecordOut(BaseModel):
    start: str                   # first / last as-of date (YYYY-MM-DD)
    end: str
    universe: str                # which stocks were judged, in words
    ic: float                    # mean rank correlation of score vs. later return
    years: dict[str, float] = {}  # the same, per calendar year
    ratings: list[RatingRecordOut] = []
    generated: str = ""


class LiveRecordOut(BaseModel):
    since: date | None = None    # first recorded day
    days: int = 0                # days recorded
    matured_days: int = 0        # of which the horizon has passed
    ready_on: date | None = None  # roughly when the first result arrives
    ratings: list[RatingRecordOut] = []


class TrackRecordOut(BaseModel):
    """How past ratings of this style did over its main horizon."""

    style: InvestingStyle
    horizon: str                 # "3m" / "4w"
    backtest: BacktestRecordOut | None = None
    live: LiveRecordOut = LiveRecordOut()


class WatchlistItemOut(StockBase):
    """A watchlist row: stock + latest price + latest fundamentals + ratios."""

    id: int
    indices: list[str] = []
    added_at: datetime | None = None
    last_price: float | None = None
    change_percent: float | None = None
    fundamental: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()
    recommendation: RecommendationSummary | None = None


class FundamentalsResponse(BaseModel):
    """Yearly fundamentals series + derived metrics for one ticker."""

    ticker: str
    name: str
    yearly: list[FundamentalOut]
    latest: FundamentalOut | None = None
    metrics: DerivedMetrics = DerivedMetrics()


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantChatIn(BaseModel):
    """The visible conversation (oldest first); the last turn is the new question."""

    messages: list[ChatTurn] = Field(min_length=1, max_length=40)
    # Saved chat this continues; None starts a new one. Ignored when saving is off.
    chat_id: int | None = None
    context: str | None = Field(None, max_length=200)  # e.g. "the BBCA.JK detail view"


class AssistantChatOut(BaseModel):
    reply: str
    provider: str = ""
    model: str
    tools_used: list[str] = []
    remaining_today: int
    chat_id: int | None = None  # None when the user doesn't save chats


class AssistantStatusOut(BaseModel):
    configured: bool
    models: list[str]
    setup_hint: str = ""  # what to set when not configured (e.g. GEMINI_API_KEY)
    personal_data: bool
    remaining_today: int
    daily_limit: int
    save_chats: bool = True
    chat_days: int = 90  # saved chats are deleted this long after their last message


class ChatSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant"]
    content: str
    tools_used: list[str] | None = None
    created_at: datetime


class ChatDetailOut(ChatSummaryOut):
    messages: list[ChatMessageOut]


_Name = Annotated[str, StringConstraints(max_length=32)]


class HiddenColumns(BaseModel):
    home: list[_Name] = Field(default_factory=list, max_length=30)
    watchlist: list[_Name] = Field(default_factory=list, max_length=30)


class DisplaySettings(BaseModel):
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


class TradingCosts(BaseModel):
    """
    The user's broker costs, in percent. Defaults are typical for Indonesian
    online brokers: 0.15% to buy, 0.25% to sell (including the 0.1% final tax on
    share sales), and the 10% final tax on dividends for residents.
    """

    buy_fee_pct: float = Field(default=0.15, ge=0, le=5)
    sell_fee_pct: float = Field(default=0.25, ge=0, le=5)
    dividend_tax_pct: float = Field(default=10.0, ge=0, le=50)


class PreferencesOut(BaseModel):
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


class PreferencesIn(BaseModel):
    """Partial update: only the fields that are sent change."""

    investing_style: InvestingStyle | None = None
    assistant_personal_data: bool | None = None
    assistant_save_chats: bool | None = None  # False also deletes saved chats
    display: DisplaySettings | None = None  # replaces the saved settings
    # Only ever moves forward, so a device with an older list can't un-read alerts.
    alerts_seen_at: datetime | None = None
    trading_costs: TradingCosts | None = None
    daily_digest: bool | None = None


class IndexOut(BaseModel):
    """One IDX stock index (indeks saham) with its latest value."""

    code: str
    name: str
    group: str
    last: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    updated_at: datetime | None = None
    has_history: bool = False
    history_since: date | None = None


class IndexBarOut(BaseModel):
    """Daily index bar, shaped like PricePoint so the stock chart can draw it."""

    timestamp: date
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class IndexHistoryOut(BaseModel):
    code: str
    name: str
    has_history: bool
    points: list[IndexBarOut]


class HoldingRiskOut(BaseModel):
    ticker: str
    weight: float
    sector: str
    beta: float | None = None


class SectorWeightOut(BaseModel):
    sector: str
    weight: float


class PortfolioRiskOut(BaseModel):
    """Concentration, sector exposure, beta vs IHSG, stress test, drawdown (all in %)."""

    holdings: list[HoldingRiskOut]
    sectors: list[SectorWeightOut]
    effective_holdings: float | None = None
    top_weight: float | None = None
    top3_weight: float | None = None
    beta: float | None = None
    stress_ihsg_pct: float
    stress_portfolio_pct: float | None = None
    last_day_portfolio_pct: float | None = None
    last_day_ihsg_pct: float | None = None
    max_drawdown_pct: float | None = None
    warnings: list[str] = []


class NotificationStatusOut(BaseModel):
    """Which out-of-app channels are configured (and whether a test was delivered)."""

    telegram: bool
    delivered: bool | None = None


class ExpectedDividendOut(BaseModel):
    """A projected (not announced) dividend, from last year's ex-date."""

    ticker: str
    name: str
    expected_ex_date: date
    based_on: date
    amount_per_share: float
    regular: bool
    shares_held: float | None = None
    expected_income: float | None = None
    in_portfolio: bool
    in_watchlist: bool


class MailStatusOut(BaseModel):
    """Email delivery setup (no secrets: provider name and sender only)."""

    configured: bool
    provider: str | None
    sender: str | None
    recipients: int  # default recipients in MAIL_TO
    setup_hint: str = ""  # what to set when not (fully) configured


class MailTestOut(BaseModel):
    delivered: bool
    message_id: str | None = None



# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
Role = Literal["user", "admin"]


class MeOut(BaseModel):
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


TwoFactorMethod = Literal["totp", "email", "recovery"]


class TwoFactorChallengeOut(BaseModel):
    """The password was right; a second step is needed."""

    token: str  # identifies this sign-in attempt for /api/auth/2fa/verify
    methods: list[TwoFactorMethod]  # usable now, preferred first
    email_hint: str  # "l***@example.com"
    email_sent: bool  # a code was emailed already


class LoginOut(BaseModel):
    """Either signed in (`user`) or a second step is needed (`two_factor`)."""

    user: MeOut | None = None
    two_factor: TwoFactorChallengeOut | None = None


class TwoFactorVerifyIn(BaseModel):
    token: str = Field(max_length=64)
    method: TwoFactorMethod
    code: str = Field(max_length=32)
    remember_device: bool = False


class TwoFactorTokenIn(BaseModel):
    token: str = Field(max_length=64)


class TwoFactorStatusOut(BaseModel):
    totp: bool
    email: bool
    email_available: bool  # email is set up on the server
    recovery_codes_left: int
    trusted_devices: int
    required: bool  # admins must keep 2FA on


class TotpSetupOut(BaseModel):
    secret: str  # for typing into the app when the QR can't be scanned
    uri: str  # otpauth:// link (opens the app on a phone)
    qr_svg: str


class CodeIn(BaseModel):
    code: str = Field(max_length=32)


class PasswordConfirmIn(BaseModel):
    password: str = Field(max_length=256)


class RecoveryCodesOut(BaseModel):
    """Shown once: only keyed hashes are stored."""

    recovery_codes: list[str] | None = None


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class AuthOptionsOut(BaseModel):
    """What the sign-in screens can offer (public)."""

    password_reset_by_email: bool  # "Forgot password?" needs email to be set up
    password_min_length: int
    password_min_score: int  # zxcvbn score 0-4


class InviteInfoOut(BaseModel):
    email: str | None  # None = setup invite: the first admin chooses the email
    role: Role


class AcceptInviteIn(BaseModel):
    name: str = Field(max_length=80)
    password: str = Field(max_length=256)
    email: str | None = Field(None, max_length=254)  # setup invite only


class ResetRequestIn(BaseModel):
    email: str = Field(max_length=254)


class ResetPasswordIn(BaseModel):
    password: str = Field(max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: Role
    is_active: bool
    has_2fa: bool
    created_at: datetime
    last_login_at: datetime | None


class UserUpdateIn(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class InviteIn(BaseModel):
    email: str = Field(max_length=254)
    role: Role = "user"


class PendingInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
    created_at: datetime
    expires_at: datetime


class LinkOut(BaseModel):
    """A one-time invite / reset link, shown once to the admin who made it."""

    link: str
    emailed: bool  # also sent by email (when email is set up)
