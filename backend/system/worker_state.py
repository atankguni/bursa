"""
system/worker_state.py
----------------------
What the worker process tells the API (through the database): that it is alive
(heartbeat), its provider call counters, when prices last synced, and how each
scheduled job is doing. The worker writes; the API reads.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import utcnow
from database import AsyncSessionLocal
from db.upsert import upsert
from market.providers.governor import governor
from market.schemas import ProviderStat
from market.sync import last_synced_at
from system.models import ScheduledJob, WorkerStatus
from system.schemas import JobHealth

HEARTBEAT_SECONDS = 30
# No heartbeat for this long: the worker is down (stopped, crashed or hung).
STALE_AFTER = timedelta(seconds=HEARTBEAT_SECONDS * 4)


# --------------------------------------------------------------------------- #
# Worker side
# --------------------------------------------------------------------------- #
async def heartbeat(started_at: datetime) -> None:
    """Record that the worker is alive, with its counters. Commits."""
    async with AsyncSessionLocal() as session:
        await upsert(
            session, WorkerStatus,
            {
                "id": 1,
                "started_at": started_at,
                "seen_at": utcnow(),
                "provider_stats": {
                    name: s.model_dump(mode="json") for name, s in governor.stats().items()
                },
                "last_price_sync_at": last_synced_at(),
            },
            keys=["id"],
        )
        await session.commit()


async def record_jobs(jobs: list[tuple[str, str, datetime | None]]) -> None:
    """The scheduler's jobs as (id, description, next run); drops jobs that no
    longer exist. Commits. An empty list (scheduler not started yet) changes
    nothing, so a restart keeps each job's last outcome."""
    if not jobs:
        return
    async with AsyncSessionLocal() as session:
        known = set((await session.execute(select(ScheduledJob.id))).scalars())
        current = {job_id for job_id, _, _ in jobs}
        for job_id in known - current:
            row = await session.get(ScheduledJob, job_id)
            if row is not None:
                await session.delete(row)
        await upsert(
            session, ScheduledJob,
            [{"id": i, "description": d[:200], "next_run_at": n} for i, d, n in jobs],
            keys=["id"],
        )
        await session.commit()


async def record_run(job_id: str, error: str | None, next_run: datetime | None) -> None:
    """A job finished (`error` None = it worked). Commits."""
    async with AsyncSessionLocal() as session:
        row = await session.get(ScheduledJob, job_id)
        if row is None:  # registered just now; the next record_jobs fills it in
            return
        row.last_run_at = utcnow()
        row.ok = error is None
        row.error = error[:300] if error else None
        row.next_run_at = next_run
        await session.commit()


# --------------------------------------------------------------------------- #
# API side
# --------------------------------------------------------------------------- #
async def status(session: AsyncSession) -> WorkerStatus | None:
    return await session.get(WorkerStatus, 1, populate_existing=True)


def is_alive(worker: WorkerStatus | None) -> bool:
    return worker is not None and utcnow() - worker.seen_at < STALE_AFTER


async def provider_stats(session: AsyncSession) -> dict[str, ProviderStat]:
    """Provider calls of this API process plus the worker's (which makes most)."""
    merged = dict(governor.stats())
    worker = await status(session)
    for name, raw in (worker.provider_stats if worker else {}).items():
        theirs = ProviderStat.model_validate(raw)
        mine = merged.get(name)
        if mine is None:
            merged[name] = theirs
            continue
        newest = max((mine, theirs), key=lambda s: s.last_call_at or 0)
        merged[name] = ProviderStat(
            calls=mine.calls + theirs.calls,
            calls_today=mine.calls_today + theirs.calls_today,
            errors=mine.errors + theirs.errors,
            last_error=newest.last_error or mine.last_error or theirs.last_error,
            last_call_at=newest.last_call_at,
        )
    return merged


async def last_price_sync(session: AsyncSession) -> datetime | None:
    """When prices were last synced (by the worker, or by this process on demand)."""
    worker = await status(session)
    times = [t for t in (last_synced_at(), worker and worker.last_price_sync_at) if t]
    return max(times) if times else None


async def job_report(session: AsyncSession) -> list[JobHealth]:
    """Every scheduled job with its next run and last outcome (None: not run yet)."""
    rows = (await session.execute(select(ScheduledJob).order_by(ScheduledJob.id))).scalars()
    return [
        JobHealth(
            id=r.id, description=r.description, next_run=r.next_run_at,
            last_run=r.last_run_at, ok=r.ok, error=r.error,
        )
        for r in rows
    ]
