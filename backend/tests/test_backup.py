"""Nightly SQLite backups: consistent, compressed, private, pruned."""

import gzip
import sqlite3
import stat

from config import settings
from services import backup


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
    for s in stamps:
        target = backup.backup_sqlite(db, dest, keep=2, stamp=s)

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
    restored.write_bytes(gzip.decompress(target.read_bytes()))
    assert sqlite3.connect(restored).execute("select count(*) from t").fetchone()[0] == 1000


def test_no_key_copy_when_secret_comes_from_env(tmp_path, monkeypatch):
    db = tmp_path / "bursa.db"
    _make_db(db)
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    backup.backup_sqlite(db, tmp_path / "b", keep=7, stamp="2026-10-01_0230")
    assert [p.name for p in (tmp_path / "b").iterdir()] == ["bursa-2026-10-01_0230.db.gz"]


def test_only_sqlite_is_backed_up():
    assert backup.sqlite_path("sqlite+aiosqlite:///./data/bursa.db").name == "bursa.db"
    assert backup.sqlite_path("postgresql+asyncpg://u:p@h/bursa") is None
    assert backup.sqlite_path("sqlite+aiosqlite:///:memory:") is None
