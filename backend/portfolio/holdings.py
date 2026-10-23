"""
portfolio/holdings.py
---------------------
Derive the portfolio (holdings + average-cost P/L) from recorded transactions.

Costs follow the user's `TradingCosts`: recorded fees are part of cost / proceeds;
P/L after selling estimates the sell fee + tax on today's value; dividends count
when the shares were held before the ex-date (cum date or earlier), after tax.

Pure helpers (`apply_transactions`) are unit-tested without a database; the
`build_*` functions enrich the result with current prices.
"""

import logging
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Protocol, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.preferences import get_trading_costs
from clock import local_today
from market.corporate_actions import AdjustedTx, adjusted_transactions
from market.models import DailyBar, Dividend, IndexBar, Stock
from portfolio.models import Transaction
from portfolio.schemas import EquityPoint, HoldingOut, PortfolioTotals

log = logging.getLogger("bursa.portfolio")


class Trade(Protocol):
    """What `apply_transactions` reads (a `Transaction` or a test double)."""

    @property
    def ticker(self) -> str: ...
    @property
    def side(self) -> str: ...
    @property
    def quantity(self) -> float: ...
    @property
    def price(self) -> float: ...
    @property
    def fees(self) -> float | None: ...


class Book(TypedDict):
    quantity: float
    cost_basis: float
    realized_pl: float


def apply_transactions(txs: Sequence[Trade | Transaction | AdjustedTx]) -> dict[str, Book]:
    """
    Fold trades into positions using weighted-average cost.

    Returns {ticker: {quantity, cost_basis, realized_pl}}. `txs` must be ordered
    by trade date. Sells reduce cost basis at the running average; the difference
    between proceeds and cost is realized P/L.
    """
    books: dict[str, Book] = {}
    for t in txs:
        book = books.setdefault(t.ticker, {"quantity": 0.0, "cost_basis": 0.0, "realized_pl": 0.0})
        qty = float(t.quantity)
        price = float(t.price)
        fees = float(t.fees or 0.0)

        if t.side == "buy":
            book["quantity"] += qty
            book["cost_basis"] += qty * price + fees
        else:  # sell
            held = book["quantity"]
            sell_qty = min(qty, held) if held > 0 else 0.0
            avg = book["cost_basis"] / held if held > 0 else 0.0
            book["realized_pl"] += sell_qty * price - fees - avg * sell_qty
            book["cost_basis"] -= avg * sell_qty
            book["quantity"] = held - sell_qty
            if book["quantity"] <= 1e-9:
                book["quantity"] = 0.0
                book["cost_basis"] = 0.0
    return books


type DividendMap = dict[str, list[tuple[date, float]]]


def dividend_income(txs: Sequence[AdjustedTx], dividends: DividendMap) -> dict[str, float]:
    """
    Gross cash dividends earned per ticker: for each ex-date, the shares held at
    the end of the day before (bought on the cum date or earlier) x the amount.
    `txs` are in today's (split-adjusted) shares, like the provider's amounts.
    """
    out: dict[str, float] = defaultdict(float)
    for ticker, divs in dividends.items():
        trades = [t for t in txs if t.ticker == ticker]
        for ex_date, amount in divs:
            held = sum(
                t.quantity if t.side == "buy" else -t.quantity
                for t in trades
                if t.trade_date < ex_date
            )
            if held > 0:
                out[ticker] += held * amount
    return dict(out)


async def load_dividends(
    session: AsyncSession, tickers: Sequence[str], since: date
) -> DividendMap:
    """Ex-dates (up to today) and amounts per ticker, ascending."""
    out: DividendMap = defaultdict(list)
    if not tickers:
        return out
    rows = await session.execute(
        select(Dividend.ticker, Dividend.ex_date, Dividend.amount)
        .where(
            Dividend.ticker.in_(tickers),
            Dividend.ex_date > since,
            Dividend.ex_date <= local_today(),
        )
        .order_by(Dividend.ex_date)
    )
    for ticker, ex_date, amount in rows:
        out[ticker].append((ex_date, amount))
    return out


