"""Data health: can the app's data be trusted right now?"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from schemas import DataHealthOut
from services import worker_state
from services.data_health import report

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/data-health", response_model=DataHealthOut)
async def data_health(session: AsyncSession = Depends(get_session)) -> DataHealthOut:
    return await report(session, await worker_state.job_report(session))
