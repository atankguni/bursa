"""
Dividend income per month, net of tax: received over the last 12 months (by
ex-date, like the tax summary) and expected over the next 6 (projected from last
year's ex-dates for the shares held today, see `dividend_calendar`).
"""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from accounts.preferences import get_trading_costs
from clock import local_today
from market.corporate_actions import adjusted_transactions
from portfolio.dividend_calendar import dividend_calendar
from portfolio.holdings import entitled_dividends, load_dividends
from portfolio.schemas import DividendIncomeOut, DividendMonthOut

PAST_MONTHS = 12  # including this month
AHEAD_MONTHS = 6


def add_months(d: date, n: int) -> date:
    """The first day of the month `n` months from `d`'s month."""
    m = d.year * 12 + d.month - 1 + n
    return date(m // 12, m % 12 + 1, 1)


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_window(today: date) -> tuple[list[str], date, date]:
    """The months shown, the first day of the first and the last day of the last."""
    first = add_months(today, -(PAST_MONTHS - 1))
    last = add_months(today, AHEAD_MONTHS + 1) - timedelta(days=1)
    keys = [month_key(add_months(first, i)) for i in range(PAST_MONTHS + AHEAD_MONTHS)]
    return keys, first, last


async def dividend_income_by_month(session: AsyncSession, user_id: int) -> DividendIncomeOut:
    today = local_today()
    keys, first, last = month_window(today)
    rate = (await get_trading_costs(session, user_id)).dividend_tax_pct / 100

    received: dict[str, float] = defaultdict(float)
    txs = await adjusted_transactions(session, user_id)
    tickers = sorted({t.ticker for t in txs})
    divs = await load_dividends(session, tickers, first - timedelta(days=1))
    for _, ex_date, gross in entitled_dividends(txs, divs):
        received[month_key(ex_date)] += gross * (1 - rate)

    expected: dict[str, float] = defaultdict(float)
    for d in await dividend_calendar(session, user_id, (last - today).days):
        if d.expected_income and d.expected_ex_date <= last:
            expected[month_key(d.expected_ex_date)] += d.expected_income * (1 - rate)

    months = [
        DividendMonthOut(
            month=k, received=round(received[k], 2), expected=round(expected[k], 2)
        )
        for k in keys
    ]
    return DividendIncomeOut(
        months=months,
        current_month=month_key(today),
        received_12m=round(sum(m.received for m in months), 2),
        expected_6m=round(sum(m.expected for m in months), 2),
        dividend_tax_pct=rate * 100,
    )