async def build_portfolio(
    session: AsyncSession, user_id: int
) -> tuple[PortfolioTotals, list[HoldingOut]]:
    """Return (totals, holdings) enriched with the latest prices."""
    # In today's shares: split-adjusted (shares x ratio, price / ratio).
    txs = await adjusted_transactions(session, user_id)
    books = apply_transactions(txs)
    costs = await get_trading_costs(session, user_id)
    after_tax = 1 - costs.dividend_tax_pct / 100

    open_books = {t: b for t, b in books.items() if b["quantity"] > 0}
    realized_pl = sum(b["realized_pl"] for b in books.values())
    earned = (
        dividend_income(
            txs, await load_dividends(session, list(books), min(t.trade_date for t in txs))
        )
        if txs
        else {}
    )
    dividends_received = sum(earned.values()) * after_tax
    if not open_books:
        totals = PortfolioTotals(
            invested=0.0,
            market_value=0.0,
            unrealized_pl=0.0,
            day_change=0.0,
            realized_pl=round(realized_pl, 2),
            dividends_received=round(dividends_received, 2),
            total_return=round(realized_pl + dividends_received, 2),
        )
        return totals, []

    tickers = list(open_books)
    stocks = {
        s.ticker: s
        for s in (
            await session.execute(select(Stock).where(Stock.ticker.in_(tickers)))
        ).scalars().all()
    }

    # Latest + previous daily close per ticker.
    from market.prices import latest_daily

    prices = await latest_daily(session, tickers)

    holdings: list[HoldingOut] = []
    for ticker, book in open_books.items():
        qty = book["quantity"]
        avg_cost = book["cost_basis"] / qty if qty else 0.0
        info = prices.get(ticker, {})
        close = info.get("close")
        prev = info.get("prev_close")
        price = close if close is not None else avg_cost  # fall back to cost
        market_value = qty * price
        invested = book["cost_basis"]
        unrealized = market_value - invested
        day_change = qty * (close - prev) if close is not None and prev else None

        holdings.append(
            HoldingOut(
                ticker=ticker,
                name=stocks[ticker].name if ticker in stocks else ticker,
                board=stocks[ticker].listing_board if ticker in stocks else None,
                split_adjusted=any(t.ticker == ticker and t.split_factor != 1.0 for t in txs),
                quantity=qty,
                avg_cost=round(avg_cost, 2),
                price=close,
                market_value=round(market_value, 2),
                invested=round(invested, 2),
                unrealized_pl=round(unrealized, 2),
                unrealized_pl_pct=round(unrealized / invested * 100, 2) if invested else None,
                day_change=round(day_change, 2) if day_change is not None else None,
                day_change_pct=(
                    round((close - prev) / prev * 100, 2) if close is not None and prev else None
                ),
                # weight and projected_income are filled below
                dividends_received=round(earned.get(ticker, 0.0) * after_tax, 2),
            )
        )

    total_value = sum(h.market_value for h in holdings)
    for h in holdings:
        h.weight = round(h.market_value / total_value * 100, 2) if total_value else None

    # Projected annual dividend income per holding (trailing 12m per share).
    from market.dividends import trailing_dps

    dps = await trailing_dps(session, tickers)
    for h in holdings:
        h.projected_income = round(dps.get(h.ticker, 0.0) * h.quantity * after_tax, 2)

    total_invested = sum(h.invested for h in holdings)
    unrealized_pl = total_value - total_invested
    day_change = sum(h.day_change or 0.0 for h in holdings)
    prev_value = total_value - day_change
    exit_costs = total_value * costs.sell_fee_pct / 100

    totals = PortfolioTotals(
        invested=round(total_invested, 2),
        market_value=round(total_value, 2),
        unrealized_pl=round(unrealized_pl, 2),
        unrealized_pl_pct=(
            round(unrealized_pl / total_invested * 100, 2) if total_invested else None
        ),
        day_change=round(day_change, 2),
        day_change_pct=round(day_change / prev_value * 100, 2) if prev_value else None,
        realized_pl=round(realized_pl, 2),
        projected_income=round(sum(h.projected_income for h in holdings), 2),
        exit_costs=round(exit_costs, 2),
        dividends_received=round(dividends_received, 2),
        total_return=round(unrealized_pl - exit_costs + realized_pl + dividends_received, 2),
    )
    holdings.sort(key=lambda h: h.market_value, reverse=True)
    return totals, holdings


