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

from pydantic import BaseModel, ConfigDict, Field

from assistant.providers.base import (
    AssistantMessage,
    ChatProvider,
    Message,
    ProviderBusyError,
    ProviderError,
    ToolCall,
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
            else:  # ToolResultsMessage
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
        reply = _Response.model_validate(data)
        if not reply.candidates:
            reason = reply.prompt_feedback.block_reason if reply.prompt_feedback else None
            raise ProviderError(f"{model}: {reason or 'no answer'}")
        content = reply.candidates[0].content or _Content()
        calls = [
            ToolCall(
                id=p.function_call.id or uuid.uuid4().hex,
                name=p.function_call.name,
                args=p.function_call.args,
            )
            for p in content.parts
            if p.function_call is not None
        ]
        text = "".join(p.text or "" for p in content.parts if not p.thought)
        # The turn goes back verbatim on the next request (Gemini 3 needs its
        # thought signatures), so keep the raw JSON, not the parsed model.
        raw_candidates: list[Any] = data.get("candidates") or []
        native: object = raw_candidates[0].get("content") or {"role": "model", "parts": []}
        return AssistantMessage(
            text=text.strip(), tool_calls=calls, provider=self.name, model=model, native=native
        )


# -- response shape (only the fields read; the rest is ignored) --------------------
class _FunctionCall(BaseModel):
    id: str | None = None
    name: str
    args: dict[str, Any] = {}


class _Part(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    text: str | None = None
    thought: bool = False
    function_call: _FunctionCall | None = Field(default=None, alias="functionCall")


class _Content(BaseModel):
    model_config = ConfigDict(extra="ignore")

    parts: list[_Part] = []


class _Candidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: _Content | None = None


class _Feedback(BaseModel):
    model_config = ConfigDict(extra="ignore")

    block_reason: str | None = Field(default=None, alias="blockReason")


class _Response(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: list[_Candidate] = []
    prompt_feedback: _Feedback | None = Field(default=None, alias="promptFeedback")
