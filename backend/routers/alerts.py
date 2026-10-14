"""Alert endpoints (rules + in-app events)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from models import Alert, AlertEvent, Stock
from schemas import AlertEventOut, AlertIn, AlertOut
from services.alerts import THRESHOLD_TYPES

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(session: AsyncSession = Depends(get_session)) -> list[AlertOut]:
    rows = (
        await session.execute(select(Alert).order_by(Alert.created_at.desc()))
    ).scalars().all()
    return [AlertOut.model_validate(r) for r in rows]


@router.get("/events", response_model=list[AlertEventOut])
async def list_events(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[AlertEventOut]:
    rows = (
        await session.execute(
            select(AlertEvent).order_by(AlertEvent.triggered_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [AlertEventOut.model_validate(r) for r in rows]


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: AlertIn,
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == payload.ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {payload.ticker}")
    if payload.type in THRESHOLD_TYPES and payload.threshold is None:
        raise HTTPException(status_code=400, detail="threshold is required")

    alert = Alert(
        ticker=payload.ticker, type=payload.type, threshold=payload.threshold
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return AlertOut.model_validate(alert)


@router.post("/{alert_id}/toggle", response_model=AlertOut)
async def toggle_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.active = not alert.active
    await session.commit()
    await session.refresh(alert)
    return AlertOut.model_validate(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    await session.delete(alert)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
