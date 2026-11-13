"""
portfolio/cash.py
-----------------
The user's cash in their trading account (RDN), derived rather than typed in:

    deposits - withdrawals
    - buys          (shares x price + fees, on the trade date: the broker blocks it)
    + sales         (shares x price - fees, on the settlement date, T+2 trading days)
    + dividends     (after tax, counted from the ex-date)

Sales not yet settled are shown apart ("settling"). Bonus shares cost nothing;
exercised rights cost their exercise price, like a buy.

The return on the money put in compares the account (shares + cash) with net
deposits; once there is a year of history it is also given as a money-weighted
annual rate (XIRR: deposits and withdrawals weighted by how long the money was in).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import local_today
from market.trading_clock import settlement_date
from portfolio.holdings import build_portfolio
from portfolio.models import CashMovement, Transaction
from portfolio.schemas import CashMovementOut, CashOut

YEAR = 365.0


class Trade(Protocol):
    @property
    def side(self) -> str: ...
    @property
    def quantity(self) -> float: ...
    @property
    def price(self) -> float: ...
    @property
    def fees(self) -> float: ...
    @property
    def trade_date(self) -> date: ...


class Movement(Protocol):
    @property
    def kind(self) -> str: ...
    @property
    def amount(self) -> float: ...
    @property
    def day(self) -> date: ...


@dataclass(frozen=True)
class Balance:
    available: float
    settling: float
    settles_on: date | None
    net_deposits: float


def balance(
    movements: Sequence[Movement | CashMovement],
    trades: Sequence[Trade | Transaction],
    dividends_net: float,
    today: date,
    settle: Callable[[date], date] = settlement_date,
) -> Balance:
    """Cash on `today` from deposits/withdrawals, trades and dividends."""
    net_deposits = sum(
        m.amount if m.kind == "deposit" else -m.amount for m in movements if m.day <= today
    )
    available = net_deposits + dividends_net
    settling = 0.0
    settles_on: date | None = None
    for t in trades:
        if t.trade_date > today:
            continue
        value = t.quantity * t.price
        if t.side == "buy":
            available -= value + t.fees
            continue
        proceeds = value - t.fees
        arrives = settle(t.trade_date)
        if arrives <= today:
            available += proceeds
        else:
            settling += proceeds
            settles_on = max(settles_on or arrives, arrives)
    return Balance(available, settling, settles_on, net_deposits)


def money_weighted_return(flows: Sequence[tuple[date, float]], today: date) -> float | None:
    """
    Annual rate r with sum(cf / (1 + r) ** (years since start)) == 0 (XIRR), for
    flows from the investor's side: deposits negative, withdrawals and the final
    account value positive. None when it has no solution in -99.99%..+10000%.
    """
    if not flows or not any(cf < 0 for _, cf in flows) or not any(cf > 0 for _, cf in flows):
        return None
    start = min(d for d, _ in flows)

    def npv(rate: float) -> float:
        return sum(cf / (1 + rate) ** ((d - start).days / YEAR) for d, cf in flows)

    lo, hi = -0.9999, 100.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):  # bisection: slow but can't diverge
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


async def cash_summary(session: AsyncSession, user_id: int) -> CashOut:
    today = local_today()
    movements = (
        await session.execute(
            select(CashMovement)
            .where(CashMovement.user_id == user_id)
            .order_by(CashMovement.day.desc(), CashMovement.id.desc())
        )
    ).scalars().all()
    trades = (
        await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.trade_date, Transaction.id)
        )
    ).scalars().all()
    totals, _ = await build_portfolio(session, user_id)

    b = balance(movements, trades, totals.dividends_received, today)
    cash = b.available + b.settling
    account = totals.market_value + cash
    gain = account - b.net_deposits
    since = min((m.day for m in movements if m.kind == "deposit"), default=None)

    annual: float | None = None
    if since is not None and (today - since).days >= YEAR:
        flows = [
            (m.day, -m.amount if m.kind == "deposit" else m.amount)
            for m in movements
            if m.day <= today
        ]
        rate = money_weighted_return([*flows, (today, account)], today)
        annual = round(rate * 100, 2) if rate is not None else None

    return CashOut(
        movements=[CashMovementOut.model_validate(m) for m in movements],
        tracked=bool(movements),
        available=round(b.available, 2),
        settling=round(b.settling, 2),
        settles_on=b.settles_on,
        balance=round(cash, 2),
        net_deposits=round(b.net_deposits, 2),
        market_value=round(totals.market_value, 2),
        account_value=round(account, 2),
        gain=round(gain, 2),
        gain_pct=round(gain / b.net_deposits * 100, 2) if b.net_deposits > 0 else None,
        annual_return_pct=annual,
        since=since,
    )
