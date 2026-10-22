from collections.abc import Callable, Mapping
from datetime import datetime, tzinfo
from typing import Any

from apscheduler.events import JobExecutionEvent
from apscheduler.job import Job
from apscheduler.triggers import BaseTrigger

class AsyncIOScheduler:
    timezone: tzinfo
    running: bool
    def __init__(
        self,
        *,
        timezone: tzinfo | str | None = None,
        job_defaults: Mapping[str, object] | None = None,
    ) -> None: ...
    def add_job(
        self,
        func: Callable[..., Any],
        trigger: BaseTrigger | str | None = None,
        *,
        id: str | None = None,
        replace_existing: bool = False,
        max_instances: int = 1,
        coalesce: bool = ...,
        misfire_grace_time: int | None = ...,
        next_run_time: datetime | None = ...,
        **trigger_args: object,
    ) -> Job: ...
    def add_listener(
        self, callback: Callable[[JobExecutionEvent], None], mask: int = ...
    ) -> None: ...
    def get_jobs(self) -> list[Job]: ...
    def get_job(self, job_id: str) -> Job | None: ...
    def start(self, paused: bool = False) -> None: ...
    def shutdown(self, wait: bool = True) -> None: ...
