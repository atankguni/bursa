"""
services/market_overview.py
---------------------------
Breadth, top movers, and sector aggregation for the market dashboard.

Reuses the screener dataset so the numbers stay consistent across pages.
"""

import logging
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from services.screener import ScreenerRowData, build_rows

log = logging.getLogger("bursa.market_overview")


class SectorPerformance(TypedDict):
    sector: str
    count: int
    avg_change_percent: float


class Mover(TypedDict):
    ticker: str
    name: str
    price: float | None
    change_percent: float | None


class Overview(TypedDict):
    up: int
    down: int
    flat: int
    top_gainers: list[Mover]
    top_losers: list[Mover]
    sectors: list[SectorPerformance]


class _SectorTotals(TypedDict):
    count: int
    total: float


def aggregate_sectors(rows: list[ScreenerRowData]) -> list[SectorPerformance]:
    """Average % change per sector (rows without a change are ignored)."""
    agg: dict[str, _SectorTotals] = {}
    for r in rows:
        change = r["change_percent"]
        if change is None:
            continue
        a = agg.setdefault(r["sector"] or "Unknown", {"count": 0, "total": 0.0})
        a["count"] += 1
        a["total"] += change
    out: list[SectorPerformance] = [
        {
            "sector": sector,
            "count": a["count"],
            "avg_change_percent": round(a["total"] / a["count"], 2),
        }
        for sector, a in agg.items()
    ]
    out.sort(key=lambda x: x["avg_change_percent"], reverse=True)
    return out


def _mover(r: ScreenerRowData) -> Mover:
    return {
        "ticker": r["ticker"],
        "name": r["name"],
        "price": r["price"],
        "change_percent": r["change_percent"],
    }


async def overview(session: AsyncSession, top_n: int = 5) -> Overview:
    """Breadth counts, top gainers/losers, and sector performance."""
    rows = await build_rows(session, None)  # prices only, no ratings

    # (change, row) pairs so the narrowed float survives the sort.
    with_change = [
        (chg, r) for r in rows if (chg := r["change_percent"]) is not None
    ]
    up = sum(1 for chg, _ in with_change if chg > 0)
    down = sum(1 for chg, _ in with_change if chg < 0)
    flat = len(with_change) - up - down

    by_change = [r for _, r in sorted(with_change, key=lambda p: p[0], reverse=True)]
    gainers = [_mover(r) for r in by_change[:top_n]]
    losers = [_mover(r) for r in reversed(by_change[-top_n:])]

    return {
        "up": up,
        "down": down,
        "flat": flat,
        "top_gainers": gainers,
        "top_losers": losers,
        "sectors": aggregate_sectors(rows),
    }
