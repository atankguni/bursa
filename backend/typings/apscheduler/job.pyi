from collections.abc import Callable
from datetime import datetime
from typing import Any

class Job:
    id: str
    func: Callable[..., Any]
    next_run_time: datetime | None
