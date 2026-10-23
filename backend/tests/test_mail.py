"""Mail service: provider selection, validation, SMTP / Resend adapters, endpoints.
No real mail server or API is contacted: smtplib and urlopen are faked."""

import base64
import io
import json
import smtplib
import urllib.error

import pytest

import mail
import mail.resend as resend_mod
import mail.smtp as smtp_mod
from config import settings
from mail.base import Attachment, Email, MailBusyError, MailError, split_addresses, validate
from mail.registry import get_provider, setup_hint
from mail.resend import ResendProvider


@pytest.fixture(autouse=True)
def _mail_off(monkeypatch):
    """Start every test with email disabled, whatever backend/.env says."""
    for k in ("mail_provider", "mail_from", "mail_to", "smtp_host", "smtp_username",
              "smtp_password", "resend_api_key"):
        monkeypatch.setattr(settings, k, None)


@pytest.fixture
def smtp_settings(monkeypatch):
    for k, v in {
        "mail_provider": "smtp", "mail_from": "Bursa <bursa@example.com>",
        "mail_to": "me@example.com", "smtp_host": "smtp.example.com", "smtp_port": 587,
        "smtp_security": "starttls", "smtp_username": "me@example.com",
        "smtp_password": "secret",
    }.items():
        monkeypatch.setattr(settings, k, v)


