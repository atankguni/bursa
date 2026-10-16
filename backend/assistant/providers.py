"""
assistant/providers.py
----------------------
Chat-model adapters behind one small interface, so the provider can be swapped
(like market/providers for data). Gemini is the only one today; it is called
over its public REST API with the stdlib, so no SDK dependency is needed.

The assistant loop speaks a neutral format (`ToolSpec`, `ToolCall`, `Reply`);
each adapter owns the translation to its wire format and any opaque state the
provider needs echoed back (Gemini 3 "thought signatures" live in `Reply.raw`).
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("bursa.assistant.providers")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema (object)


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None  # provider-native turn, echoed back verbatim on the next request
    model: str = ""


class ProviderBusyError(RuntimeError):
    """Rate-limited or overloaded (try another model / later)."""


class ProviderError(RuntimeError):
    """Non-retryable failure (bad key, bad request, ...)."""


class ChatProvider(ABC):
    name: str = "base"

    @abstractmethod
    def start(self, system: str, history: list[dict[str, str]]) -> list[Any]:
        """Build the provider-native transcript from neutral {role, content} turns."""

    @abstractmethod
    async def generate(self, model: str, system: str, transcript: list[Any],
                       tools: list[ToolSpec], allow_tools: bool = True) -> Reply:
        """One model call (`allow_tools=False` forces a text answer).

        Raises ProviderBusyError / ProviderError.
        """

    @abstractmethod
    def add_model_turn(self, transcript: list[Any], reply: Reply) -> None:
        """Append the model's turn exactly as returned (keeps provider state)."""

    @abstractmethod
    def add_tool_results(self, transcript: list[Any],
                         results: list[tuple[ToolCall, Any]]) -> None:
        """Append tool outputs for the calls in the last model turn."""


# --------------------------------------------------------------------------- #
# Gemini (Google AI Studio / Generative Language API)
# --------------------------------------------------------------------------- #
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_BUSY_CODES = {429, 500, 503, 504}


class GeminiProvider(ChatProvider):
    name = "gemini"

    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self._key = api_key
        self._timeout = timeout

    def start(self, system: str, history: list[dict[str, str]]) -> list[Any]:
        return [
            {"role": "model" if t["role"] == "assistant" else "user",
             "parts": [{"text": t["content"]}]}
            for t in history
        ]

    def _post(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            _GEMINI_URL.format(model=model),
            data=json.dumps(body).encode(),
            headers={"x-goog-api-key": self._key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read() or b"{}").get("error", {}).get("message", "")
            except ValueError:
                pass
            if exc.code in _BUSY_CODES:
                raise ProviderBusyError(f"{model}: HTTP {exc.code} {detail[:120]}") from exc
            raise ProviderError(f"{model}: HTTP {exc.code} {detail[:200]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderBusyError(f"{model}: {exc}") from exc

    async def generate(self, model: str, system: str, transcript: list[Any],
                       tools: list[ToolSpec], allow_tools: bool = True) -> Reply:
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": transcript,
        }
        if tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in tools
            ]}]
            if not allow_tools:  # keep declarations (history has calls), but answer now
                body["toolConfig"] = {"functionCallingConfig": {"mode": "NONE"}}
        data = await asyncio.to_thread(self._post, model, body)

        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no answer")
            raise ProviderError(f"{model}: {reason}")
        content = candidates[0].get("content") or {"role": "model", "parts": []}
        parts = content.get("parts") or []
        calls = [
            ToolCall(p["functionCall"]["name"], p["functionCall"].get("args") or {})
            for p in parts if "functionCall" in p
        ]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return Reply(text=text.strip(), tool_calls=calls, raw=content, model=model)

    def add_model_turn(self, transcript: list[Any], reply: Reply) -> None:
        transcript.append(reply.raw)  # verbatim: Gemini 3 requires thought signatures back

    def add_tool_results(self, transcript: list[Any],
                         results: list[tuple[ToolCall, Any]]) -> None:
        transcript.append({
            "role": "user",
            "parts": [
                {"functionResponse": {"name": call.name, "response": {"result": result}}}
                for call, result in results
            ],
        })


def provider_for(name: str, api_key: str | None) -> ChatProvider | None:
    """The configured provider, or None when it isn't set up (no key)."""
    if name == "gemini" and api_key:
        return GeminiProvider(api_key)
    return None
