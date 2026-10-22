"""
services/backup.py
------------------
Nightly backups of a SQLite database: a consistent online copy (SQLite's backup
API, safe while the app writes), gzip-compressed, plus the 2FA server secret
file (without it, a restored database can't read 2FA secrets). The newest
BACKUP_KEEP backups are kept; files are readable by the owner only.

They sit next to the database (BACKUP_DIR), which guards against mistakes and
corruption but not against losing the disk: copy them elsewhere too.
PostgreSQL / MySQL are skipped: use their own tools (pg_dump, mysqldump).

Run one now: `docker compose exec backend python -m services.backup`
"""

import asyncio
import gzip
import logging
import os
import shutil
import sqlite3
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


def _private(path: Path) -> None:
    os.chmod(path, 0o600)


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
    asyncio.run(run_backup())
