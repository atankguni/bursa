"""
services/crypto.py
------------------
The server secret and what it protects:

* `encrypt` / `decrypt`: authenticator-app (TOTP) secrets are stored encrypted
  (Fernet: AES-128-CBC + HMAC-SHA256), so a copy of the database alone can't
  generate sign-in codes.
* `keyed_hash`: recovery codes and emailed codes are stored as HMAC-SHA256 with
  the secret, so a database copy can't be brute-forced offline.

The secret comes from SECRET_KEY, or is generated once into `secret_key_file`
(next to the SQLite database, in the mounted data folder). Losing it means 2FA
has to be reset for every user, so back it up with the database.
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
from functools import cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config import settings

log = logging.getLogger("bursa.crypto")


class SecretError(RuntimeError):
    """Encrypted data can't be read with the current server secret."""


def _load_or_create(path: Path) -> str:
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    # Created owner-only, and never overwritten (O_EXCL) if another process won.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text().strip()
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    log.warning("Generated the server secret at %s: back it up with the database", path)
    return key


@cache
def _secret() -> bytes:
    raw = settings.secret_key or _load_or_create(Path(settings.secret_key_file))
    if len(raw) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters")
    return raw.encode()


def _subkey(purpose: str) -> bytes:
    # One key per use, so a value from one purpose can't be replayed in another.
    return hmac.new(_secret(), purpose.encode(), hashlib.sha256).digest()


@cache
def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_subkey("encrypt")))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretError("stored secret can't be decrypted (server secret changed?)") from exc


def keyed_hash(value: str, purpose: str) -> str:
    return hmac.new(_subkey(f"hash:{purpose}"), value.encode(), hashlib.sha256).hexdigest()


def ensure_secret() -> None:
    """Load (or create) the secret at startup, so problems show up immediately."""
    _secret()
