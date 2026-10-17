"""Alert endpoints: the signed-in user's rules and in-app events."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import current_user, get_session, require_admin
from models import Alert, AlertEvent, Stock, User
from schemas import AlertEventOut, AlertIn, AlertOut, NotificationStatusOut
from services import notify
from services.alerts import THRESHOLD_TYPES

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> list[AlertOut]:
    rows = (
        await session.execute(
            select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at.desc())
        )
    ).scalars().all()
    return [AlertOut.model_validate(r) for r in rows]


@router.get("/events", response_model=list[AlertEventOut])
async def list_events(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[AlertEventOut]:
    rows = (
        await session.execute(
            select(AlertEvent)
            .where(AlertEvent.user_id == user.id)
            .order_by(AlertEvent.triggered_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [AlertEventOut.model_validate(r) for r in rows]


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: AlertIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> AlertOut:
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == payload.ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {payload.ticker}")
    if payload.type in THRESHOLD_TYPES and payload.threshold is None:
        raise HTTPException(status_code=400, detail="threshold is required")

    alert = Alert(
        user_id=user.id, ticker=payload.ticker, type=payload.type, threshold=payload.threshold
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return AlertOut.model_validate(alert)


@router.post("/{alert_id}/toggle", response_model=AlertOut)
async def toggle_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> AlertOut:
    alert = (
        await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
        )
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
    user: User = Depends(current_user),
) -> Response:
    alert = (
        await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
        )
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    await session.delete(alert)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/notifications",
    response_model=NotificationStatusOut,
    dependencies=[Depends(require_admin)],  # server-wide Telegram setup
)
async def notification_status() -> NotificationStatusOut:
    return NotificationStatusOut(telegram=notify.telegram_configured())


@router.post(
    "/notifications/test",
    response_model=NotificationStatusOut,
    dependencies=[Depends(require_admin)],
)
async def notification_test() -> NotificationStatusOut:
    """Send a test message through every configured channel."""
    if not notify.telegram_configured():
        raise HTTPException(
            status_code=400,
            detail="Telegram isn't set up: add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
            "to backend/.env and restart the backend.",
        )
    try:
        await notify.send("✅ Bursa test notification: alerts will arrive here.")
    except notify.NotifyError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return NotificationStatusOut(telegram=True, delivered=True)
