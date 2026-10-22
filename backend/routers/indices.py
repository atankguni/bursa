"""IDX stock indices (indeks saham): latest values and history."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from market.indices import BY_CODE
from schemas import IndexBarOut, IndexHistoryOut, IndexOut
from services.indices import index_history, list_indices

router = APIRouter(prefix="/api/indices", tags=["indices"])


@router.get("", response_model=list[IndexOut])
async def get_indices(session: AsyncSession = Depends(get_session)) -> list[IndexOut]:
    return await list_indices(session)


@router.get("/{code}/history", response_model=IndexHistoryOut)
async def get_index_history(
    code: str,
    range_: str = Query("1y", alias="range", pattern="^(1m|3m|6m|1y|5y|max)$"),
    session: AsyncSession = Depends(get_session),
) -> IndexHistoryOut:
    idx = BY_CODE.get(code.upper())
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Unknown index: {code}")
    bars = await index_history(session, idx.code, range_)
    return IndexHistoryOut(
        code=idx.code,
        name=idx.name,
        has_history=idx.history,
        points=[
            IndexBarOut(
                timestamp=b.day, close=b.close,
                # The app's own daily closes have no OHLC: draw them flat.
                open=b.open if b.open is not None else b.close,
                high=b.high if b.high is not None else b.close,
                low=b.low if b.low is not None else b.close,
                volume=b.volume or 0,
            )
            for b in bars
        ],
    )
