"""Settings rules (the tests read no .env: BURSA_ENV_FILE is empty)."""

from config import Settings


def test_https_address_turns_on_secure_cookies():
    assert Settings(public_url="https://bursa.tail1234.ts.net").session_cookie_secure


def test_plain_http_keeps_the_setting():
    assert not Settings(public_url="http://localhost:5173").session_cookie_secure
    assert Settings(
        public_url="http://localhost:5173", session_cookie_secure=True
    ).session_cookie_secure