class FakeSMTP:
    """Records the conversation; `fail` raises from the named step."""

    instances: list[FakeSMTP] = []
    fail: dict[str, Exception] = {}

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.calls, self.sent = host, port, [], []
        if "connect" in self.fail:
            raise self.fail["connect"]
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("quit")

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user))
        if "login" in self.fail:
            raise self.fail["login"]

    def send_message(self, msg):
        self.calls.append("send")
        if "send" in self.fail:
            raise self.fail["send"]
        self.sent.append(msg)


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail = [], {}
    monkeypatch.setattr(smtp_mod.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtp_mod.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


# --- registry / configuration -------------------------------------------------
def test_disabled_without_a_provider():
    assert get_provider() is None and not mail.configured()
    assert "MAIL_PROVIDER" in setup_hint()


def test_provider_needs_its_settings(monkeypatch):
    monkeypatch.setattr(settings, "mail_provider", "smtp")
    assert get_provider() is None and "SMTP_HOST" in setup_hint()
    monkeypatch.setattr(settings, "mail_provider", "resend")
    assert get_provider() is None and "RESEND_API_KEY" in setup_hint()
    monkeypatch.setattr(settings, "resend_api_key", "re_x")
    assert isinstance(get_provider(), ResendProvider)


def test_unknown_or_misconfigured_provider_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "mail_provider", "carrier-pigeon")
    assert get_provider() is None
    monkeypatch.setattr(settings, "mail_provider", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_security", "tls-ish")
    assert get_provider() is None


# --- validation -----------------------------------------------------------------
def _ok(**kw) -> Email:
    base = {"subject": "Hi", "text": "Body", "to": ("a@example.com",), "sender": "b@example.com"}
    return Email(**(base | kw))


def test_validation_rejects_header_injection_and_bad_addresses():
    validate(_ok())
    validate(_ok(to=("Name <a@example.com>",)))
    for bad in (
        _ok(subject="Hi\r\nBcc: x@evil.com"),
        _ok(subject=" "),
        _ok(text=""),
        _ok(to=()),
        _ok(to=("not-an-address",)),
        _ok(to=("a@example.com\nBcc: x@evil.com",)),
        _ok(reply_to="nope"),
        _ok(attachments=(Attachment("../x.csv", b""),)),
    ):
        with pytest.raises(MailError):
            validate(bad)


def test_split_addresses():
    assert split_addresses(None) == ()
    assert split_addresses("a@x.com, Me <b@y.com>") == ("a@x.com", "Me <b@y.com>")


# --- service + SMTP ---------------------------------------------------------------
async def test_send_fills_defaults_and_builds_mime(smtp_settings, fake_smtp):
    msg_id = await mail.send(Email(
        subject="Digest", text="plain", html="<p>rich</p>",
        attachments=(Attachment("r.csv", b"a,b\n", "text/csv"),),
    ))
    (server,) = fake_smtp.instances
    assert (server.host, server.port) == ("smtp.example.com", 587)
    assert server.calls == ["starttls", ("login", "me@example.com"), "send", "quit"]
    (sent,) = server.sent
    assert sent["From"] == "Bursa <bursa@example.com>" and sent["To"] == "me@example.com"
    assert msg_id is not None and msg_id.endswith("@example.com>")
    assert sent["Message-ID"] == msg_id
    parts = [p.get_content_type() for p in sent.walk()]
    assert {"text/plain", "text/html", "text/csv"} <= set(parts)


async def test_ssl_mode_skips_starttls(smtp_settings, fake_smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", "ssl")
    monkeypatch.setattr(settings, "smtp_port", 465)
    await mail.send(Email(subject="x", text="y"))
    assert fake_smtp.instances[0].calls[0] == ("login", "me@example.com")


async def test_smtp_errors_are_classified(smtp_settings, fake_smtp):
    email = Email(subject="x", text="y")
    fake_smtp.fail = {"login": smtplib.SMTPAuthenticationError(535, b"bad")}
    with pytest.raises(MailError, match="app password") as err:
        await mail.send(email)
    assert not isinstance(err.value, MailBusyError)
    assert "secret" not in str(err.value)  # credentials never echoed

    fake_smtp.fail = {"send": smtplib.SMTPDataError(451, b"try later")}
    with pytest.raises(MailBusyError):
        await mail.send(email)
    fake_smtp.fail = {"connect": ConnectionRefusedError("refused")}
    with pytest.raises(MailBusyError, match="Can't reach"):
        await mail.send(email)
    assert await mail.send_quietly(email) is False  # background use never raises


async def test_not_configured_send(monkeypatch):
    with pytest.raises(mail.MailNotConfiguredError):
        await mail.send(Email(subject="x", text="y", to=("a@example.com",)))
    assert await mail.send_quietly(Email(subject="x", text="y")) is False


# --- Resend ----------------------------------------------------------------------
class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> None:
        return None


async def test_resend_request(monkeypatch):
    seen = {}

    def urlopen(req, timeout=None):
        seen["url"], seen["headers"] = req.full_url, dict(req.header_items())
        seen["body"] = json.loads(req.data)
        return FakeResponse(b'{"id": "abc-123"}')

    monkeypatch.setattr(resend_mod.urllib.request, "urlopen", urlopen)
    provider = ResendProvider(api_key="re_key", timeout=5)
    msg_id = await provider.send(_ok(html="<b>x</b>", attachments=(Attachment("a.txt", b"hi"),)))
    assert msg_id == "abc-123" and seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["Authorization"] == "Bearer re_key"
    body = seen["body"]
    assert body["to"] == ["a@example.com"] and body["html"] == "<b>x</b>"
    assert base64.b64decode(body["attachments"][0]["content"]) == b"hi"


@pytest.mark.parametrize(("code", "busy"), [(429, True), (503, True), (422, False)])
async def test_resend_errors_are_classified(monkeypatch, code, busy):
    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, code, "err", {},  # type: ignore[arg-type]
            io.BytesIO(b'{"message": "domain is not verified"}'),
        )

    monkeypatch.setattr(resend_mod.urllib.request, "urlopen", urlopen)
    with pytest.raises(MailError, match=f"HTTP {code}") as err:
        await ResendProvider(api_key="k", timeout=5).send(_ok())
    assert isinstance(err.value, MailBusyError) is busy


# --- endpoints -------------------------------------------------------------------
async def test_status_and_test_endpoints(client, smtp_settings, fake_smtp):
    status = (await client.get("/api/mail/status")).json()
    assert status == {"configured": True, "provider": "smtp",
                      "sender": "Bursa <bursa@example.com>", "recipients": 1, "setup_hint": ""}
    r = (await client.post("/api/mail/test")).json()
    assert r["delivered"] is True and r["message_id"]
    assert fake_smtp.instances[0].sent[0]["Subject"] == "Bursa test email"


async def test_test_endpoint_errors(client, monkeypatch, smtp_settings, fake_smtp):
    fake_smtp.fail = {"login": smtplib.SMTPAuthenticationError(535, b"bad")}
    r = await client.post("/api/mail/test")
    assert r.status_code == 502 and "app password" in r.json()["detail"]

    monkeypatch.setattr(settings, "mail_to", None)
    r = await client.post("/api/mail/test")
    assert r.status_code == 400 and "MAIL_TO" in r.json()["detail"]

    monkeypatch.setattr(settings, "mail_provider", None)
    r = await client.post("/api/mail/test")
    assert r.status_code == 400 and "MAIL_PROVIDER" in r.json()["detail"]
    assert (await client.get("/api/mail/status")).json()["configured"] is False


# --- console (development) -------------------------------------------------------
async def test_console_provider_prints_instead_of_sending(monkeypatch, caplog):
    monkeypatch.setattr(settings, "mail_provider", "console")
    monkeypatch.setattr(settings, "public_url", "http://localhost:5173")
    assert mail.configured()  # no MAIL_FROM needed
    with caplog.at_level("WARNING", logger="bursa.mail.console"):
        msg_id = await mail.send(Email(subject="Your Bursa code: 123456", text="Code 123456",
                                       to=("a@example.com",)))
    assert msg_id and msg_id.startswith("console-")
    assert "Your Bursa code: 123456" in caplog.text and "To: a@example.com" in caplog.text


@pytest.mark.parametrize("url", ["https://bursa.example.com", "http://192.168.1.10:5173"])
def test_console_provider_refuses_non_local_servers(monkeypatch, url):
    monkeypatch.setattr(settings, "mail_provider", "console")
    monkeypatch.setattr(settings, "public_url", url)
    assert get_provider() is None and not mail.configured()
    assert "localhost" in setup_hint()
