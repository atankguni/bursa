"""
services/dividend_calendar.py
-----------------------------
Expected upcoming dividends for holdings + watchlist.

The provider has no announced future ex-dates for IDX stocks (it only reports
the most recent past one), but IDX companies pay on very regular yearly
schedules. So each dividend from the last 12 months is projected one year
ahead and clearly labelled as an estimate; "regular" means the company also
paid in that month a year earlier.
"""

from datetime import date, timedelta
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Dividend, Stock, Watchlist
from services.dividends import sync_dividends
from services.portfolio import build_portfolio


class ExpectedDividend(TypedDict):
    ticker: str
    name: str
    expected_ex_date: date
    based_on: date  # last year's ex-date it's projected from
    amount_per_share: float
    regular: bool  # also paid in that month the year before
    shares_held: float | None
    expected_income: float | None
    in_portfolio: bool
    in_watchlist: bool


def _plus_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # Feb 29
        return d.replace(year=d.year + 1, day=28)


def project(
    history: list[tuple[date, float]], today: date, horizon_days: int
) -> list[tuple[date, date, float, bool]]:
    """(expected_ex_date, based_on, amount, regular) within the horizon."""
    window_start = today - timedelta(days=365)
    months_year_before = {
        (d.year, d.month) for d, _ in history if d < window_start
    }
    out = []
    for ex_date, amount in history:
        if not (window_start <= ex_date <= today):
            continue
        expected = _plus_year(ex_date)
        if today <= expected <= today + timedelta(days=horizon_days):
            regular = (ex_date.year - 1, ex_date.month) in months_year_before
            out.append((expected, ex_date, amount, regular))
    return out


async def dividend_calendar(session: AsyncSession, days: int = 180) -> list[ExpectedDividend]:
    _, holdings = await build_portfolio(session)
    held = {h["ticker"]: h["quantity"] for h in holdings}
    watched = set((await session.execute(select(Watchlist.ticker))).scalars().all())
    tickers = sorted(set(held) | watched)
    if not tickers:
        return []

    # Fetch dividend history once for tickers that have none stored yet.
    have = set(
        (await session.execute(
            select(Dividend.ticker).where(Dividend.ticker.in_(tickers)).group_by(Dividend.ticker)
        )).scalars().all()
    )
    for t in tickers:
        if t not in have:
            await sync_dividends(t)

    history: dict[str, list[tuple[date, float]]] = {t: [] for t in tickers}
    for t, d, a in (await session.execute(
        select(Dividend.ticker, Dividend.ex_date, Dividend.amount)
        .where(Dividend.ticker.in_(tickers),
               Dividend.ex_date >= date.today() - timedelta(days=800))
        .order_by(Dividend.ex_date)
    )).all():
        history[t].append((d, a))
    names = dict((await session.execute(
        select(Stock.ticker, Stock.name).where(Stock.ticker.in_(tickers))
    )).all())

    today = date.today()
    out: list[ExpectedDividend] = []
    for t in tickers:
        for expected, based_on, amount, regular in project(history[t], today, days):
            shares = held.get(t)
            out.append({
                "ticker": t, "name": names.get(t, t), "expected_ex_date": expected,
                "based_on": based_on, "amount_per_share": round(amount, 4),
                "regular": regular, "shares_held": shares,
                "expected_income": round(amount * shares, 2) if shares else None,
                "in_portfolio": t in held, "in_watchlist": t in watched,
            })
    return sorted(out, key=lambda x: x["expected_ex_date"])
