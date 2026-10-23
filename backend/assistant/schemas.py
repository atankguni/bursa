"""
assistant/schemas.py
--------------------
API models (Pydantic) for the AI assistant.
"""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from schemas import Schema

# Who wrote an assistant chat message.
ChatRole = Literal["user", "assistant"]


class ChatTurn(Schema):
    role: ChatRole
    content: str = Field(min_length=1, max_length=4000)


class AssistantChatIn(Schema):
    """The visible conversation (oldest first); the last turn is the new question."""

    messages: list[ChatTurn] = Field(min_length=1, max_length=40)
    # Saved chat this continues; None starts a new one. Ignored when saving is off.
    chat_id: int | None = None
    context: str | None = Field(None, max_length=200)  # e.g. "the BBCA detail view"


class AssistantChatOut(Schema):
    reply: str
    provider: str = ""
    model: str
    tools_used: list[str] = []
    remaining_today: int
    chat_id: int | None = None  # None when the user doesn't save chats


class AssistantStatusOut(Schema):
    configured: bool
    models: list[str]
    setup_hint: str = ""  # what to set when not configured (e.g. GEMINI_API_KEY)
    personal_data: bool
    remaining_today: int
    daily_limit: int
    save_chats: bool = True
    chat_days: int = 90  # saved chats are deleted this long after their last message


class ChatSummaryOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    role: ChatRole
    content: str
    tools_used: list[str] | None = None
    created_at: datetime


class ChatDetailOut(ChatSummaryOut):
    messages: list[ChatMessageOut]
