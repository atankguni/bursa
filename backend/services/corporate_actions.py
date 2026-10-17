"""
services/corporate_actions.py
-----------------------------
Stock splits: stored per ticker, used to adjust recorded transactions (shares x
ratio, price / ratio — invested capital unchanged) and to invalidate full price
histories fetched before a split (the provider re-adjusts old prices).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from db.upsert import upsert
from market.providers.governor import governor
from market.providers.registry import price_provider
from models import Split, Stock, Transaction

log = logging.getLogger("bursa.corporate_actions")

CHECK_EVERY = timedelta(days=7)

type SplitMap = dict[str, list[tuple[date, float]]]


@dataclass(frozen=True)
class AdjustedTx:
    """A transaction expressed in today's (post-split) shares."""

    id: int
    ticker: str
    side: str
    quantity: float
    price: float
    fees: float | None
    trade_date: date
    split_factor: float  # 1.0 = no split since the trade


async def load_splits(session: AsyncSession, tickers: Sequence[str]) -> SplitMap:
    out: SplitMap = {t: [] for t in tickers}
    if not tickers:
        return out
    rows = (
        await session.execute(
            select(Split.ticker, Split.ex_date, Split.ratio)
            .where(Split.ticker.in_(list(tickers)))
            .order_by(Split.ex_date)
        )
    ).all()
    for ticker, ex_date, ratio in rows:
        out[ticker].append((ex_date, ratio))
    return out


def split_factor(splits: Sequence[tuple[date, float]], trade_date: date,
                 today: date | None = None) -> float:
    """Product of split ratios that took effect after `trade_date` (up to today)."""
    today = today or date.today()
    factor = 1.0
    for ex_date, ratio in splits:
        if trade_date < ex_date <= today:
            factor *= ratio
    return factor


def adjust(txs: Sequence[Transaction], splits: SplitMap) -> list[AdjustedTx]:
    out: list[AdjustedTx] = []
    for t in txs:
        f = split_factor(splits.get(t.ticker, []), t.trade_date)
        out.append(AdjustedTx(
            id=t.id, ticker=t.ticker, side=t.side, quantity=t.quantity * f,
            price=t.price / f, fees=t.fees, trade_date=t.trade_date, split_factor=f,
        ))
    return out


async def adjusted_transactions(
    session: AsyncSession, ticker: str | None = None
) -> list[AdjustedTx]:
    """All (or one ticker's) transactions in trade order, split-adjusted."""
    stmt = select(Transaction).order_by(Transaction.trade_date, Transaction.id)
    if ticker is not None:
        stmt = stmt.where(Transaction.ticker == ticker)
    txs = (await session.execute(stmt)).scalars().all()
    splits = await load_splits(session, sorted({t.ticker for t in txs}))
    return adjust(txs, splits)


async def sync_splits(tickers: Sequence[str]) -> int:
    """Fetch and store splits; reset full price histories older than a new split."""
    provider = price_provider()
    found = 0
    for ticker in tickers:
        try:
            rows = await governor.call(
                provider.name, f"splits:{ticker}", provider.fetch_splits, ticker
            )
        except Exception as exc:  # noqa: BLE001 - keep going
            log.warning("Split sync failed for %s: %s", ticker, exc)
            continue
        async with AsyncSessionLocal() as session:
            stock = (
                await session.execute(select(Stock).where(Stock.ticker == ticker))
            ).scalar_one_or_none()
            if stock is None:
                continue
            for r in rows:
                await upsert(
                    session, Split,
                    {"ticker": ticker, "ex_date": r["ex_date"], "ratio": r["ratio"]},
                    keys=["ticker", "ex_date"], update=["ratio"],
                )
                # A split after the full history was stored: the provider has since
                # re-adjusted older prices, so fetch the history again on next view.
                stored = stock.full_history_at
                if stored is not None and r["ex_date"] >= stored.date():
                    stock.full_history_at = None
                    log.info("New split for %s on %s: full history will be re-fetched",
                             ticker, r["ex_date"])
            stock.splits_checked_at = datetime.utcnow()
            await session.commit()
            found += len(rows)
    return found


async def sync_due(tickers: Sequence[str]) -> int:
    """Check splits for the given tickers whose last check is over a week old."""
    async with AsyncSessionLocal() as session:
        cutoff = datetime.utcnow() - CHECK_EVERY
        due = (
            await session.execute(
                select(Stock.ticker).where(
                    Stock.ticker.in_(list(tickers)),
                    (Stock.splits_checked_at.is_(None)) | (Stock.splits_checked_at < cutoff),
                )
            )
        ).scalars().all()
    return await sync_splits(list(due)) if due else 0
