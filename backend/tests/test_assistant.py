"""Assistant loop, tools and Gemini adapter (no network: providers are faked)."""

import assistant.service as service
from assistant.providers import ChatProvider, GeminiProvider, Reply, ToolCall
from assistant.tools import _ticker, available_tools
from config import settings


class _ScriptedProvider(ChatProvider):
    """Returns pre-scripted replies; records what the loop sent back."""

    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.tool_results = []
        self.calls = 0

    def start(self, system, history):
        return [dict(t) for t in history]

    async def generate(self, model, system, transcript, tools, allow_tools=True):
        self.calls += 1
        self.last_tools = [t.name for t in tools]
        return self.replies.pop(0)

    def add_model_turn(self, transcript, reply):
        transcript.append({"role": "assistant", "calls": reply.tool_calls})

    def add_tool_results(self, transcript, results):
        self.tool_results.extend(results)
        transcript.append({"role": "tool", "results": results})


def _install(monkeypatch, provider):
    monkeypatch.setattr(service, "provider_for", lambda name, key: provider)
    monkeypatch.setattr(service, "_usage", {})


async def test_chat_runs_tools_then_answers(client, monkeypatch):
    fake = _ScriptedProvider([
        Reply("", [ToolCall("get_stock", {"ticker": "bbca"})], model="m1"),
        Reply("BBCA is a bank.", model="m1"),
    ])
    _install(monkeypatch, fake)

    r = await client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "Tell me about BBCA"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "BBCA is a bank." and body["tools_used"] == ["get_stock"]
    call, result = fake.tool_results[0]
    assert result["ticker"] == "BBCA.JK"  # "bbca" normalised to the Yahoo symbol
    assert "get_portfolio" not in fake.last_tools  # personal data is off by default


async def test_unknown_tool_and_tool_errors_are_reported_not_raised(client, monkeypatch):
    fake = _ScriptedProvider([
        Reply("", [ToolCall("delete_everything", {}), ToolCall("get_fundamentals",
                                                               {"ticker": "NOPE"})]),
        Reply("Sorry, I can't do that."),
    ])
    _install(monkeypatch, fake)
    r = await client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "delete my data"}]})
    assert r.status_code == 200
    results = [res for _, res in fake.tool_results]
    assert "unknown tool" in results[0]["error"]
    assert "no fundamentals" in results[1]["error"]


async def test_tool_rounds_are_capped(client, monkeypatch):
    monkeypatch.setattr(settings, "assistant_max_tool_rounds", 2)
    loop = [Reply("", [ToolCall("market_overview", {})]) for _ in range(2)]
    fake = _ScriptedProvider([*loop, Reply("Final answer.")])
    _install(monkeypatch, fake)
    r = await client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "loop forever"}]})
    assert r.json()["reply"] == "Final answer." and fake.calls == 3


async def test_not_configured_and_daily_cap(client, monkeypatch):
    monkeypatch.setattr(service, "provider_for", lambda name, key: None)
    r = await client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]

    _install(monkeypatch, _ScriptedProvider([Reply("ok")]))
    monkeypatch.setattr(settings, "assistant_daily_limit", 1)
    assert (await client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "one"}]})).status_code == 200
    r = await client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "two"}]})
    assert r.status_code == 503 and "Daily limit" in r.json()["detail"]


async def test_last_message_must_be_user(client):
    r = await client.post("/api/assistant/chat", json={
        "messages": [{"role": "assistant", "content": "hello"}]})
    assert r.status_code == 422


def test_personal_tools_only_when_enabled():
    assert "get_portfolio" not in available_tools(False)
    assert {"get_portfolio", "get_watchlist"} <= set(available_tools(True))


def test_ticker_normalisation():
    assert _ticker("bbca") == "BBCA.JK" and _ticker("BBCA.JK") == "BBCA.JK"


async def test_gemini_adapter_wire_format(monkeypatch):
    sent = []
    responses = [{"candidates": [{"content": {"role": "model", "parts": [
        {"functionCall": {"name": "get_stock", "args": {"ticker": "BBCA"}},
         "thoughtSignature": "sig-123"}]}}]}]

    g = GeminiProvider("test-key")
    monkeypatch.setattr(g, "_post", lambda model, body: sent.append(body) or responses.pop(0))
    transcript = g.start("sys", [{"role": "user", "content": "q"},
                                 {"role": "assistant", "content": "a"}])
    assert [t["role"] for t in transcript] == ["user", "model"]

    reply = await g.generate("m", "sys", transcript, [
        *[t.spec for t in available_tools(False).values()]], allow_tools=False)
    assert reply.tool_calls == [ToolCall("get_stock", {"ticker": "BBCA"})]
    assert sent[0]["toolConfig"]["functionCallingConfig"]["mode"] == "NONE"
    assert sent[0]["systemInstruction"]["parts"][0]["text"] == "sys"

    g.add_model_turn(transcript, reply)
    g.add_tool_results(transcript, [(reply.tool_calls[0], {"price": 1})])
    # The model turn is echoed verbatim so Gemini 3's thought signature survives.
    assert transcript[-2]["parts"][0]["thoughtSignature"] == "sig-123"
    assert transcript[-1]["parts"][0]["functionResponse"] == {
        "name": "get_stock", "response": {"result": {"price": 1}}}
