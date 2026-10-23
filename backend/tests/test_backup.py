"""Nightly SQLite backups: consistent, checked, compressed, private, pruned, restorable."""

import gzip
import sqlite3
import stat

import pytest

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
