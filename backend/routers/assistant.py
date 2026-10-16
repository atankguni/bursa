"""AI assistant endpoints (read-only Q&A over the app's data)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from assistant import service
from assistant.providers import setup_hint
from assistant.providers.registry import parse_entry
from config import settings
from deps import get_session
from schemas import AssistantChatIn, AssistantChatOut, AssistantStatusOut

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatusOut)
async def assistant_status() -> AssistantStatusOut:
    models = []
    for entry in settings.assistant_chain:
        try:
            models.append(parse_entry(entry)[1])
        except ValueError:
            continue
    return AssistantStatusOut(
        configured=service.configured(),
        models=models,
        setup_hint=setup_hint(),
        personal_data=settings.assistant_personal_data,
        remaining_today=service.remaining_today(),
        daily_limit=settings.assistant_daily_limit,
    )


@router.post("/chat", response_model=AssistantChatOut)
async def assistant_chat(
    payload: AssistantChatIn, session: AsyncSession = Depends(get_session)
) -> AssistantChatOut:
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="the last message must be from the user")
    try:
        answer = await service.ask(
            session, [m.model_dump() for m in payload.messages], payload.context
        )
    except service.AssistantUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AssistantChatOut(
        reply=answer.reply,
        provider=answer.provider,
        model=answer.model,
        tools_used=answer.tools_used,
        remaining_today=answer.remaining_today,
    )
