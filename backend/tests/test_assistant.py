"""Assistant loop, provider chain/registry, tools and the Gemini adapter (no network)."""

from typing import Self

import assistant.providers.registry as registry
import assistant.service as service
from assistant.providers import (
    AssistantMessage,
    ChatProvider,
    ProviderBusyError,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    UserMessage,
)
from assistant.providers.gemini import GeminiProvider
from assistant.tools import _ticker, available_tools
from clock import utcnow
from config import Settings, settings


class _Scripted(ChatProvider):
    """Fake adapter: replays scripted replies (or raises) and records what it saw."""

    name = "fake"
    credential_env = "FAKE_API_KEY"

    def __init__(self, script):
        self.script = list(script)
        self.seen = []  # messages passed on each call
        self.allow_tools_seen = []
        self.tool_names: list[str] = []

    @classmethod
    def from_settings(cls, settings: Settings) -> Self | None:  # pragma: no cover
        return None  # tests build instances directly

    async def complete(self, *, model, system, messages, tools, allow_tools=True):
        self.seen.append(list(messages))
        self.allow_tools_seen.append(allow_tools)
        self.tool_names = [t.name for t in tools]
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        step.provider, step.model = self.name, model
        return step


def _named(name: str) -> type[_Scripted]:
    """A _Scripted adapter registered under another name (`name` is per class)."""
    return type(f"_Scripted_{name}", (_Scripted,), {"name": name})


def _chain(monkeypatch, *attempts):
    monkeypatch.setattr(service, "resolve_chain", lambda: list(attempts))


def _call(name, **args):
    return ToolCall(id=f"id-{name}", name=name, args=args)


async def _ask(client, text="hi"):
    return await client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": text}]})


# --------------------------------------------------------------------------- #
# Loop
# --------------------------------------------------------------------------- #
async def test_chat_runs_tools_then_answers(client, monkeypatch):
    fake = _Scripted([AssistantMessage(tool_calls=[_call("get_stock", ticker="bbca")]),
                      AssistantMessage(text="BBCA is a bank.")])
    _chain(monkeypatch, (fake, "m1"))

    r = await _ask(client, "Tell me about BBCA")
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "BBCA is a bank."
    assert (body["provider"], body["model"], body["tools_used"]) == ("fake", "m1", ["get_stock"])
    tool_msg = fake.seen[1][-1]
    assert isinstance(tool_msg, ToolResultsMessage)
    content = tool_msg.results[0].content
    assert isinstance(content, dict) and content["ticker"] == "BBCA"  # "bbca" normalised
    assert "get_portfolio" not in fake.tool_names  # personal data is off by default


async def test_unknown_tool_and_tool_errors_are_reported_not_raised(client, monkeypatch):
    fake = _Scripted([
        AssistantMessage(tool_calls=[_call("delete_everything"),
                                     _call("get_fundamentals", ticker="NOPE")]),
        AssistantMessage(text="Sorry, I can't do that."),
    ])
    _chain(monkeypatch, (fake, "m"))
    assert (await _ask(client, "delete my data")).status_code == 200
    unknown, missing = fake.seen[1][-1].results
    assert unknown.is_error and "unknown tool" in unknown.content
    assert not missing.is_error and "no fundamentals" in missing.content["error"]


async def test_tool_rounds_are_capped(client, monkeypatch):
    monkeypatch.setattr(settings, "assistant_max_tool_rounds", 2)
    loop = [AssistantMessage(tool_calls=[_call("market_overview")]) for _ in range(2)]
    fake = _Scripted([*loop, AssistantMessage(text="Final answer.")])
    _chain(monkeypatch, (fake, "m"))
    r = await _ask(client, "loop forever")
    assert r.json()["reply"] == "Final answer."
    assert fake.allow_tools_seen == [True, True, False]  # last call forces an answer


async def test_not_configured_uses_setup_hint_and_daily_cap(client, monkeypatch):
    _chain(monkeypatch)  # nothing configured
    r = await _ask(client)
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]

    _chain(monkeypatch, (_Scripted([AssistantMessage(text="ok")]), "m"))
    monkeypatch.setattr(settings, "assistant_daily_limit", 1)
    assert (await _ask(client, "one")).status_code == 200
    r = await _ask(client, "two")
    assert r.status_code == 503 and "Daily limit" in r.json()["detail"]


