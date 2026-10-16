"""
assistant/providers/gemini.py
-----------------------------
Google Gemini (AI Studio / Generative Language API) over REST with the stdlib —
no SDK dependency. Credential: GEMINI_API_KEY.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Self

from assistant.providers.base import (
    AssistantMessage,
    ChatProvider,
    Message,
    ProviderBusyError,
    ProviderError,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)

if TYPE_CHECKING:
    from config import Settings

log = logging.getLogger("bursa.assistant.gemini")

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_BUSY_CODES = {429, 500, 502, 503, 504}


class GeminiProvider(ChatProvider):
    name = "gemini"
    credential_env = "GEMINI_API_KEY"

    def __init__(self, api_key: str, timeout: float = 60.0) -> None:
        self._key = api_key
        self._timeout = timeout

    @classmethod
    def from_settings(cls, settings: "Settings") -> Self | None:
        return cls(settings.gemini_api_key) if settings.gemini_api_key else None

    # -- neutral -> wire -------------------------------------------------------
    def _contents(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if isinstance(m, UserMessage):
                out.append({"role": "user", "parts": [{"text": m.text}]})
            elif isinstance(m, AssistantMessage):
                if m.provider == self.name and m.native is not None:
                    out.append(m.native)  # verbatim: Gemini 3 needs its thought signatures
                    continue
                parts: list[dict[str, Any]] = [{"text": m.text}] if m.text else []
                parts += [{"functionCall": {"name": c.name, "args": c.args}} for c in m.tool_calls]
                out.append({"role": "model", "parts": parts or [{"text": ""}]})
            elif isinstance(m, ToolResultsMessage):
                out.append({"role": "user", "parts": [
                    {"functionResponse": {
                        "name": r.call.name,
                        "response": {"error" if r.is_error else "result": r.content},
                    }}
                    for r in m.results
                ]})
        return out

    def _body(self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec],
              allow_tools: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self._contents(messages),
        }
        if tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in tools
            ]}]
            if not allow_tools:  # keep declarations (history has calls), but answer now
                body["toolConfig"] = {"functionCallingConfig": {"mode": "NONE"}}
        return body

    # -- transport --------------------------------------------------------------
    def _post(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            _URL.format(model=model),
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

    # -- wire -> neutral ----------------------------------------------------------
    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        data = await asyncio.to_thread(
            self._post, model, self._body(system, messages, tools, allow_tools)
        )
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no answer")
            raise ProviderError(f"{model}: {reason}")
        content = candidates[0].get("content") or {"role": "model", "parts": []}
        parts = content.get("parts") or []
        calls = [
            ToolCall(
                id=p["functionCall"].get("id") or uuid.uuid4().hex,
                name=p["functionCall"]["name"],
                args=p["functionCall"].get("args") or {},
            )
            for p in parts
            if "functionCall" in p
        ]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return AssistantMessage(
            text=text.strip(), tool_calls=calls, provider=self.name, model=model, native=content
        )
