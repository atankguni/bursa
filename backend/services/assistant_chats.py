"""
services/assistant_chats.py
---------------------------
Saved assistant conversations, so a user can continue one later or on another
device. Private to their owner. A chat is deleted ASSISTANT_CHAT_DAYS after its
last message (hidden right at that moment, removed by the hourly purge), and all
of a user's chats go when they turn saving off.
"""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import AssistantChat, ChatMessage

TITLE_LENGTH = 80


def _now() -> datetime:
    return datetime.utcnow()


def _cutoff() -> datetime:
    """Chats whose last message is older than this are expired."""
    return _now() - timedelta(days=max(1, settings.assistant_chat_days))


def title_for(question: str) -> str:
    """The first question, on one line and shortened (no AI call: saves quota)."""
    text = " ".join(question.split())
    return text if len(text) <= TITLE_LENGTH else text[: TITLE_LENGTH - 1].rstrip() + "…"


async def list_chats(session: AsyncSession, user_id: int, limit: int = 100) -> list[AssistantChat]:
    """The user's chats, most recently used first."""
    rows = await session.execute(
        select(AssistantChat)
        .where(AssistantChat.user_id == user_id, AssistantChat.updated_at >= _cutoff())
        .order_by(AssistantChat.updated_at.desc(), AssistantChat.id.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def get_chat(session: AsyncSession, user_id: int, chat_id: int) -> AssistantChat | None:
    """One of the user's own chats, unless it expired."""
    return (
        await session.execute(
            select(AssistantChat).where(
                AssistantChat.id == chat_id,
                AssistantChat.user_id == user_id,
                AssistantChat.updated_at >= _cutoff(),
            )
        )
    ).scalar_one_or_none()


async def chat_messages(session: AsyncSession, chat_id: int) -> list[ChatMessage]:
    rows = await session.execute(
        select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id)
    )
    return list(rows.scalars())


async def save_exchange(
    session: AsyncSession,
    user_id: int,
    chat_id: int | None,
    question: str,
    reply: str,
    tools_used: list[str],
) -> int:
    """Append a question and its answer, and return the chat's id. A missing,
    foreign or expired `chat_id` (e.g. deleted on another device) starts a new chat."""
    now = _now()
    chat = await get_chat(session, user_id, chat_id) if chat_id is not None else None
    if chat is None:
        chat = AssistantChat(
            user_id=user_id, title=title_for(question), created_at=now, updated_at=now
        )
        session.add(chat)
        await session.flush()
    chat.updated_at = now
    session.add_all([
        ChatMessage(chat_id=chat.id, role="user", content=question, created_at=now),
        ChatMessage(
            chat_id=chat.id, role="assistant", content=reply,
            tools_used=tools_used or None, created_at=now,
        ),
    ])
    await session.commit()
    return chat.id


async def _delete(session: AsyncSession, chat_ids: list[int]) -> int:
    # Messages first: not every database enforces ON DELETE CASCADE the same way.
    if not chat_ids:
        return 0
    await session.execute(delete(ChatMessage).where(ChatMessage.chat_id.in_(chat_ids)))
    await session.execute(delete(AssistantChat).where(AssistantChat.id.in_(chat_ids)))
    return len(chat_ids)


async def delete_chat(session: AsyncSession, user_id: int, chat_id: int) -> bool:
    ids = list(
        (
            await session.execute(
                select(AssistantChat.id).where(
                    AssistantChat.id == chat_id, AssistantChat.user_id == user_id
                )
            )
        ).scalars()
    )
    removed = await _delete(session, ids)
    await session.commit()
    return removed > 0


async def delete_all_chats(session: AsyncSession, user_id: int) -> int:
    """Delete every chat of the user. The caller commits."""
    ids = list(
        (
            await session.execute(
                select(AssistantChat.id).where(AssistantChat.user_id == user_id)
            )
        ).scalars()
    )
    return await _delete(session, ids)


async def purge_expired_chats() -> int:
    """Delete chats past the retention period (hourly job)."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        ids = list(
            (
                await session.execute(
                    select(AssistantChat.id).where(AssistantChat.updated_at < _cutoff())
                )
            ).scalars()
        )
        removed = await _delete(session, ids)
        await session.commit()
        return removed
