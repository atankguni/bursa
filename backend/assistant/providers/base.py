"""
assistant/providers/base.py
---------------------------
The provider-neutral contract every chat-model adapter implements.

The assistant loop only ever sees these types. An adapter translates them to
its own wire format on each call, and may stash provider-native state on an
`AssistantMessage.native` (e.g. Gemini 3 thought signatures); that state is only
sent back to the provider that produced it.

Adding a provider:
  1. subclass `ChatProvider` in a new module (e.g. `anthropic.py`);
  2. register it in `registry.py`;
  3. add its credential to `config.Settings` (and `backend/.env`);
  4. reference it in `assistant_chain` as "<name>:<model>".
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Self

if TYPE_CHECKING:
    from config import Settings


# --------------------------------------------------------------------------- #
# Neutral conversation types
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object (keep to the common subset)


@dataclass(frozen=True)
class ToolCall:
    id: str  # provider's call id, or a generated one if it has none
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call: ToolCall
    content: Any  # JSON-serialisable
    is_error: bool = False


@dataclass
class UserMessage:
    text: str


@dataclass
class AssistantMessage:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider: str = ""  # which adapter produced it (empty for client-sent history)
    model: str = ""
    native: Any = None  # provider-native turn; only re-sent to the same provider


@dataclass
class ToolResultsMessage:
    results: list[ToolResult]


type Message = UserMessage | AssistantMessage | ToolResultsMessage


# --------------------------------------------------------------------------- #
# Errors (the loop decides what to do; adapters only classify)
# --------------------------------------------------------------------------- #
class ProviderBusyError(RuntimeError):
    """Rate-limited, overloaded or unreachable: another attempt may succeed."""


class ProviderError(RuntimeError):
    """The provider rejected the request (bad key, bad request, blocked)."""


# --------------------------------------------------------------------------- #
# Adapter interface
# --------------------------------------------------------------------------- #
class ChatProvider(ABC):
    name: ClassVar[str]
    # Setting / environment variable the provider needs (shown in setup hints).
    credential_env: ClassVar[str]

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: "Settings") -> Self | None:
        """Build from app settings, or None when not configured (no key)."""

    @abstractmethod
    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        """One model call. `allow_tools=False` forces a text answer.

        Raises ProviderBusyError or ProviderError.
        """
