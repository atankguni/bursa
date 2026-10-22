from datetime import datetime

EVENT_JOB_EXECUTED: int
EVENT_JOB_ERROR: int

class JobExecutionEvent:
    code: int
    job_id: str
    jobstore: str
    scheduled_run_time: datetime
    retval: object
    exception: BaseException | None
    traceback: str | None
