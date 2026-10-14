"""
services/portfolio.py
---------------------
Derive the portfolio (holdings + average-cost P/L) from recorded transactions.

Pure helpers (`apply_transactions`) are unit-tested without a database; the
`build_*` functions enrich the result with current prices.
"""

import logging
from bisect import bisect_right
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Stock, StockPrice, Transaction

log = logging.getLogger("bursa.portfolio")


def apply_transactions(txs: list) -> dict[str, dict]:
    """
    Fold trades into positions using weighted-average cost.

    Returns {ticker: {quantity, cost_basis, realized_pl}}. `txs` must be ordered
    by trade date. Sells reduce cost basis at the running average; the difference
    between proceeds and cost is realized P/L.
    """
    books: dict[str, dict] = {}
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


async def build_portfolio(session: AsyncSession) -> tuple[dict, list[dict]]:
    """Return (totals, holdings) enriched with the latest prices."""
    txs = (
        await session.execute(
            select(Transaction).order_by(Transaction.trade_date, Transaction.id)
        )
    ).scalars().all()
    books = apply_transactions(txs)

    open_books = {t: b for t, b in books.items() if b["quantity"] > 0}
    realized_pl = sum(b["realized_pl"] for b in books.values())
    if not open_books:
        totals = {
            "invested": 0.0,
            "market_value": 0.0,
            "unrealized_pl": 0.0,
            "unrealized_pl_pct": None,
            "day_change": 0.0,
            "day_change_pct": None,
            "realized_pl": round(realized_pl, 2),
            "projected_income": 0.0,
        }
        return totals, []

    tickers = list(open_books)
    stocks = {
        s.ticker: s
        for s in (
            await session.execute(select(Stock).where(Stock.ticker.in_(tickers)))
        ).scalars().all()
    }

    # Latest + previous daily close per ticker.
    from services.prices import latest_daily

    prices = await latest_daily(session, tickers)

    holdings: list[dict] = []
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
            {
                "ticker": ticker,
                "name": stocks[ticker].name if ticker in stocks else ticker,
                "quantity": qty,
                "avg_cost": round(avg_cost, 2),
                "price": close,
                "market_value": round(market_value, 2),
                "invested": round(invested, 2),
                "unrealized_pl": round(unrealized, 2),
                "unrealized_pl_pct": round(unrealized / invested * 100, 2) if invested else None,
                "day_change": round(day_change, 2) if day_change is not None else None,
                "day_change_pct": (
                    round((close - prev) / prev * 100, 2)
                    if close is not None and prev
                    else None
                ),
                "weight": None,  # filled below
            }
        )

    total_value = sum(h["market_value"] for h in holdings)
    for h in holdings:
        h["weight"] = round(h["market_value"] / total_value * 100, 2) if total_value else None

    # Projected annual dividend income per holding (trailing 12m per share).
    from services.dividends import trailing_dps

    dps = await trailing_dps(session, tickers)
    for h in holdings:
        h["projected_income"] = round(dps.get(h["ticker"], 0.0) * h["quantity"], 2)

    total_invested = sum(h["invested"] for h in holdings)
    unrealized_pl = total_value - total_invested
    day_change = sum(h["day_change"] or 0.0 for h in holdings)
    prev_value = total_value - day_change

    totals = {
        "invested": round(total_invested, 2),
        "market_value": round(total_value, 2),
        "unrealized_pl": round(unrealized_pl, 2),
        "unrealized_pl_pct": (
            round(unrealized_pl / total_invested * 100, 2) if total_invested else None
        ),
        "day_change": round(day_change, 2),
        "day_change_pct": round(day_change / prev_value * 100, 2) if prev_value else None,
        "realized_pl": round(realized_pl, 2),
        "projected_income": round(sum(h["projected_income"] or 0.0 for h in holdings), 2),
    }
    holdings.sort(key=lambda h: h["market_value"], reverse=True)
    return totals, holdings


def _close_on_or_before(series: list[tuple], d) -> float | None:
    """Last close at/before date `d` from an ascending [(date, close), ...]."""
    i = bisect_right([x[0] for x in series], d) - 1
    return series[i][1] if i >= 0 else None


async def equity_curve(session: AsyncSession) -> list[dict]:
    """Daily portfolio value reconstructed from transactions + stored closes."""
    txs = (
        await session.execute(
            select(Transaction).order_by(Transaction.trade_date, Transaction.id)
        )
    ).scalars().all()
    if not txs:
        return []

    tickers = sorted({t.ticker for t in txs})
    rows = (
        await session.execute(
            select(StockPrice.ticker, StockPrice.timestamp, StockPrice.close)
            .where(StockPrice.interval == "1d", StockPrice.ticker.in_(tickers))
            .order_by(StockPrice.timestamp)
        )
    ).all()

    series: dict[str, list[tuple]] = defaultdict(list)
    for ticker, ts, close in rows:
        series[ticker].append((ts.date(), close))
    if not series:
        return []

    dates = sorted({d for lst in series.values() for d, _ in lst})
    start = min(t.trade_date for t in txs)
    dates = [d for d in dates if d >= start]

    tx_by_date: dict = defaultdict(list)
    for t in txs:
        tx_by_date[t.trade_date].append(t)
    tx_dates = sorted(tx_by_date)

    qty: dict[str, float] = defaultdict(float)
    ti = 0
    curve: list[dict] = []
    for d in dates:
        while ti < len(tx_dates) and tx_dates[ti] <= d:
            for t in tx_by_date[tx_dates[ti]]:
                qty[t.ticker] += t.quantity if t.side == "buy" else -t.quantity
            ti += 1
        value = 0.0
        for ticker, q in qty.items():
            if q <= 0:
                continue
            close = _close_on_or_before(series.get(ticker, []), d)
            if close is not None:
                value += q * close
        curve.append({"date": d, "value": round(value, 2)})
    return curve
