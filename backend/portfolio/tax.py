"""
portfolio/tax.py
----------------
A year's figures for the annual tax return (SPT Tahunan), from the user's
transactions:

  * holdings on the year's last day: shares, the year acquired, acquisition
    cost (harga perolehan, buy fees included), the last close and market value;
  * sales in the year: gross value, the 0.1% final tax on it (withheld by the
    broker, part of the recorded fees), fees and realized P/L;
  * cash dividends in the year (by ex-date): gross, tax at the user's rate, net.

Transactions are split-adjusted to today's shares for the arithmetic; counts and
prices are shown as they were then (a 1:5 split in 2027 doesn't change what was
held on 31 December 2026). Average cost follows `holdings.apply_trade`, like the
portfolio page.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.preferences import get_trading_costs
from clock import local_today
from market.corporate_actions import (
    AdjustedTx,
    SplitMap,
    adjusted_transactions,
    load_splits,
    split_factor,
)
from market.dividends import sync_dividends
from market.models import DailyBar, Dividend, Stock
from portfolio.holdings import Book, DividendMap, apply_trade, load_dividends, new_book
from portfolio.schemas import (
    TaxDividendOut,
    TaxHoldingOut,
    TaxSaleOut,
    TaxSummaryOut,
    TaxTotals,
)

log = logging.getLogger("bursa.tax")

# PPh final on share sales at the exchange: 0.1% of the gross sale value.
SALES_TAX_PCT = 0.1


@dataclass
class _Sales:
    shares: float = 0.0
    proceeds: float = 0.0
    fees: float = 0.0
    realized_pl: float = 0.0


@dataclass
class YearFigures:
    """What `summarize` works out, before names and prices are attached."""

    books: dict[str, Book] = field(default_factory=dict[str, Book])  # positions on the last day
    acquired: dict[str, date] = field(default_factory=dict[str, date])
    sales: dict[str, _Sales] = field(default_factory=dict[str, _Sales])
    dividends: list[tuple[str, date, float, float]] = field(
        default_factory=list[tuple[str, date, float, float]]
    )
    # (ticker, ex_date, shares held in today's terms, amount per today's share)


def year_end(year: int, today: date) -> date:
    """The day the summary is taken: 31 December, or today during the year."""
    return min(date(year, 12, 31), today)


def summarize(
    txs: Sequence[AdjustedTx], year: int, end: date, dividends: DividendMap
) -> YearFigures:
    """Fold trades up to `end`, collecting the year's sales and dividends."""
    start = date(year, 1, 1)
    out = YearFigures()
    for t in txs:
        if t.trade_date > end:
            break
        book = out.books.setdefault(t.ticker, new_book())
        if t.side == "buy" and book["quantity"] <= 0:
            out.acquired[t.ticker] = t.trade_date  # a new position starts
        realized = apply_trade(book, t)
        if t.side == "sell" and t.trade_date >= start:
            s = out.sales.setdefault(t.ticker, _Sales())
            s.shares += t.quantity / t.split_factor  # as sold
            s.proceeds += t.quantity * t.price  # split-invariant
            s.fees += float(t.fees or 0.0)
            s.realized_pl += realized

    for ticker, divs in dividends.items():
        trades = [t for t in txs if t.ticker == ticker]
        for ex_date, amount in divs:
            if not start <= ex_date <= end:
                continue
            held = sum(
                t.quantity if t.side == "buy" else -t.quantity
                for t in trades
                if t.trade_date < ex_date
            )
            if held > 0:
                out.dividends.append((ticker, ex_date, held, amount))
    out.dividends.sort(key=lambda d: (d[1], d[0]))
    out.books = {k: b for k, b in out.books.items() if b["quantity"] > 0}
    return out


