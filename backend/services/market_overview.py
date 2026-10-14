"""
services/market_overview.py
---------------------------
Breadth, top movers, and sector aggregation for the market dashboard.

Reuses the screener dataset so the numbers stay consistent across pages.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from services.screener import build_rows

log = logging.getLogger("bursa.market_overview")


def aggregate_sectors(rows: list[dict]) -> list[dict]:
    """Average % change per sector (rows without a change are ignored)."""
    agg: dict[str, dict] = {}
    for r in rows:
        if r["change_percent"] is None:
            continue
        key = r["sector"] or "Unknown"
        a = agg.setdefault(key, {"sector": key, "count": 0, "total": 0.0})
        a["count"] += 1
        a["total"] += r["change_percent"]
    out = [
        {
            "sector": a["sector"],
            "count": a["count"],
            "avg_change_percent": round(a["total"] / a["count"], 2),
        }
        for a in agg.values()
    ]
    out.sort(key=lambda x: x["avg_change_percent"], reverse=True)
    return out


def _mover(r: dict) -> dict:
    return {
        "ticker": r["ticker"],
        "name": r["name"],
        "price": r["price"],
        "change_percent": r["change_percent"],
    }


async def overview(session: AsyncSession, top_n: int = 5) -> dict:
    """Breadth counts, top gainers/losers, and sector performance."""
    rows = await build_rows(session)

    with_change = [r for r in rows if r["change_percent"] is not None]
    up = sum(1 for r in with_change if r["change_percent"] > 0)
    down = sum(1 for r in with_change if r["change_percent"] < 0)
    flat = len(with_change) - up - down

    by_change = sorted(with_change, key=lambda r: r["change_percent"], reverse=True)
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
