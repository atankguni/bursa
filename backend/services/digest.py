"""
services/digest.py
------------------
The daily summary email, sent after the close to users who turned it on
(Settings → Investing): the portfolio's day, the biggest movers among holdings
and the watchlist, signal changes, expected dividends (estimated cum dates) and
how many alerts fired. Nothing is sent to someone with no holdings or watchlist,
or on a day the market was closed.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from config import settings
from mail.base import Email
from mail.templates import layout
from models import AlertEvent, RatingSnapshot, User, Watchlist
from schemas import PortfolioTotals, Rating
from services.dividend_calendar import UpcomingDividend, next_expected
from services.market_clock import is_trading_day
from services.portfolio import build_portfolio
from services.preferences import get_investing_style, users_with_digest
from services.prices import latest_daily
from services.recommendation import rating_label

log = logging.getLogger("bursa.digest")

MOVERS = 5
DIVIDEND_DAYS = 10


@dataclass
class Mover:
    ticker: str
    change_pct: float
    held: bool


@dataclass
class SignalChange:
    ticker: str
    before: Rating
    after: Rating


@dataclass
class Digest:
    day: date
    totals: PortfolioTotals | None  # None without holdings
    movers: list[Mover] = field(default_factory=list[Mover])
    signals: list[SignalChange] = field(default_factory=list[SignalChange])
    dividends: list[tuple[str, UpcomingDividend]] = field(
        default_factory=list[tuple[str, UpcomingDividend]]
    )
    alerts: int = 0


async def build_digest(session: AsyncSession, user: User, day: date) -> Digest | None:
    """The summary for `day`, or None when the user follows no stocks."""
    totals, holdings = await build_portfolio(session, user.id)
    held = {h.ticker for h in holdings}
    watched = set(
        (await session.execute(
            select(Watchlist.ticker).where(Watchlist.user_id == user.id)
        )).scalars().all()
    )
    tickers = sorted(held | watched)
    if not tickers:
        return None

    quotes = await latest_daily(session, tickers)
    movers: list[Mover] = []
    for t, q in quotes.items():
        close, prev, at = q.get("close"), q.get("prev_close"), q.get("updated_at")
        if close is not None and prev and at is not None and at.date() == day:
            movers.append(Mover(t, (close - prev) / prev * 100, t in held))
    movers.sort(key=lambda m: abs(m.change_pct), reverse=True)

    # Signal changes: the day's recorded ratings vs the previous recorded day.
    style = await get_investing_style(session, user.id)
    days = (
        await session.execute(
            select(RatingSnapshot.day)
            .where(RatingSnapshot.style == style, RatingSnapshot.day <= day)
            .group_by(RatingSnapshot.day)
            .order_by(RatingSnapshot.day.desc())
            .limit(2)
        )
    ).scalars().all()
    signals: list[SignalChange] = []
    if len(days) == 2 and days[0] == day:
        rows = (
            await session.execute(
                select(RatingSnapshot.day, RatingSnapshot.ticker, RatingSnapshot.rating).where(
                    RatingSnapshot.style == style,
                    RatingSnapshot.day.in_(days),
                    RatingSnapshot.ticker.in_(tickers),
                )
            )
        ).all()
        by_day: dict[date, dict[str, Rating]] = {d: {} for d in days}
        for d, t, r in rows:
            by_day[d][t] = r
        for t, now_rating in sorted(by_day[days[0]].items()):
            before = by_day[days[1]].get(t)
            if before and before != now_rating:
                signals.append(SignalChange(t, before, now_rating))

    upcoming = await next_expected(session, tickers, day, DIVIDEND_DAYS)
    start = datetime.combine(day, time(), ZoneInfo(settings.timezone))
    alerts = (
        await session.execute(
            select(func.count()).select_from(AlertEvent).where(
                AlertEvent.user_id == user.id,
                AlertEvent.triggered_at >= start,
            )
        )
    ).scalar_one()

    return Digest(
        day=day,
        totals=totals if holdings else None,
        movers=movers[:MOVERS],
        signals=signals,
        dividends=sorted(upcoming.items(), key=lambda kv: kv[1]["cum_date"]),
        alerts=alerts,
    )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _rp(v: float) -> str:
    return f"Rp {v:,.0f}"


def _signed_rp(v: float) -> str:
    return f"{'+' if v >= 0 else '−'}Rp {abs(v):,.0f}"


def subject(d: Digest) -> str:
    parts = [f"Bursa · {d.day:%a %d %b}"]
    if d.totals and d.totals.day_change_pct is not None:
        parts.append(f"portfolio {d.totals.day_change_pct:+.2f}%")
    if d.signals:
        parts.append(f"{len(d.signals)} signal change{'s' * (len(d.signals) != 1)}")
    if d.dividends:
        parts.append(f"{len(d.dividends)} dividend{'s' * (len(d.dividends) != 1)} soon")
    return parts[0] + (": " + ", ".join(parts[1:]) if len(parts) > 1 else "")


def sections(d: Digest) -> list[tuple[str, list[str]]]:
    """(heading, lines) in plain text; the HTML version escapes the same lines."""
    out: list[tuple[str, list[str]]] = []
    if d.totals:
        t = d.totals
        pct = f" ({t.day_change_pct:+.2f}%)" if t.day_change_pct is not None else ""
        out.append(("Portfolio", [
            f"Value {_rp(t.market_value)}, today {_signed_rp(t.day_change)}{pct}",
            f"Total return so far {_signed_rp(t.total_return)} "
            "(after selling costs, with dividends)",
        ]))
    if d.movers:
        out.append(("Biggest moves", [
            f"{m.ticker} {m.change_pct:+.2f}%{' (you hold it)' if m.held else ''}"
            for m in d.movers
        ]))
    if d.signals:
        out.append(("Signal changes", [
            f"{s.ticker}: {rating_label(s.before)} → {rating_label(s.after)}"
            for s in d.signals
        ]))
    if d.dividends:
        out.append(("Dividends coming up (estimated from last year)", [
            f"{t}: last day to buy ≈ {u['cum_date']:%a %d %b}, "
            f"about {_rp(u['amount_per_share'])}/share"
            for t, u in d.dividends
        ]))
    if d.alerts:
        out.append(("Alerts", [f"{d.alerts} alert{'s' * (d.alerts != 1)} fired today"]))
    return out


def render(d: Digest, name: str) -> Email:
    parts = sections(d)
    if not parts:
        parts = [("Quiet day", ["Nothing moved for the stocks you follow."])]
    link = f"{settings.public_url.rstrip('/')}/"
    off = "Turn this email off in Settings → Investing."
    text = "\n\n".join(
        [f"Hi {name}, here's your day on the IDX."]
        + [f"{h}\n" + "\n".join(f"- {line}" for line in lines) for h, lines in parts]
        + [f"Open Bursa: {link}", "Signals are heuristics, not financial advice. " + off]
    )
    body = f"<p style=\"margin:0 0 12px;\">Hi {escape(name)}, here's your day on the IDX.</p>"
    for heading, lines in parts:
        body += (
            f"<p style=\"margin:16px 0 4px;font-weight:600;\">{escape(heading)}</p>"
            + "".join(f"<div>• {escape(line)}</div>" for line in lines)
        )
    body += (
        f"<p style=\"margin:20px 0 0;\"><a href=\"{escape(link)}\">Open Bursa</a></p>"
        "<p style=\"margin:12px 0 0;font-size:12px;color:#64748b;\">"
        f"Signals are heuristics, not financial advice. {escape(off)}</p>"
    )
    title = subject(d)
    return Email(subject=title, text=text, html=layout(title, body))


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #
async def send_digest(session: AsyncSession, user: User, day: date) -> bool:
    digest = await build_digest(session, user, day)
    if digest is None:
        return False
    email = render(digest, user.name or user.email.split("@")[0])
    return await mail.send_quietly(Email(
        subject=email.subject, text=email.text, html=email.html, to=(user.email,)
    ))


async def send_digests(session: AsyncSession, now: datetime | None = None) -> int:
    """Send today's digest to everyone who turned it on (trading days only)."""
    day = (now or datetime.now(ZoneInfo(settings.timezone))).date()
    if not is_trading_day(day) or not mail.configured():
        return 0
    sent = 0
    for user in await users_with_digest(session):
        if await send_digest(session, user, day):
            sent += 1
    log.info("Daily digest: %d sent", sent)
    return sent
