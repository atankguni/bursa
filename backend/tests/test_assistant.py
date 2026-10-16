"""Assistant loop, provider chain/registry, tools and the Gemini adapter (no network)."""

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
from config import settings


class _Scripted(ChatProvider):
    """Fake adapter: replays scripted replies (or raises) and records what it saw."""

    name = "fake"
    credential_env = "FAKE_API_KEY"

    def __init__(self, script, name="fake"):
        self.script = list(script)
        self.name = name
        self.seen = []  # messages passed on each call
        self.allow_tools_seen = []

    @classmethod
    def from_settings(cls, settings):  # pragma: no cover - tests build instances directly
        return None

    async def complete(self, *, model, system, messages, tools, allow_tools=True):
        self.seen.append(list(messages))
        self.allow_tools_seen.append(allow_tools)
        self.tool_names = [t.name for t in tools]
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        step.provider, step.model = self.name, model
        return step


def _chain(monkeypatch, *attempts):
    monkeypatch.setattr(service, "resolve_chain", lambda: list(attempts))
    monkeypatch.setattr(service, "_usage", {})


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
    assert tool_msg.results[0].content["ticker"] == "BBCA.JK"  # "bbca" normalised
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
    first = _Scripted([AssistantMessage(tool_calls=[_call("market_overview")]),
                       ProviderBusyError("429 quota")], name="primary")
    second = _Scripted([AssistantMessage(text="Answered by backup.")], name="backup")
    _chain(monkeypatch, (first, "a"), (second, "b"))

    body = (await _ask(client, "how is the market?")).json()
    assert body["reply"] == "Answered by backup."
    assert (body["provider"], body["model"]) == ("backup", "b")
    # The backup starts from the user's question only: no turns (or native state)
    # produced by the other provider leak into its request.
    assert len(second.seen[0]) == 1 and isinstance(second.seen[0][0], UserMessage)


async def test_rejected_attempt_falls_back(client, monkeypatch):
    bad = _Scripted([ProviderError("401 bad key")], name="badkey")
    good = _Scripted([AssistantMessage(text="ok")], name="good")
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
        def from_settings(cls, settings):
            return cls([], name="keyed")

    class _NoKey(_Keyed):
        name = "nokey"
        credential_env = "NOKEY_API_KEY"

        @classmethod
        def from_settings(cls, settings):
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
    assert _ticker("bbca") == "BBCA.JK" and _ticker("BBCA.JK") == "BBCA.JK"


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
