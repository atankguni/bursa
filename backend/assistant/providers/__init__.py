"""Chat-model adapters behind one neutral interface (see base.py)."""

from assistant.providers.base import (
    AssistantMessage,
    ChatProvider,
    Message,
    ProviderBusyError,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from assistant.providers.registry import resolve_chain, setup_hint

__all__ = [
    "AssistantMessage",
    "ChatProvider",
    "Message",
    "ProviderBusyError",
    "ProviderError",
    "ToolCall",
    "ToolResult",
    "ToolResultsMessage",
    "ToolSpec",
    "UserMessage",
    "resolve_chain",
    "setup_hint",
]