async def test_last_message_must_be_user(client):
    r = await client.post("/api/assistant/chat", json={
        "messages": [{"role": "assistant", "content": "hello"}]})
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Fallback across the chain
# --------------------------------------------------------------------------- #
async def test_busy_attempt_falls_back_and_restarts_cleanly(client, monkeypatch):
    # First provider gets as far as a tool call, then hits its quota mid-question.
    first = _named("primary")([AssistantMessage(tool_calls=[_call("market_overview")]),
                               ProviderBusyError("429 quota")])
    second = _named("backup")([AssistantMessage(text="Answered by backup.")])
    _chain(monkeypatch, (first, "a"), (second, "b"))

    body = (await _ask(client, "how is the market?")).json()
    assert body["reply"] == "Answered by backup."
    assert (body["provider"], body["model"]) == ("backup", "b")
    # The backup starts from the user's question only: no turns (or native state)
    # produced by the other provider leak into its request.
    assert len(second.seen[0]) == 1 and isinstance(second.seen[0][0], UserMessage)


async def test_rejected_attempt_falls_back(client, monkeypatch):
    bad = _named("badkey")([ProviderError("401 bad key")])
    good = _named("good")([AssistantMessage(text="ok")])
    _chain(monkeypatch, (bad, "x"), (good, "y"))
    assert (await _ask(client)).json()["provider"] == "good"


async def test_all_attempts_busy_is_503(client, monkeypatch):
    _chain(monkeypatch, (_Scripted([ProviderBusyError("503")]), "a"),
           (_Scripted([ProviderBusyError("429")]), "b"))
    r = await _ask(client)
    assert r.status_code == 503 and "busy" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
def test_registry_resolves_chain_skipping_unknown_and_unconfigured(monkeypatch):
    class _Keyed(_Scripted):
        name = "keyed"
        credential_env = "KEYED_API_KEY"

        @classmethod
        def from_settings(cls, settings: Settings) -> Self | None:
            return cls([])

    class _NoKey(_Keyed):
        name = "nokey"
        credential_env = "NOKEY_API_KEY"

        @classmethod
        def from_settings(cls, settings: Settings) -> Self | None:
            return None

    monkeypatch.setattr(registry, "_REGISTRY", {"keyed": _Keyed, "nokey": _NoKey})
    monkeypatch.setattr(settings, "assistant_chain", [
        "nokey:m0", "keyed:m1", "mystery:m2", "malformed", "keyed:m3"])
    chain = registry.resolve_chain()
    assert [(p.name, m) for p, m in chain] == [("keyed", "m1"), ("keyed", "m3")]
    assert chain[0][0] is chain[1][0]  # one instance per provider
    assert registry.setup_hint() == "NOKEY_API_KEY or KEYED_API_KEY"


def test_parse_entry_validation():
    assert registry.parse_entry(" gemini : gemini-3.5-flash ") == ("gemini", "gemini-3.5-flash")
    for bad in ["gemini", ":model", "gemini:"]:
        try:
            registry.parse_entry(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} should be rejected")


def test_default_chain_is_gemini():
    assert all(registry.parse_entry(e)[0] == "gemini" for e in settings.assistant_chain)
    no_key = settings.model_copy(update={"gemini_api_key": None})
    assert GeminiProvider.from_settings(no_key) is None


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def test_personal_tools_only_when_enabled():
    assert "get_portfolio" not in available_tools(False)
    assert {"get_portfolio", "get_watchlist"} <= set(available_tools(True))


def test_ticker_normalisation():
    assert _ticker("bbca") == "BBCA" and _ticker("BBCA.JK") == "BBCA"


