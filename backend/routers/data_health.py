"""Data health: can the app's data be trusted right now?"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from scheduler import job_report
from services.data_health import report

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/data-health")
async def data_health(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    return await report(session, job_report())
