"""
system/models.py
----------------
Tables for the API and worker processes. Conventions: models.py.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from db.types import UTCDateTime, one_of
from signals.schemas import SyncMode
from system.schemas import DataName, WorkerTaskName


# --------------------------------------------------------------------------- #
# API <-> worker
# --------------------------------------------------------------------------- #
class WorkerStatus(Base):
    """The worker process (one row). `seen_at` is its heartbeat: when it is old,
    the worker isn't running and the API says so."""

    __tablename__ = "worker_status"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    # The worker's outbound provider calls ({provider: ProviderStat}).
    provider_stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_price_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class ScheduledJob(Base):
    """A job of the worker's scheduler: when it runs next and how the last run went."""

    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class WorkerTask(Base):
    """
    A long job the API hands to the worker (signals/sync_job.py). The API sets
    `request` and `requested_at`; the worker claims it (`requested_at` -> NULL),
    reports progress here, and checks `cancel_requested`. A task still `running`
    when the worker restarts is resumed from `request` and `done`.
    """

    __tablename__ = "worker_tasks"
    __table_args__ = (one_of("name", WorkerTaskName), one_of("mode", SyncMode))

    name: Mapped[WorkerTaskName] = mapped_column(String(32), primary_key=True)
    request: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mode: Mapped[SyncMode] = mapped_column(String(8), default="batch", nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class DataVersion(Base):
    """A counter per kind of cached result; see system/data_version.py."""

    __tablename__ = "data_versions"
    __table_args__ = (one_of("name", DataName),)

    name: Mapped[DataName] = mapped_column(String(16), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
