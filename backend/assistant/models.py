"""
assistant/models.py
-------------------
Tables for the AI assistant. Conventions: models.py.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assistant.schemas import ChatRole
from database import Base
from db.columns import created_at_column, user_fk
from db.types import UTCDateTime, one_of


class AssistantChat(Base):
    """A saved assistant conversation. Deleted ASSISTANT_CHAT_DAYS after its last
    message, or right away when the user turns saving off
    (assistant/chats.py)."""

    __tablename__ = "assistant_chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = user_fk(index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)  # the first question
    created_at: Mapped[datetime] = created_at_column()
    # Time of the last message: what the list sorts by and what expiry counts from.
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)


class ChatMessage(Base):
    """One turn of a saved assistant chat."""

    __tablename__ = "assistant_chat_messages"
    __table_args__ = (one_of("role", ChatRole),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_chats.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[ChatRole] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tools_used: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class AssistantUsage(Base):
    """Questions a user asked the assistant on a day (the daily cap)."""

    __tablename__ = "assistant_usage"

    user_id: Mapped[int] = user_fk(primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