# --------------------------------------------------------------------------- #
# Gemini adapter (wire format)
# --------------------------------------------------------------------------- #
async def test_gemini_adapter_wire_format(monkeypatch):
    sent = []
    native = {"role": "model", "parts": [
        {"functionCall": {"name": "get_stock", "args": {"ticker": "BBCA"}},
         "thoughtSignature": "sig-123"}]}
    g = GeminiProvider("test-key")
    monkeypatch.setattr(g, "_post", lambda model, body: sent.append(body) or {
        "candidates": [{"content": native}]})

    specs = [t.spec for t in available_tools(False).values()]
    reply = await g.complete(model="m", system="sys", messages=[UserMessage("q")],
                             tools=specs, allow_tools=False)
    assert reply.provider == "gemini" and reply.native is native
    assert reply.tool_calls[0].name == "get_stock" and reply.tool_calls[0].id  # id generated
    assert sent[0]["toolConfig"]["functionCallingConfig"]["mode"] == "NONE"
    assert sent[0]["systemInstruction"]["parts"][0]["text"] == "sys"

    history = [
        UserMessage("q"),
        AssistantMessage(text="earlier answer"),  # client-sent history: rebuilt as text
        reply,  # own turn: echoed verbatim (keeps the thought signature)
        ToolResultsMessage([ToolResult(reply.tool_calls[0], {"price": 1}),
                            ToolResult(reply.tool_calls[0], "boom", is_error=True)]),
    ]
    contents = g._contents(history)
    assert [c["role"] for c in contents] == ["user", "model", "model", "user"]
    assert contents[1]["parts"] == [{"text": "earlier answer"}]
    assert contents[2]["parts"][0]["thoughtSignature"] == "sig-123"
    assert contents[3]["parts"][0]["functionResponse"]["response"] == {"result": {"price": 1}}
    assert contents[3]["parts"][1]["functionResponse"]["response"] == {"error": "boom"}

    # A turn produced by another provider never ships its native state to Gemini.
    foreign = AssistantMessage(tool_calls=[_call("get_stock", ticker="X")],
                               provider="other", native={"secret": True})
    assert "secret" not in str(g._contents([foreign]))


# --------------------------------------------------------------------------- #
# Saved chats
# --------------------------------------------------------------------------- #
async def _say(client, messages, chat_id=None):
    return await client.post("/api/assistant/chat", json={
        "messages": [{"role": r, "content": c} for r, c in messages], "chat_id": chat_id})


async def test_chats_are_saved_and_continued(client, monkeypatch):
    fake = _Scripted([AssistantMessage(tool_calls=[_call("get_stock", ticker="bbca")]),
                      AssistantMessage(text="A bank."),
                      AssistantMessage(text="Yes, it pays dividends.")])
    _chain(monkeypatch, (fake, "m1"))

    first = (await _say(client, [("user", "What is   BBCA?")])).json()
    chat_id = first["chat_id"]
    assert chat_id is not None
    second = (await _say(client, [("user", "What is   BBCA?"), ("assistant", "A bank."),
                                  ("user", "Dividends?")], chat_id)).json()
    assert second["chat_id"] == chat_id

    listed = (await client.get("/api/assistant/chats")).json()
    assert [(c["id"], c["title"]) for c in listed] == [(chat_id, "What is BBCA?")]
    detail = (await client.get(f"/api/assistant/chats/{chat_id}")).json()
    assert [(m["role"], m["content"]) for m in detail["messages"]] == [
        ("user", "What is   BBCA?"), ("assistant", "A bank."),
        ("user", "Dividends?"), ("assistant", "Yes, it pays dividends."),
    ]
    assert detail["messages"][1]["tools_used"] == ["get_stock"]


async def test_chats_are_private(client, monkeypatch):
    from tests.conftest import make_user, signed_in

    _chain(monkeypatch, (_Scripted([AssistantMessage(text="mine"),
                                    AssistantMessage(text="theirs")]), "m1"))
    chat_id = (await _say(client, [("user", "secret question")])).json()["chat_id"]

    await make_user("other@example.com")
    async with await signed_in("other@example.com") as other:
        assert (await other.get("/api/assistant/chats")).json() == []
        assert (await other.get(f"/api/assistant/chats/{chat_id}")).status_code == 404
        assert (await other.delete(f"/api/assistant/chats/{chat_id}")).status_code == 404
        # Someone else's id can't be appended to: a new chat starts instead.
        theirs = (await _say(other, [("user", "hi")], chat_id)).json()["chat_id"]
        assert theirs != chat_id
    detail = (await client.get(f"/api/assistant/chats/{chat_id}")).json()
    assert len(detail["messages"]) == 2


