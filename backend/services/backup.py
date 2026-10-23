"""
services/backup.py
------------------
Nightly backups of a SQLite database: a consistent online copy (SQLite's backup
API, safe while the app writes), checked with `PRAGMA integrity_check`,
gzip-compressed, plus the 2FA server secret file (without it, a restored
database can't read 2FA secrets). The newest BACKUP_KEEP backups are kept;
files are readable by the owner only.

They sit next to the database (BACKUP_DIR), which guards against mistakes and
corruption but not against losing the disk: copy them elsewhere too.
PostgreSQL is skipped: use its own tools (pg_dump).

Run one now: `docker compose exec backend python -m services.backup`
Restore one: `python -m services.backup restore <backup.db.gz> <new.db>`
(steps in docs/configuration.md).
"""

import asyncio
import gzip
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

from config import settings

log = logging.getLogger("bursa.backup")

PREFIX = "bursa-"
DB_SUFFIX = ".db.gz"
KEY_SUFFIX = ".secret.key"


def sqlite_path(url: str) -> Path | None:
    """The database file behind a SQLite URL, or None for other databases."""
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or not parsed.database:
        return None
    if parsed.database == ":memory:":
        return None
    return Path(parsed.database)


class BadBackup(RuntimeError):
    """A copy failed SQLite's integrity check."""


def _private(path: Path) -> None:
    os.chmod(path, 0o600)


def check_integrity(db: Path) -> None:
    """Raise BadBackup unless SQLite's full integrity check passes."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        result = [r[0] for r in con.execute("PRAGMA integrity_check")]
    except sqlite3.DatabaseError as exc:  # too damaged to even check
        result = [str(exc)]
    finally:
        con.close()
    if result != ["ok"]:
        raise BadBackup(f"{db}: " + "; ".join(str(r) for r in result[:5]))


def backup_sqlite(db: Path, dest: Path, keep: int, stamp: str) -> Path:
    """Write `bursa-<stamp>.db.gz` (+ the secret key file) into `dest`; prune old ones."""
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    tmp = dest / f".{PREFIX}{stamp}.db.tmp"
    target = dest / f"{PREFIX}{stamp}{DB_SUFFIX}"
    try:
        src = sqlite3.connect(db)
        try:
            out = sqlite3.connect(tmp)
            try:
                src.backup(out)
            finally:
                out.close()
        finally:
            src.close()
        check_integrity(tmp)  # a damaged copy is never kept as a backup
        partial = target.with_name(target.name + ".part")
        with open(tmp, "rb") as raw, gzip.open(partial, "wb", compresslevel=6) as packed:
            shutil.copyfileobj(raw, packed, length=1024 * 1024)
        _private(partial)
        partial.replace(target)  # never leave a half-written backup under the real name
    finally:
        tmp.unlink(missing_ok=True)

    key_file = Path(settings.secret_key_file)
    if not settings.secret_key and key_file.is_file():
        key_copy = dest / f"{PREFIX}{stamp}{KEY_SUFFIX}"
        shutil.copyfile(key_file, key_copy)
        _private(key_copy)

    prune(dest, keep)
    return target


def prune(dest: Path, keep: int) -> list[str]:
    """Delete all but the newest `keep` backups (and their key copies)."""
    stamps = sorted(
        (p.name[len(PREFIX) : -len(DB_SUFFIX)] for p in dest.glob(f"{PREFIX}*{DB_SUFFIX}")),
        reverse=True,
    )
    removed = stamps[max(1, keep) :]
    for stamp in removed:
        for suffix in (DB_SUFFIX, KEY_SUFFIX):
            (dest / f"{PREFIX}{stamp}{suffix}").unlink(missing_ok=True)
    return removed


def restore_sqlite(backup: Path, target: Path) -> None:
    """Unpack `backup` into `target` (which must not exist) and check it."""
    if target.exists():
        raise FileExistsError(f"{target} exists; move it aside first")
    partial = target.with_name(target.name + ".part")
    with gzip.open(backup, "rb") as packed, open(partial, "wb") as raw:
        shutil.copyfileobj(packed, raw, length=1024 * 1024)
    try:
        check_integrity(partial)
    except BadBackup:
        partial.unlink()
        raise
    _private(partial)
    partial.replace(target)


async def run_backup() -> Path | None:
    """Back up the configured database now. None when not SQLite or disabled."""
    if not settings.backup_enabled:
        return None
    db = sqlite_path(settings.database_url)
    if db is None:
        log.info("Backups only cover SQLite; use your database's own tools (pg_dump, ...)")
        return None
    if not db.is_file():
        log.warning("Backup skipped: database file %s not found", db)
        return None
    stamp = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d_%H%M")
    target = await asyncio.to_thread(
        backup_sqlite, db, Path(settings.backup_dir), settings.backup_keep, stamp
    )
    log.info(
        "Backup written: %s (%.1f MB, keeping the newest %d)",
        target, target.stat().st_size / 1e6, settings.backup_keep,
    )
    return target


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if sys.argv[1:2] == ["restore"] and len(sys.argv) == 4:
        restore_sqlite(Path(sys.argv[2]), Path(sys.argv[3]))
        log.info("Restored %s to %s (integrity check passed)", sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 1:
        asyncio.run(run_backup())
    else:
        raise SystemExit("usage: python -m services.backup [restore <backup.db.gz> <new.db>]")
