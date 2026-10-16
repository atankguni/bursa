"""
assistant/service.py
--------------------
The question -> tools -> answer loop, provider-agnostic.

Stateless per request: the client sends the visible conversation (text turns);
tool calls happen inside one request and aren't stored. Guards: a daily
question cap and a cap on tool rounds per question.

Fallback: `assistant_chain` lists ("provider", "model") attempts. If an attempt
fails (busy, quota, rejected), the whole question is re-run from scratch on the
next one, so no provider ever receives another model's internal state (e.g.
Gemini thought signatures). Re-running is cheap: tools only read the local DB.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from assistant.providers import (
    AssistantMessage,
    ChatProvider,
    Message,
    ProviderBusyError,
    ProviderError,
    ToolResult,
    ToolResultsMessage,
    UserMessage,
    resolve_chain,
    setup_hint,
)
from assistant.tools import Tool, available_tools
from config import settings
from services.preferences import get_assistant_personal_data, get_investing_style

log = logging.getLogger("bursa.assistant")

SYSTEM_PROMPT = """\
You are the assistant inside Bursa, a personal stock monitor for the Indonesia \
Stock Exchange (IDX). Answer the user's questions about stocks, signals, the \
market and how the app works.

How to answer:
- Every number you state (prices, ratios, scores, returns, P/L) must come from a \
tool result in this conversation. If no tool gives it, say the app doesn't have \
that data; never estimate or recall figures from memory.
- Stock codes are IDX tickers like BBCA (shown without .JK). Prices are in IDR.
- Signals are the app's own heuristic factor scores, relative to other IDX \
stocks, and depend on the user's investing style ({style}). When explaining a \
signal, name the categories and drivers the tool returned.
- Reply in the user's language (Indonesian or English). Be concise: a short \
answer, then a few bullet points if useful. Use **bold** sparingly; no tables.
- You can only read data. If asked to trade, change settings or edit the \
watchlist or portfolio, say the user can do that in the app.
- For buy/sell questions, give the data-based view and note briefly that it is \
not financial advice.
{personal}
Today is {today} (Jakarta time).{context}"""

_PERSONAL_ON = ("- You can read the user's watchlist and portfolio with "
                "get_watchlist / get_portfolio.")
_PERSONAL_OFF = ("- You cannot see the user's watchlist or portfolio (personal data "
                 "is turned off); if asked, say so.")


class AssistantUnavailable(RuntimeError):
    """Not configured, over the daily cap, or every attempt failed."""


@dataclass
class Answer:
    reply: str
    provider: str
    model: str
    tools_used: list[str] = field(default_factory=list)
    remaining_today: int = 0


# In-memory daily counter (single-process app; resets on restart, which only
# ever loosens the cap - the provider's own quota still applies).
_usage: dict[str, int] = {}


def _today() -> str:
    return datetime.now(ZoneInfo(settings.timezone)).date().isoformat()


def remaining_today() -> int:
    return max(0, settings.assistant_daily_limit - _usage.get(_today(), 0))


def configured() -> bool:
    return bool(resolve_chain())


def _jsonable(value: Any) -> Any:
    """Tool output as plain JSON (dates -> ISO strings), as providers require."""
    return json.loads(json.dumps(value, default=str))


async def _run_tools(session: AsyncSession, tools: dict[str, Tool],
                     reply: AssistantMessage, used: list[str]) -> ToolResultsMessage:
    results: list[ToolResult] = []
    for call in reply.tool_calls:
        used.append(call.name)
        tool = tools.get(call.name)
        if tool is None:
            results.append(ToolResult(call, f"unknown tool {call.name}", is_error=True))
            continue
        try:
            results.append(ToolResult(call, _jsonable(await tool.handler(session, call.args))))
        except Exception as exc:  # noqa: BLE001 - report to the model, keep going
            log.warning("Assistant tool %s failed: %s", call.name, exc)
            results.append(ToolResult(call, f"tool failed: {exc}", is_error=True))
    return ToolResultsMessage(results)


async def _attempt(provider: ChatProvider, model: str, system: str,
                   history: list[Message], session: AsyncSession,
                   tools: dict[str, Tool]) -> Answer:
    """Answer one question with one (provider, model), running tools as asked."""
    messages = list(history)
    specs = [t.spec for t in tools.values()]
    used: list[str] = []
    for _ in range(settings.assistant_max_tool_rounds):
        reply = await provider.complete(model=model, system=system, messages=messages,
                                        tools=specs)
        if not reply.tool_calls:
            return Answer(reply.text or "(no answer)", provider.name, model, used)
        messages.append(reply)
        messages.append(await _run_tools(session, tools, reply, used))

    # Out of tool rounds: answer with what it has.
    reply = await provider.complete(model=model, system=system, messages=messages,
                                    tools=specs, allow_tools=False)
    return Answer(reply.text or "(no answer)", provider.name, model, used)


async def ask(
    session: AsyncSession,
    history: list[dict[str, str]],
    context: str | None = None,
) -> Answer:
    attempts = resolve_chain()
    if not attempts:
        raise AssistantUnavailable(f"The assistant isn't configured: set {setup_hint()}.")
    if remaining_today() <= 0:
        raise AssistantUnavailable(
            f"Daily limit of {settings.assistant_daily_limit} questions reached."
        )
    _usage[_today()] = _usage.get(_today(), 0) + 1

    personal = await get_assistant_personal_data(session)
    tools = available_tools(personal)
    system = SYSTEM_PROMPT.format(
        style=await get_investing_style(session),
        personal=_PERSONAL_ON if personal else _PERSONAL_OFF,
        today=datetime.now(ZoneInfo(settings.timezone)).strftime("%A %d %B %Y, %H:%M"),
        context=f"\nThe user is currently looking at: {context}." if context else "",
    )
    base: list[Message] = [
        AssistantMessage(text=t["content"]) if t["role"] == "assistant"
        else UserMessage(t["content"])
        for t in history
    ]

    rejected = False
    for provider, model in attempts:
        try:
            answer = await _attempt(provider, model, system, base, session, tools)
            answer.remaining_today = remaining_today()
            return answer
        except ProviderBusyError as exc:
            log.warning("Assistant attempt %s:%s busy, trying next: %s", provider.name, model, exc)
        except ProviderError as exc:
            rejected = True
            log.error("Assistant attempt %s:%s rejected: %s", provider.name, model, exc)
    raise AssistantUnavailable(
        "The AI service rejected the request." if rejected
        else "The AI service is busy or the free quota is used up. Try again in a minute."
    )