async def test_turning_saving_off_deletes_and_stops_saving(client, monkeypatch):
    _chain(monkeypatch, (_Scripted([AssistantMessage(text="a"), AssistantMessage(text="b")]),
                         "m1"))
    await _say(client, [("user", "one")])
    assert len((await client.get("/api/assistant/chats")).json()) == 1

    r = await client.put("/api/preferences", json={"assistant_save_chats": False})
    assert r.json()["assistant_save_chats"] is False
    assert (await client.get("/api/assistant/chats")).json() == []
    assert (await client.get("/api/assistant/status")).json()["save_chats"] is False

    assert (await _say(client, [("user", "two")])).json()["chat_id"] is None
    assert (await client.get("/api/assistant/chats")).json() == []


async def test_chats_expire_after_last_message(client, monkeypatch):
    from datetime import timedelta

    from sqlalchemy import func, select, update

    from database import AsyncSessionLocal
    from models import AssistantChat, ChatMessage
    from services.assistant_chats import purge_expired_chats

    monkeypatch.setattr(settings, "assistant_chat_days", 7)
    _chain(monkeypatch, (_Scripted([AssistantMessage(text="a"), AssistantMessage(text="b"),
                                    AssistantMessage(text="c")]), "m1"))
    old = (await _say(client, [("user", "old")])).json()["chat_id"]
    recent = (await _say(client, [("user", "recent")])).json()["chat_id"]
    async with AsyncSessionLocal() as s:
        # Started long ago but used 6 days ago: kept. Last used 8 days ago: expired.
        long_ago = utcnow() - timedelta(days=30)
        await s.execute(update(AssistantChat).where(AssistantChat.id == recent).values(
            created_at=long_ago, updated_at=utcnow() - timedelta(days=6)))
        await s.execute(update(AssistantChat).where(AssistantChat.id == old).values(
            created_at=long_ago, updated_at=utcnow() - timedelta(days=8)))
        await s.commit()

    assert [c["id"] for c in (await client.get("/api/assistant/chats")).json()] == [recent]
    assert (await client.get(f"/api/assistant/chats/{old}")).status_code == 404
    # Continuing an expired chat starts a new one rather than reviving it.
    assert (await _say(client, [("user", "again")], old)).json()["chat_id"] not in (old, recent)

    assert await purge_expired_chats() == 1
    async with AsyncSessionLocal() as s:
        left = await s.scalar(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.chat_id == old))
        assert left == 0


async def test_delete_one_and_all(client, monkeypatch):
    _chain(monkeypatch, (_Scripted([AssistantMessage(text=str(i)) for i in range(3)]), "m1"))
    ids = [(await _say(client, [("user", f"q{i}")])).json()["chat_id"] for i in range(3)]
    assert (await client.delete(f"/api/assistant/chats/{ids[0]}")).status_code == 204
    assert {c["id"] for c in (await client.get("/api/assistant/chats")).json()} == set(ids[1:])
    assert (await client.delete("/api/assistant/chats")).status_code == 204
    assert (await client.get("/api/assistant/chats")).json() == []


async def test_trimmed_history_starts_with_user_turn(client, monkeypatch):
    fake = _Scripted([AssistantMessage(text="ok")])
    _chain(monkeypatch, (fake, "m1"))
    r = await _say(client, [("assistant", "older answer"), ("user", "next question")])
    assert r.status_code == 200
    assert isinstance(fake.seen[0][0], UserMessage)


def test_chat_title_is_first_question_shortened():
    from services.assistant_chats import title_for

    assert title_for("  Is\nBBCA   cheap? ") == "Is BBCA cheap?"
    long = title_for("x" * 200)
    assert len(long) == 80 and long.endswith("…")


def test_tool_output_is_plain_json():
    from datetime import date

    from schemas import EquityPoint

    out = service._jsonable({"curve": [EquityPoint(date=date(2026, 3, 10), value=1.5)]})
    assert out == {"curve": [{"date": "2026-03-10", "value": 1.5,
                              "return_pct": None, "benchmark_pct": None}]}
