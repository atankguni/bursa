"""
system/data_health.py
---------------------
One report on whether the app's data can be trusted right now: scheduled jobs,
provider calls, price freshness, fundamentals coverage, index/listing freshness,
and suspicious values (including Yahoo vs IDX share-count mismatches).
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import local_today, utcnow
from config import settings
from market.fundamentals import SHARES_TOLERANCE  # the same rule the fix applies
from market.models import Fundamental, IntradayBar, MarketIndex, Stock, StockQuote
from market.prices import latest_fundamentals
from market.sync_state import is_done, last_done
from market.trading_clock import WIB, last_closed_trading_day
from signals.screener import build_rows
from system import worker_state
from system.schemas import (
    DataHealthOut,
    FundamentalsHealth,
    HealthSections,
    HealthStatus,
    IndicesHealth,
    JobHealth,
    JobsHealth,
    ListingHealth,
    PricesHealth,
    ProviderHealth,
    ProvidersHealth,
    SuspiciousHealth,
    TickerIssue,
)

STALE_DAYS = 7  # no daily bar in this many days -> likely suspended/delisted


def _status(ok: bool, warn: bool = False) -> HealthStatus:
    return "ok" if ok else ("warn" if warn else "error")


async def report(session: AsyncSession, jobs: list[JobHealth]) -> DataHealthOut:
    now = utcnow()
    trading_day = last_closed_trading_day()
    total = (await session.execute(select(func.count()).select_from(Stock))).scalar_one()

    # --- prices ---------------------------------------------------------------
    last_bar = dict(
        (await session.execute(select(StockQuote.ticker, StockQuote.day))).tuples().all()
    )
    today = local_today()
    current = sum(1 for day in last_bar.values() if day >= trading_day)
    stale = sorted(
        t for t, day in last_bar.items() if (today - day) > timedelta(days=STALE_DAYS)
    )
    no_prices = total - len(last_bar)
    # Intraday bars since the start of the trading day, exchange time.
    day_start = datetime.combine(trading_day, time(), ZoneInfo(settings.timezone))
    intraday_tickers, intraday_last = (
        await session.execute(
            select(func.count(func.distinct(IntradayBar.ticker)), func.max(IntradayBar.timestamp))
            .where(IntradayBar.timestamp >= day_start)
        )
    ).one()
    coverage = current / total if total else 0.0

    # --- fundamentals ---------------------------------------------------------
    by_source = dict(
        (await session.execute(
            select(Fundamental.source, func.count(func.distinct(Fundamental.ticker)))
            .group_by(Fundamental.source)
        )).tuples().all()
    )
    with_funds = sum(by_source.values())
    never_tried = (
        await session.execute(
            select(func.count()).select_from(Stock).where(
                ~is_done("fundamentals"),
                ~Stock.ticker.in_(select(Fundamental.ticker).distinct()),
            )
        )
    ).scalar_one()

    # --- indices & listing ----------------------------------------------------
    idx_row = (
        await session.execute(
            select(func.min(MarketIndex.updated_at), func.max(MarketIndex.updated_at),
                   func.count())
            .where(MarketIndex.updated_at.is_not(None))
        )
    ).one()
    # min/max are None when no index has a quote yet.
    idx_oldest = idx_row[0]
    idx_newest = idx_row[1]
    idx_count: int = idx_row[2]
    listing_at = await last_done(session, "listing")
    boards = dict(
        (await session.execute(
            select(Stock.listing_board, func.count()).group_by(Stock.listing_board)
        )).all()
    )

    # --- suspicious values ----------------------------------------------------
    rows = await build_rows(session, None)  # data checks only, no ratings
    extreme = [
        TickerIssue(ticker=r.ticker, issue=issue)
        for r in rows
        for issue in (
            [f"RoE {r.roe * 100:.0f}%"] if r.roe is not None and abs(r.roe) > 1 else []
        ) + (
            [f"PBV {r.pbv:.2f}"]
            if r.pbv is not None and (r.pbv > 50 or r.pbv < 0.1) else []
        )
    ]
    stocks = {s.ticker: s for s in (await session.execute(select(Stock))).scalars()}
    funds = await latest_fundamentals(session, list(stocks))
    mismatched: list[TickerIssue] = []
    for t, f in funds.items():
        idx_shares = stocks[t].idx_shares
        if f.total_shares and idx_shares:
            diff = abs(f.total_shares - idx_shares) / idx_shares
            if diff > SHARES_TOLERANCE:
                mismatched.append(TickerIssue(
                    ticker=t,
                    issue=f"shares: Yahoo {f.total_shares:,.0f} vs IDX {idx_shares:,.0f}",
                ))

    failing_jobs = [j for j in jobs if j.ok is False]
    calls = await worker_state.provider_stats(session)
    worker = await worker_state.status(session)
    worker_running = worker_state.is_alive(worker)
    return DataHealthOut(
        generated_at=now,
        sections=HealthSections(
            jobs=JobsHealth(
                status=_status(worker_running and not failing_jobs),
                items=jobs,
                worker_seen_at=worker.seen_at if worker else None,
                worker_running=worker_running,
            ),
            providers=ProvidersHealth(
                status=_status(all(not s.last_error for s in calls.values()), warn=True),
                items=[ProviderHealth(name=n, **s.model_dump()) for n, s in calls.items()],
            ),
            prices=PricesHealth(
                status=_status(coverage >= 0.8, warn=coverage >= 0.5),
                trading_day=trading_day,
                stocks=total,
                current=current,
                coverage_pct=round(coverage * 100, 1),
                no_prices=no_prices,
                stale=len(stale),
                stale_sample=stale[:15],
                intraday_tickers=intraday_tickers,
                intraday_last=intraday_last,
            ),
            fundamentals=FundamentalsHealth(
                status=_status(with_funds / total >= 0.5 if total else False, warn=True),
                statements=by_source.get("statements", 0),
                summary=by_source.get("summary", 0),
                missing=total - with_funds,
                never_tried=never_tried,
            ),
            indices=IndicesHealth(
                status=_status(
                    idx_newest is not None and now - idx_newest < timedelta(days=4), warn=True
                ),
                count=idx_count,
                oldest_update=idx_oldest,
                newest_update=idx_newest,
            ),
            listing=ListingHealth(
                status=_status(
                    listing_at is not None and now - listing_at < timedelta(days=8), warn=True
                ),
                synced_at=listing_at,
                boards={str(k): v for k, v in boards.items()},
            ),
            suspicious=SuspiciousHealth(
                status=_status(not mismatched, warn=True),
                extreme_values=extreme,
                share_mismatches=mismatched,
            ),
        ),
        timezone_now=datetime.now(WIB),
    )
