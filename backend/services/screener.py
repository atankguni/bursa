"""
services/screener.py
--------------------
Rank/filter the tracked universe by recommendation score + raw fundamentals.

`build_rows` assembles one row per stock (price, change, PBV, RoE, sector,
score/rating); `filter_rows` is a pure predicate kept separate for testing.
"""

import logging
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Stock
from services.metrics import derive_metrics
from services.prices import (
    indices_map,
    latest_daily,
    latest_fundamentals,
    profiles,
)
from services.recommendation import compute_universe_cached

log = logging.getLogger("bursa.screener")


class ScreenerRowData(TypedDict):
    """One screener row (mirrors `schemas.ScreenerRow`)."""

    ticker: str
    name: str
    indices: list[str]
    sector: str | None
    price: float | None
    change_percent: float | None
    pbv: float | None
    roe: float | None
    score: float | None
    rating: str | None
    strength: str | None
    has_fundamentals: bool  # False -> PBV/RoE are blank until "Sync missing" fetches them
    board: str | None  # IDX listing board ("Watchlist" = special monitoring)


async def build_rows(session: AsyncSession) -> list[ScreenerRowData]:
    """Assemble the screener dataset (one dict per tracked stock)."""
    stocks = (
        await session.execute(select(Stock).order_by(Stock.ticker))
    ).scalars().all()
    tickers = [s.ticker for s in stocks]

    index_map = await indices_map(session, tickers)
    price_map = await latest_daily(session, tickers)
    fund_map = await latest_fundamentals(session, tickers)
    prof_map = await profiles(session, tickers)
    rec_map = await compute_universe_cached(session)

    rows: list[ScreenerRowData] = []
    for s in stocks:
        info = price_map.get(s.ticker, {})
        price = info.get("close")
        prev = info.get("prev_close")
        chg = (
            round((price - prev) / prev * 100, 2)
            if price is not None and prev not in (None, 0)
            else None
        )
        metrics = derive_metrics(price, fund_map.get(s.ticker))
        rec = rec_map.get(s.ticker)
        profile = prof_map.get(s.ticker)
        rows.append(
            {
                "ticker": s.ticker,
                "name": s.name,
                "indices": index_map.get(s.ticker, []),
                "sector": profile.sector if profile else None,
                "price": price,
                "change_percent": chg,
                "pbv": metrics.pbv,
                "roe": metrics.roe,
                "score": rec.score if rec else None,
                "rating": rec.rating if rec else None,
                "strength": rec.strength if rec else None,
                "has_fundamentals": s.ticker in fund_map,
                "board": s.listing_board,
            }
        )
    return rows


def filter_rows(
    rows: list[ScreenerRowData],
    *,
    min_score: float | None = None,
    max_pbv: float | None = None,
    min_roe: float | None = None,
    rating: str | None = None,
    sector: str | None = None,
    buy_only: bool = False,
) -> list[ScreenerRowData]:
    """Keep rows matching every provided criterion (missing data is excluded)."""

    def keep(r: ScreenerRowData) -> bool:
        if min_score is not None and (r["score"] is None or r["score"] < min_score):
            return False
        if max_pbv is not None and (r["pbv"] is None or r["pbv"] > max_pbv):
            return False
        if min_roe is not None and (r["roe"] is None or r["roe"] < min_roe):
            return False
        if rating and r["rating"] != rating:
            return False
        if buy_only and r["rating"] not in ("Buy", "Strong Buy"):
            return False
        if sector and (r["sector"] or "") != sector:
            return False
        return True

    return [r for r in rows if keep(r)]
