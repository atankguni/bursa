"""
services/sync_state.py
----------------------
When a per-stock background job last handled a stock (`models.SyncState`).
"""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import ColumnElement, and_, delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import utcnow
from db.upsert import upsert
from models import Stock, SyncState
from schemas import SyncJob


async def mark_done(
    session: AsyncSession, job: SyncJob, tickers: Collection[str], at: datetime | None = None
) -> None:
    """Record that `job` handled `tickers` now (or `at`). Does not commit."""
    when = at or utcnow()
    await upsert(
        session, SyncState,
        [{"ticker": t, "job": job, "done_at": when} for t in tickers],
        keys=["ticker", "job"],
    )


async def clear(session: AsyncSession, job: SyncJob, ticker: str) -> None:
    """Forget that `job` ran for `ticker` (it runs again). Does not commit."""
    await session.execute(
        delete(SyncState).where(SyncState.ticker == ticker, SyncState.job == job)
    )


async def done_at(session: AsyncSession, job: SyncJob, ticker: str) -> datetime | None:
    return (
        await session.execute(
            select(SyncState.done_at).where(SyncState.ticker == ticker, SyncState.job == job)
        )
    ).scalar_one_or_none()


async def last_done(session: AsyncSession, job: SyncJob) -> datetime | None:
    """The newest time `job` ran for any stock."""
    return (
        await session.execute(select(func.max(SyncState.done_at)).where(SyncState.job == job))
    ).scalar_one()


def is_done(job: SyncJob) -> ColumnElement[bool]:
    """WHERE clause on `Stock`: `job` has handled this stock."""
    return exists().where(and_(SyncState.ticker == Stock.ticker, SyncState.job == job))


def done_column(job: SyncJob) -> ColumnElement[datetime]:
    """`job`'s time for the `Stock` row being selected (NULL = never), for ordering."""
    return (
        select(SyncState.done_at)
        .where(SyncState.ticker == Stock.ticker, SyncState.job == job)
        .scalar_subquery()
    )
