"""AI assistant endpoints (read-only Q&A over the app's data) and the user's
saved chats."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from assistant import service
from assistant.providers import setup_hint
from assistant.providers.registry import parse_entry
from config import settings
from deps import current_user, get_session
from models import User
from schemas import (
    AssistantChatIn,
    AssistantChatOut,
    AssistantStatusOut,
    ChatDetailOut,
    ChatMessageOut,
    ChatSummaryOut,
)
from services import assistant_chats as chats
from services.preferences import get_assistant_personal_data, get_assistant_save_chats

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatusOut)
async def assistant_status(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> AssistantStatusOut:
    models: list[str] = []
    for entry in settings.assistant_chain:
        try:
            models.append(parse_entry(entry)[1])
        except ValueError:
            continue
    return AssistantStatusOut(
        configured=service.configured(),
        models=models,
        setup_hint=setup_hint(),
        personal_data=await get_assistant_personal_data(session, user.id),
        remaining_today=service.remaining_today(user.id),
        daily_limit=settings.assistant_daily_limit,
        save_chats=await get_assistant_save_chats(session, user.id),
        chat_days=max(1, settings.assistant_chat_days),
    )


@router.post("/chat", response_model=AssistantChatOut)
async def assistant_chat(
    payload: AssistantChatIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> AssistantChatOut:
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="the last message must be from the user")
    try:
        answer = await service.ask(
            session, user.id, [m.model_dump() for m in payload.messages], payload.context
        )
    except service.AssistantUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    chat_id = None
    if await get_assistant_save_chats(session, user.id):
        chat_id = await chats.save_exchange(
            session, user.id, payload.chat_id, payload.messages[-1].content,
            answer.reply, answer.tools_used,
        )
    return AssistantChatOut(
        reply=answer.reply,
        provider=answer.provider,
        model=answer.model,
        tools_used=answer.tools_used,
        remaining_today=answer.remaining_today,
        chat_id=chat_id,
    )


@router.get("/chats", response_model=list[ChatSummaryOut])
async def list_chats(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> list[ChatSummaryOut]:
    return [ChatSummaryOut.model_validate(c) for c in await chats.list_chats(session, user.id)]


@router.get("/chats/{chat_id}", response_model=ChatDetailOut)
async def get_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> ChatDetailOut:
    chat = await chats.get_chat(session, user.id, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found (it may have expired)")
    messages = await chats.chat_messages(session, chat.id)
    return ChatDetailOut(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[ChatMessageOut.model_validate(m) for m in messages],
    )


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> None:
    if not await chats.delete_chat(session, user.id, chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")


@router.delete("/chats", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_chats(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> None:
    await chats.delete_all_chats(session, user.id)
    await session.commit()
