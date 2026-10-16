"""
services/data_health.py
-----------------------
One report on whether the app's data can be trusted right now: scheduled jobs,
provider calls, price freshness, fundamentals coverage, index/listing freshness,
and suspicious values (including Yahoo vs IDX share-count mismatches).
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from market.providers.governor import governor
from models import Fundamental, IndexQuote, Stock, StockPrice
from services.fundamentals import SHARES_TOLERANCE  # the same rule the fix applies
from services.market_clock import WIB, last_closed_trading_day
from services.prices import latest_fundamentals
from services.screener import build_rows

STALE_DAYS = 7  # no daily bar in this many days -> likely suspended/delisted


def _status(ok: bool, warn: bool = False) -> str:
    return "ok" if ok else ("warn" if warn else "error")


async def report(session: AsyncSession, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.utcnow()
    trading_day = last_closed_trading_day()
    total = (await session.execute(select(func.count()).select_from(Stock))).scalar_one()

    # --- prices ---------------------------------------------------------------
    last_bar = dict(
        (await session.execute(
            select(StockPrice.ticker, func.max(StockPrice.timestamp))
            .where(StockPrice.interval == "1d").group_by(StockPrice.ticker)
        )).all()
    )
    current = sum(1 for ts in last_bar.values() if ts.date() >= trading_day)
    stale = sorted(
        t for t, ts in last_bar.items() if (now - ts) > timedelta(days=STALE_DAYS)
    )
    no_prices = total - len(last_bar)
    # 1m bars are stored in UTC; the WIB trading day starts 7h earlier in UTC.
    day_start_utc = datetime.combine(trading_day, datetime.min.time()) - timedelta(hours=7)
    intraday_tickers, intraday_last = (
        await session.execute(
            select(func.count(func.distinct(StockPrice.ticker)), func.max(StockPrice.timestamp))
            .where(StockPrice.interval == "1m", StockPrice.timestamp >= day_start_utc)
        )
    ).one()
    coverage = current / total if total else 0.0

    # --- fundamentals ---------------------------------------------------------
    by_source = dict(
        (await session.execute(
            select(func.coalesce(Fundamental.source, "statements"),
                   func.count(func.distinct(Fundamental.ticker)))
            .group_by(func.coalesce(Fundamental.source, "statements"))
        )).all()
    )
    with_funds = sum(by_source.values())
    never_tried = (
        await session.execute(
            select(func.count()).select_from(Stock).where(
                Stock.fundamentals_checked_at.is_(None),
                ~Stock.ticker.in_(select(Fundamental.ticker).distinct()),
            )
        )
    ).scalar_one()

    # --- indices & listing ----------------------------------------------------
    idx_oldest, idx_newest, idx_count = (
        await session.execute(
            select(func.min(IndexQuote.updated_at), func.max(IndexQuote.updated_at),
                   func.count())
        )
    ).one()
    listing_at = (await session.execute(select(func.max(Stock.idx_synced_at)))).scalar_one()
    boards = dict(
        (await session.execute(
            select(Stock.listing_board, func.count()).group_by(Stock.listing_board)
        )).all()
    )

    # --- suspicious values ----------------------------------------------------
    rows = await build_rows(session)
    extreme = [
        {"ticker": r["ticker"], "issue": issue}
        for r in rows
        for issue in (
            [f"RoE {r['roe'] * 100:.0f}%"] if r["roe"] is not None and abs(r["roe"]) > 1 else []
        ) + (
            [f"PBV {r['pbv']:.2f}"]
            if r["pbv"] is not None and (r["pbv"] > 50 or r["pbv"] < 0.1) else []
        )
    ]
    stocks = {s.ticker: s for s in (await session.execute(select(Stock))).scalars()}
    funds = await latest_fundamentals(session, list(stocks))
    mismatched = []
    for t, f in funds.items():
        idx_shares = stocks[t].idx_shares
        if f.total_shares and idx_shares:
            diff = abs(f.total_shares - idx_shares) / idx_shares
            if diff > SHARES_TOLERANCE:
                mismatched.append({
                    "ticker": t,
                    "issue": f"shares: Yahoo {f.total_shares:,.0f} vs IDX {idx_shares:,.0f}",
                })

    failing_jobs = [j for j in jobs if j["ok"] is False]
    calls = governor.stats()
    return {
        "generated_at": now,
        "sections": {
            "jobs": {
                "status": _status(not failing_jobs),
                "items": jobs,
            },
            "providers": {
                "status": _status(all(not s["last_error"] for s in calls.values()), warn=True),
                "items": [{"name": n, **s} for n, s in calls.items()],
            },
            "prices": {
                "status": _status(coverage >= 0.8, warn=coverage >= 0.5),
                "trading_day": trading_day,
                "stocks": total,
                "current": current,
                "coverage_pct": round(coverage * 100, 1),
                "no_prices": no_prices,
                "stale": len(stale),
                "stale_sample": stale[:15],
                "intraday_tickers": intraday_tickers,
                "intraday_last": intraday_last,
            },
            "fundamentals": {
                "status": _status(with_funds / total >= 0.5 if total else False, warn=True),
                "statements": by_source.get("statements", 0),
                "summary": by_source.get("summary", 0),
                "missing": total - with_funds,
                "never_tried": never_tried,
            },
            "indices": {
                "status": _status(
                    idx_newest is not None and now - idx_newest < timedelta(days=4), warn=True
                ),
                "count": idx_count,
                "oldest_update": idx_oldest,
                "newest_update": idx_newest,
            },
            "listing": {
                "status": _status(
                    listing_at is not None and now - listing_at < timedelta(days=8), warn=True
                ),
                "synced_at": listing_at,
                "boards": {str(k): v for k, v in boards.items()},
            },
            "suspicious": {
                "status": _status(not mismatched, warn=True),
                "extreme_values": extreme,
                "share_mismatches": mismatched,
            },
        },
        "timezone_now": datetime.now(WIB),
    }
