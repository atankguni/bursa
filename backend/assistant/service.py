"""
assistant/service.py
--------------------
The question -> tools -> answer loop.

Stateless per request: the client sends the visible conversation (text turns);
tool calls happen inside one request and aren't stored. Guards: a daily
question cap, a cap on tool rounds per question, and model fallback when the
free tier is busy.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from assistant.providers import (
    ChatProvider,
    ProviderBusyError,
    ProviderError,
    Reply,
    ToolSpec,
    provider_for,
)
from assistant.tools import available_tools
from config import settings
from services.preferences import get_investing_style

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
    """Not configured, over the daily cap, or every model is busy."""


@dataclass
class Answer:
    reply: str
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
    return provider_for(settings.assistant_provider, settings.gemini_api_key) is not None


def _jsonable(value: Any) -> Any:
    """Tool output as plain JSON (dates -> ISO strings), as providers require."""
    return json.loads(json.dumps(value, default=str))


async def _generate(provider: ChatProvider, system: str, transcript: list[Any],
                    tools: list[ToolSpec], allow_tools: bool = True) -> Reply:
    """Try each configured model in order; the free tier is often busy."""
    last: Exception | None = None
    for model in settings.assistant_models:
        try:
            return await provider.generate(model, system, transcript, tools, allow_tools)
        except ProviderBusyError as exc:
            log.warning("Assistant model busy, trying next: %s", exc)
            last = exc
    raise AssistantUnavailable(
        "The AI service is busy or the free quota is used up. Try again in a minute."
    ) from last


async def ask(
    session: AsyncSession,
    history: list[dict[str, str]],
    context: str | None = None,
) -> Answer:
    provider = provider_for(settings.assistant_provider, settings.gemini_api_key)
    if provider is None:
        raise AssistantUnavailable("The assistant isn't configured: set GEMINI_API_KEY.")
    if remaining_today() <= 0:
        raise AssistantUnavailable(
            f"Daily limit of {settings.assistant_daily_limit} questions reached."
        )
    _usage[_today()] = _usage.get(_today(), 0) + 1

    tools = available_tools(settings.assistant_personal_data)
    system = SYSTEM_PROMPT.format(
        style=await get_investing_style(session),
        personal=_PERSONAL_ON if settings.assistant_personal_data else _PERSONAL_OFF,
        today=datetime.now(ZoneInfo(settings.timezone)).strftime("%A %d %B %Y, %H:%M"),
        context=f"\nThe user is currently looking at: {context}." if context else "",
    )
    transcript = provider.start(system, history)
    specs = [t.spec for t in tools.values()]
    used: list[str] = []

    try:
        for _ in range(settings.assistant_max_tool_rounds):
            reply = await _generate(provider, system, transcript, specs)
            if not reply.tool_calls:
                return Answer(reply.text or "(no answer)", reply.model, used, remaining_today())
            provider.add_model_turn(transcript, reply)
            results = []
            for call in reply.tool_calls:
                tool = tools.get(call.name)
                used.append(call.name)
                if tool is None:
                    results.append((call, {"error": f"unknown tool {call.name}"}))
                    continue
                try:
                    results.append((call, _jsonable(await tool.handler(session, call.args))))
                except Exception as exc:  # noqa: BLE001 - report to the model, keep going
                    log.warning("Assistant tool %s failed: %s", call.name, exc)
                    results.append((call, {"error": f"tool failed: {exc}"}))
            provider.add_tool_results(transcript, results)

        # Out of tool rounds: ask for an answer with what it has.
        reply = await _generate(provider, system, transcript, specs, allow_tools=False)
        return Answer(reply.text or "(no answer)", reply.model, used, remaining_today())
    except ProviderError as exc:
        log.error("Assistant provider error: %s", exc)
        raise AssistantUnavailable("The AI service rejected the request.") from exc
