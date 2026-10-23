"""
accounts/passwords.py
---------------------
Password strength, following NIST SP 800-63B: no composition rules ("an
uppercase, a digit, a symbol" gives `Password1!`). Instead a minimum length, a
zxcvbn guessability score (common passwords, keyboard runs, repeats, dates, the
user's own name and email) and, optionally, a check against passwords leaked in
data breaches.

The breach check uses the Have I Been Pwned range API with k-anonymity: only the
first 5 hex characters of the password's SHA-1 are sent, and the match is made
locally. If the service can't be reached, the check is skipped (fail open), so an
outage never blocks sign-up.
"""

import asyncio
import hashlib
import logging
import re
import urllib.request

from config import settings

log = logging.getLogger("bursa.passwords")

MAX_LENGTH = 256
# Scoring is slow on very long input; past this length a password is strong anyway.
_SCORED_LENGTH = 100
# Words an attacker would try first against this app.
_APP_WORDS = ("bursa", "saham", "idx", "bei", "ihsg", "invest", "investor", "stock")
_RANGE_URL = "https://api.pwnedpasswords.com/range/"


def _user_words(email: str, name: str) -> list[str]:
    local = email.split("@")[0]
    return [w for w in (*_APP_WORDS, email, local, *name.split()) if w]


# What must remain once personal / app words and digits are removed.
_OWN_LETTERS = 6


def _mostly_personal(password: str, words: list[str]) -> bool:
    """Built from the name, email or app words plus digits, e.g. "budisantoso2024"
    (zxcvbn knows those words but still rates such combinations too well)."""
    rest = password.lower()
    removed = False
    for word in sorted({w.lower() for w in words if len(w) >= 3}, key=len, reverse=True):
        if word in rest:
            rest = rest.replace(word, "")
            removed = True
    return removed and len(re.sub(r"[^a-z]", "", rest)) < _OWN_LETTERS


def strength_problem(password: str, *, email: str = "", name: str = "") -> str | None:
    """What's wrong with the password (offline checks), or None when it's fine."""
    if len(password) < settings.password_min_length:
        return f"Password must be at least {settings.password_min_length} characters"
    if len(password) > MAX_LENGTH:
        return f"Password is too long ({MAX_LENGTH} characters at most)"
    if email and password.strip().lower() == email.strip().lower():
        return "Password can't be your email address"
    words = _user_words(email, name)
    if _mostly_personal(password, words):
        return (
            "This password is too easy to guess. It's mostly your name, email or the "
            "app's name; add words of your own."
        )
    from zxcvbn import zxcvbn  # its dictionaries take ~9 MB: load on first use

    result = zxcvbn(password[:_SCORED_LENGTH], user_inputs=words)
    if result["score"] >= settings.password_min_score:
        return None
    feedback = result.get("feedback") or {}
    hints = [feedback.get("warning") or "", *(feedback.get("suggestions") or [])]
    detail = " ".join(h.strip().rstrip(".") + "." for h in hints if h.strip())
    return f"This password is too easy to guess. {detail}".strip()


def _fetch_range(prefix: str) -> str:
    request = urllib.request.Request(
        _RANGE_URL + prefix,
        # Padding hides how many hashes share the prefix from anyone watching.
        headers={"Add-Padding": "true", "User-Agent": "Bursa password check"},
    )
    with urllib.request.urlopen(request, timeout=settings.password_breach_timeout) as r:
        return r.read().decode("utf-8")


async def breach_count(password: str) -> int | None:
    """How often the password appears in known breaches; None if not checked."""
    if not settings.password_breach_check:
        return None
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324 - HIBP's format
    prefix, suffix = digest[:5], digest[5:]
    try:
        body = await asyncio.to_thread(_fetch_range, prefix)
    except Exception as exc:  # noqa: BLE001 - any failure: skip the check
        log.warning("Leaked-password check unavailable, skipped: %s", exc)
        return None
    for line in body.splitlines():
        candidate, _, count = line.partition(":")
        if candidate.strip() == suffix:
            return int(count.strip() or 0)  # padding rows have a count of 0
    return 0


async def password_problem(password: str, *, email: str = "", name: str = "") -> str | None:
    """Every check (strength, then breaches): the reason it's refused, or None."""
    problem = strength_problem(password, email=email, name=name)
    if problem:
        return problem
    if await breach_count(password):
        return (
            "This password has appeared in a data breach, so attackers try it first. "
            "Choose a different one."
        )
    return None


async def is_weak(password: str, *, email: str = "", name: str = "") -> bool | None:
    """Whether today's policy would refuse this password; None when that's unknown
    (the breach service couldn't be reached), so a previous verdict is kept."""
    if strength_problem(password, email=email, name=name):
        return True
    if not settings.password_breach_check:
        return False
    count = await breach_count(password)
    return None if count is None else count > 0