def _close_on_or_before(series: list[tuple[date, float]], d: date) -> float | None:
    """Last close at/before date `d` from an ascending [(date, close), ...]."""
    i = bisect_right([x[0] for x in series], d) - 1
    return series[i][1] if i >= 0 else None


async def equity_curve(session: AsyncSession, user_id: int) -> list[EquityPoint]:
    """Daily portfolio value reconstructed from transactions + stored closes."""
    # In today's shares: split-adjusted (shares x ratio, price / ratio).
    txs = await adjusted_transactions(session, user_id)
    if not txs:
        return []

    tickers = sorted({t.ticker for t in txs})
    rows = (
        await session.execute(
            select(DailyBar.ticker, DailyBar.day, DailyBar.close)
            .where(DailyBar.ticker.in_(tickers))
            .order_by(DailyBar.day)
        )
    ).all()

    series: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for ticker, day, close in rows:
        series[ticker].append((day, close))
    if not series:
        return []

    dates = sorted({d for lst in series.values() for d, _ in lst})
    start = min(t.trade_date for t in txs)
    dates = [d for d in dates if d >= start]

    tx_by_date: dict[date, list[AdjustedTx]] = defaultdict(list)
    for t in txs:
        tx_by_date[t.trade_date].append(t)
    tx_dates = sorted(tx_by_date)

    # IHSG over the same period (index bars; empty if never fetched).
    ihsg = [
        (day, close)
        for day, close in (
            await session.execute(
                select(IndexBar.day, IndexBar.close)
                .where(IndexBar.code == "COMPOSITE")
                .order_by(IndexBar.day)
            )
        ).all()
    ]
    ihsg_base = _close_on_or_before(ihsg, dates[0]) if dates else None

    # Dividends are income: paid on shares held before the ex-date, after tax.
    after_tax = 1 - (await get_trading_costs(session, user_id)).dividend_tax_pct / 100
    divs_by_date: dict[date, list[tuple[str, float]]] = defaultdict(list)
    for ticker, divs in (await load_dividends(session, tickers, start - timedelta(days=1))).items():
        for ex_date, amount in divs:
            divs_by_date[ex_date].append((ticker, amount))
    div_dates = sorted(divs_by_date)

    qty: dict[str, float] = defaultdict(float)
    ti = 0
    di = 0
    prev_value = 0.0
    growth = 1.0  # chained (1 + daily return)
    curve: list[EquityPoint] = []
    for d in dates:
        flow = 0.0  # money put in (+) or taken out (-) on this day
        # Dividends going ex up to today, on the shares held before today's trades.
        income = 0.0
        while di < len(div_dates) and div_dates[di] <= d:
            for ticker, amount in divs_by_date[div_dates[di]]:
                income += max(qty[ticker], 0.0) * amount * after_tax
            di += 1
        while ti < len(tx_dates) and tx_dates[ti] <= d:
            for t in tx_by_date[tx_dates[ti]]:
                gross = t.quantity * t.price
                if t.side == "buy":
                    qty[t.ticker] += t.quantity
                    flow += gross + (t.fees or 0.0)
                else:
                    qty[t.ticker] -= t.quantity
                    flow -= gross - (t.fees or 0.0)
            ti += 1
        value = 0.0
        for ticker, q in qty.items():
            if q <= 0:
                continue
            close = _close_on_or_before(series.get(ticker, []), d)
            if close is not None:
                value += q * close
        # Daily return with the day's flow at the start (Modified Dietz, daily).
        base = prev_value + flow
        if base > 0:
            growth *= 1 + (value - prev_value - flow + income) / base
        prev_value = value
        bench = _close_on_or_before(ihsg, d) if ihsg_base else None
        curve.append(EquityPoint(
            date=d,
            value=round(value, 2),
            return_pct=round((growth - 1) * 100, 2),
            benchmark_pct=(
                round((bench / ihsg_base - 1) * 100, 2) if bench and ihsg_base else None
            ),
        ))
    return curve
