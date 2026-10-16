"""
services/valuation.py
---------------------
Relative valuation: where current PBV/RoE sit within the stock's own history.

PBV history is derived from the stored daily closes (book value held constant);
RoE history comes from the yearly fundamentals.
"""

import logging
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from services.prices import daily_closes, fundamental_series, latest_daily
from services.recommendation import percentile

log = logging.getLogger("bursa.valuation")



class ValuationData(TypedDict):
    """Mirrors `schemas.ValuationOut`."""

    ticker: str
    pbv: float | None
    pbv_min: float | None
    pbv_max: float | None
    pbv_percentile: float | None
    roe: float | None
    roe_percentile: float | None
    years: list[int]
    window_days: int


_EMPTY: ValuationData = {
    "ticker": "",
    "pbv": None,
    "pbv_min": None,
    "pbv_max": None,
    "pbv_percentile": None,
    "roe": None,
    "roe_percentile": None,
    "years": [],
    "window_days": 0,
}


async def valuation(session: AsyncSession, ticker: str) -> ValuationData:
    """PBV/RoE plus their percentile within the stock's own history."""
    funds = (await fundamental_series(session, [ticker])).get(ticker, [])
    if not funds:
        return {**_EMPTY, "ticker": ticker, "years": []}

    latest = funds[-1]
    price = (await latest_daily(session, [ticker])).get(ticker, {}).get("close")
    shares = latest.total_shares

    if latest.total_assets is not None and latest.total_liabilities is not None:
        book = latest.total_assets - latest.total_liabilities
    else:
        book = latest.equity

    market_cap = price * shares if price and shares else None
    pbv = round(market_cap / book, 3) if market_cap and book and book > 0 else None

    closes = (await daily_closes(session, [ticker])).get(ticker, [])
    pbv_series = (
        [(c * shares) / book for c in closes] if shares and book and book > 0 else []
    )
    pbv_percentile = (
        percentile(pbv_series, pbv) if pbv is not None and pbv_series else None
    )

    roes = [
        f.net_income / f.equity
        for f in funds
        if f.net_income is not None and f.equity not in (None, 0)
    ]
    roe = round(roes[-1], 4) if roes else None
    roe_percentile = percentile(roes, roes[-1]) if roes else None

    return {
        "ticker": ticker,
        "pbv": pbv,
        "pbv_min": round(min(pbv_series), 3) if pbv_series else None,
        "pbv_max": round(max(pbv_series), 3) if pbv_series else None,
        "pbv_percentile": round(pbv_percentile, 1) if pbv_percentile is not None else None,
        "roe": roe,
        "roe_percentile": round(roe_percentile, 1) if roe_percentile is not None else None,
        "years": [f.fiscal_year for f in funds],
        "window_days": len(closes),
    }