def build(
    figures: YearFigures,
    *,
    year: int,
    end: date,
    today: date,
    years: list[int],
    splits: SplitMap,
    closes: dict[str, float],
    names: dict[str, str],
    dividend_tax_pct: float,
) -> TaxSummaryOut:
    """The API answer: amounts rounded, shares and prices as they were then."""

    def then(ticker: str, d: date) -> float:
        # Splits after `d`: today's shares / this = the shares of then.
        return split_factor(splits.get(ticker, []), d, today)

    holdings: list[TaxHoldingOut] = []
    for ticker, book in sorted(figures.books.items()):
        f = then(ticker, end)
        close = closes.get(ticker)
        holdings.append(TaxHoldingOut(
            ticker=ticker,
            name=names.get(ticker, ticker),
            shares=round(book["quantity"] / f, 4),
            acquired_year=figures.acquired.get(ticker, end).year,
            cost=round(book["cost_basis"], 2),
            close=round(close * f, 2) if close is not None else None,
            market_value=round(book["quantity"] * close, 2) if close is not None else None,
        ))

    sales = [
        TaxSaleOut(
            ticker=ticker,
            name=names.get(ticker, ticker),
            shares=round(s.shares, 4),
            proceeds=round(s.proceeds, 2),
            sales_tax=round(s.proceeds * SALES_TAX_PCT / 100, 2),
            fees=round(s.fees, 2),
            realized_pl=round(s.realized_pl, 2),
        )
        for ticker, s in sorted(figures.sales.items())
    ]

    rate = dividend_tax_pct / 100
    dividends: list[TaxDividendOut] = []
    for ticker, ex_date, held, amount in figures.dividends:
        f = then(ticker, ex_date - timedelta(days=1))
        gross = held * amount
        dividends.append(TaxDividendOut(
            ticker=ticker,
            name=names.get(ticker, ticker),
            ex_date=ex_date,
            shares=round(held / f, 4),
            per_share=round(amount * f, 4),
            gross=round(gross, 2),
            tax=round(gross * rate, 2),
            net=round(gross * (1 - rate), 2),
        ))

    gross_div = sum(d.gross for d in dividends)
    totals = TaxTotals(
        cost=round(sum(h.cost for h in holdings), 2),
        market_value=round(sum(h.market_value or 0.0 for h in holdings), 2),
        proceeds=round(sum(s.proceeds for s in sales), 2),
        sales_tax=round(sum(s.sales_tax for s in sales), 2),
        realized_pl=round(sum(s.realized_pl for s in sales), 2),
        dividends_gross=round(gross_div, 2),
        dividends_tax=round(sum(d.tax for d in dividends), 2),
        dividends_net=round(sum(d.net for d in dividends), 2),
    )
    return TaxSummaryOut(
        year=year,
        as_of=end,
        final=today > date(year, 12, 31),
        years=years,
        dividend_tax_pct=dividend_tax_pct,
        holdings=holdings,
        sales=sales,
        dividends=dividends,
        totals=totals,
    )


async def _last_closes(
    session: AsyncSession, tickers: Sequence[str], end: date
) -> dict[str, float]:
    """Each ticker's last daily close on or before `end` (today's split basis)."""
    out: dict[str, float] = {}
    for ticker in tickers:
        close = (
            await session.execute(
                select(DailyBar.close)
                .where(DailyBar.ticker == ticker, DailyBar.day <= end)
                .order_by(DailyBar.day.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if close is not None:
            out[ticker] = close
    return out


async def _ensure_dividends(session: AsyncSession, tickers: Sequence[str]) -> None:
    """Fetch dividend history once for tickers that have none stored yet."""
    have = set(
        (
            await session.execute(
                select(Dividend.ticker).where(Dividend.ticker.in_(tickers)).group_by(Dividend.ticker)
            )
        ).scalars().all()
    )
    for t in tickers:
        if t in have:
            continue
        try:
            await sync_dividends(t)
        except Exception as exc:  # noqa: BLE001 - the rest of the summary still stands
            log.warning("Dividend history fetch failed for %s: %s", t, exc)


async def tax_summary(session: AsyncSession, user_id: int, year: int) -> TaxSummaryOut:
    today = local_today()
    end = year_end(year, today)
    txs = await adjusted_transactions(session, user_id)
    first_year = txs[0].trade_date.year if txs else today.year
    years = list(range(today.year, first_year - 1, -1))

    tickers = sorted({t.ticker for t in txs if t.trade_date <= end})
    if tickers:
        await _ensure_dividends(session, tickers)
    dividends = await load_dividends(session, tickers, date(year, 1, 1) - timedelta(days=1))
    figures = summarize(txs, year, end, dividends)

    rows = await session.execute(select(Stock.ticker, Stock.name).where(Stock.ticker.in_(tickers)))
    names = dict(rows.tuples().all())
    costs = await get_trading_costs(session, user_id)
    return build(
        figures,
        year=year,
        end=end,
        today=today,
        years=years,
        splits=await load_splits(session, tickers),
        closes=await _last_closes(session, list(figures.books), end),
        names=names,
        dividend_tax_pct=costs.dividend_tax_pct,
    )
