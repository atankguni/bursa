"""Nightly SQLite backups: consistent, checked, compressed, private, pruned, restorable."""

import gzip
import sqlite3
import stat
import subprocess

import pytest

from config import settings
from system import backup


def _make_db(path):
    con = sqlite3.connect(path)
    con.execute("create table t (x integer)")
    con.executemany("insert into t values (?)", [(i,) for i in range(1000)])
    con.commit()
    con.close()


def test_backup_is_restorable_private_and_pruned(tmp_path, monkeypatch):
    db = tmp_path / "bursa.db"
    _make_db(db)
    key = tmp_path / "secret.key"
    key.write_text("k" * 40)
    monkeypatch.setattr(settings, "secret_key", None)
    monkeypatch.setattr(settings, "secret_key_file", str(key))
    dest = tmp_path / "backups"

    stamps = ["2026-10-01_0230", "2026-10-02_0230", "2026-10-03_0230"]
    targets = [backup.backup_sqlite(db, dest, keep=2, stamp=s) for s in stamps]
    target = targets[-1]

    # Only the newest two remain, each with its key copy.
    names = sorted(p.name for p in dest.iterdir())
    assert names == [
        "bursa-2026-10-02_0230.db.gz", "bursa-2026-10-02_0230.secret.key",
        "bursa-2026-10-03_0230.db.gz", "bursa-2026-10-03_0230.secret.key",
    ]
    for p in dest.iterdir():
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert stat.S_IMODE(dest.stat().st_mode) == 0o700

    restored = tmp_path / "restored.db"
    backup.restore_sqlite(target, restored)
    assert sqlite3.connect(restored).execute("select count(*) from t").fetchone()[0] == 1000
    assert stat.S_IMODE(restored.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):  # never overwrites a database
        backup.restore_sqlite(target, restored)


def test_damaged_files_are_refused(tmp_path):
    db = tmp_path / "bursa.db"
    _make_db(db)
    raw = bytearray(db.read_bytes())
    raw[4096:8192] = b"\xff" * 4096  # wipe the table's first page
    broken = tmp_path / "broken.db"
    broken.write_bytes(bytes(raw))
    with pytest.raises(backup.BadBackup):
        backup.check_integrity(broken)

    packed = tmp_path / "broken.db.gz"
    packed.write_bytes(gzip.compress(bytes(raw)))
    with pytest.raises(backup.BadBackup):
        backup.restore_sqlite(packed, tmp_path / "restored.db")
    assert not list(tmp_path.glob("restored.db*"))  # nothing left behind


def test_wal_database_leaves_no_temp_files(tmp_path, monkeypatch):
    db = tmp_path / "bursa.db"
    _make_db(db)
    live = sqlite3.connect(db)  # like the running app: WAL mode, connection open
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("insert into t values (-1)")
    live.commit()
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    try:
        backup.backup_sqlite(db, tmp_path / "b", keep=7, stamp="2026-10-01_0230")
    finally:
        live.close()
    assert [p.name for p in (tmp_path / "b").iterdir()] == ["bursa-2026-10-01_0230.db.gz"]


def test_no_key_copy_when_secret_comes_from_env(tmp_path, monkeypatch):
    db = tmp_path / "bursa.db"
    _make_db(db)
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    backup.backup_sqlite(db, tmp_path / "b", keep=7, stamp="2026-10-01_0230")
    assert [p.name for p in (tmp_path / "b").iterdir()] == ["bursa-2026-10-01_0230.db.gz"]


def test_only_sqlite_is_backed_up():
    path = backup.sqlite_path("sqlite+aiosqlite:///./data/bursa.db")
    assert path is not None and path.name == "bursa.db"
    assert backup.sqlite_path("postgresql+asyncpg://u:p@h/bursa") is None
    assert backup.sqlite_path("sqlite+aiosqlite:///:memory:") is None


def _age_keys(tmp_path):
    """A fresh age key pair: (private key file, public key)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    identity = tmp_path / "key.txt"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    public = next(
        line.split(": ", 1)[1]
        for line in identity.read_text().splitlines()
        if line.startswith("# public key: ")
    )
    return identity, public


def test_encrypted_backup_needs_the_private_key(tmp_path, monkeypatch):
    db = tmp_path / "bursa.db"
    _make_db(db)
    key = tmp_path / "secret.key"
    key.write_text("server-secret-" * 4)
    monkeypatch.setattr(settings, "secret_key", None)
    monkeypatch.setattr(settings, "secret_key_file", str(key))
    identity, public = _age_keys(tmp_path)
    dest = tmp_path / "backups"

    target = backup.backup_sqlite(db, dest, keep=7, stamp="2026-10-01_0230", recipient=public)

    assert sorted(p.name for p in dest.iterdir()) == [
        "bursa-2026-10-01_0230.db.gz.age", "bursa-2026-10-01_0230.secret.key.age",
    ]
    for p in dest.iterdir():
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
        assert p.read_bytes().startswith(b"age-encryption.org/v1")
    assert b"server-secret" not in (dest / "bursa-2026-10-01_0230.secret.key.age").read_bytes()

    with pytest.raises(ValueError, match="identity"):
        backup.restore_sqlite(target, tmp_path / "a.db")
    other_identity, _ = _age_keys(tmp_path / "other")
    with pytest.raises(RuntimeError, match="decrypt"):
        backup.restore_sqlite(target, tmp_path / "b.db", identity=other_identity)
    assert not list(tmp_path.glob("b.db*"))

    restored = tmp_path / "restored.db"
    backup.restore_sqlite(target, restored, identity=identity)
    assert sqlite3.connect(restored).execute("select count(*) from t").fetchone()[0] == 1000


def test_prune_counts_plain_and_encrypted_together(tmp_path):
    dest = tmp_path / "b"
    dest.mkdir()
    for name in [
        "bursa-2026-10-01_0230.db.gz", "bursa-2026-10-01_0230.secret.key",
        "bursa-2026-10-02_0230.db.gz.age", "bursa-2026-10-02_0230.secret.key.age",
        "bursa-2026-10-03_0230.db.gz.age",
    ]:
        (dest / name).write_bytes(b"x")
    assert backup.prune(dest, keep=2) == ["2026-10-01_0230"]
    assert sorted(p.name for p in dest.iterdir()) == [
        "bursa-2026-10-02_0230.db.gz.age", "bursa-2026-10-02_0230.secret.key.age",
        "bursa-2026-10-03_0230.db.gz.age",
    ]


def test_recipient_must_be_an_age_public_key(tmp_path):
    from pydantic import ValidationError

    from config import Settings

    _, public = _age_keys(tmp_path)
    assert Settings(backup_recipient=f"  {public} ").backup_recipient == public
    assert Settings(backup_recipient="").backup_recipient is None
    for bad in ["age1short", "AGE-SECRET-KEY-1" + "Q" * 58, "ssh-ed25519 AAAA"]:
        with pytest.raises(ValidationError, match="age public key"):
            Settings(backup_recipient=bad)
