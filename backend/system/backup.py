"""
system/backup.py
----------------
Nightly backups of a SQLite database: a consistent online copy (SQLite's backup
API, safe while the app writes), checked with `PRAGMA integrity_check`,
zstd-compressed (`.db.zst`; older `.db.gz` backups still restore), plus the
2FA server secret file (without it, a restored
database can't read 2FA secrets). The newest BACKUP_KEEP backups are kept;
files are readable by the owner only.

With BACKUP_RECIPIENT (an age public key) both files are encrypted with `age`
(`.age` suffix): the compressed copy streams straight into it, so nothing
readable is kept. This machine can then write backups but not read them; the
private key, kept elsewhere, is needed to restore. Plain `age` decrypts them too:
`age -d -i key.txt bursa-<stamp>.db.zst.age | zstd -d -o bursa.db`.

They sit next to the database (BACKUP_DIR), which guards against mistakes and
corruption but not against losing the disk: copy them elsewhere too.
PostgreSQL is skipped: use its own tools (pg_dump).

Run one now: `docker compose exec backend python -m system.backup`
Restore one: `python -m system.backup restore <backup.db.zst[.age]> <new.db>
[--identity <private key file>]`
(steps in docs/configuration.md).
"""

import asyncio
import gzip
import io
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from compression import zstd
from datetime import datetime
from pathlib import Path
from typing import IO
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

from config import settings

log = logging.getLogger("bursa.backup")

PREFIX = "bursa-"
DB_SUFFIX = ".db.zst"
LEGACY_DB_SUFFIX = ".db.gz"  # backups made before 2026-10-23: restore and prune only
DB_SUFFIXES = (DB_SUFFIX, LEGACY_DB_SUFFIX)
# zstd level 19: a third smaller than gzip on Bursa's database, ~10 s and ~90 MB
# of memory for that moment, once a night (level 9: +15% size, 1 s, ~12 MB).
ZSTD_LEVEL = 19
KEY_SUFFIX = ".secret.key"
AGE = ".age"
CHUNK = 1024 * 1024


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


def _age_encrypt_to(target: Path, recipient: str) -> subprocess.Popen[bytes]:
    """An `age` process encrypting its stdin to `target` (create it 0600 first)."""
    target.touch(mode=0o600)
    with open(target, "wb") as out:
        return subprocess.Popen(["age", "-r", recipient], stdin=subprocess.PIPE, stdout=out)


def _finish(proc: subprocess.Popen[bytes], what: str) -> None:
    if proc.stdin:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"age failed while encrypting {what}")


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


def backup_sqlite(
    db: Path, dest: Path, keep: int, stamp: str, recipient: str | None = None
) -> Path:
    """Write `bursa-<stamp>.db.zst` (+ the secret key file) into `dest`, encrypted
    to `recipient` (`.age`) when given; prune old ones."""
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    suffix = AGE if recipient else ""
    tmp = dest / f".{PREFIX}{stamp}.db.tmp"
    target = dest / f"{PREFIX}{stamp}{DB_SUFFIX}{suffix}"
    try:
        src = sqlite3.connect(db)
        try:
            out = sqlite3.connect(tmp)
            try:
                src.backup(out)
                # The copy inherits WAL mode; a plain journal keeps it one file.
                out.execute("PRAGMA journal_mode=DELETE")
            finally:
                out.close()
        finally:
            src.close()
        check_integrity(tmp)  # a damaged copy is never kept as a backup
        partial = target.with_name(target.name + ".part")
        try:
            if recipient:
                proc = _age_encrypt_to(partial, recipient)
                assert proc.stdin is not None
                with open(tmp, "rb") as raw, zstd.ZstdFile(
                    proc.stdin, mode="wb", level=ZSTD_LEVEL
                ) as packed:
                    shutil.copyfileobj(raw, packed, length=CHUNK)
                _finish(proc, "the database")
            else:
                with open(tmp, "rb") as raw, zstd.ZstdFile(
                    partial, mode="wb", level=ZSTD_LEVEL
                ) as packed:
                    shutil.copyfileobj(raw, packed, length=CHUNK)
            _private(partial)
            partial.replace(target)  # never leave a half-written backup under the real name
        finally:
            partial.unlink(missing_ok=True)
    finally:
        for leftover in (tmp, tmp.with_name(tmp.name + "-wal"), tmp.with_name(tmp.name + "-shm")):
            leftover.unlink(missing_ok=True)

    key_file = Path(settings.secret_key_file)
    if not settings.secret_key and key_file.is_file():
        key_copy = dest / f"{PREFIX}{stamp}{KEY_SUFFIX}{suffix}"
        if recipient:
            proc = _age_encrypt_to(key_copy, recipient)
            assert proc.stdin is not None
            proc.stdin.write(key_file.read_bytes())
            _finish(proc, "the secret key")
        else:
            shutil.copyfile(key_file, key_copy)
        _private(key_copy)

    prune(dest, keep)
    return target


def _stamp(name: str) -> str | None:
    for suffix in DB_SUFFIXES:
        for enc in (AGE, ""):
            if name.startswith(PREFIX) and name.endswith(suffix + enc):
                return name[len(PREFIX) : -len(suffix + enc)]
    return None


def prune(dest: Path, keep: int) -> list[str]:
    """Delete all but the newest `keep` backups (and their key copies), plain or
    encrypted alike."""
    stamps = sorted({s for p in dest.iterdir() if (s := _stamp(p.name))}, reverse=True)
    removed = stamps[max(1, keep) :]
    for stamp in removed:
        for suffix in (*DB_SUFFIXES, KEY_SUFFIX):
            for enc in ("", AGE):
                (dest / f"{PREFIX}{stamp}{suffix}{enc}").unlink(missing_ok=True)
    return removed


def _unpacker(packed: IO[bytes], name: str) -> io.BufferedIOBase:
    """Decompress by the file's name: zstd, or gzip for older backups."""
    if name.removesuffix(AGE).endswith(LEGACY_DB_SUFFIX):
        return gzip.GzipFile(fileobj=packed, mode="rb")
    return zstd.ZstdFile(packed, mode="rb")


def restore_sqlite(backup: Path, target: Path, identity: Path | None = None) -> None:
    """Unpack `backup` into `target` (which must not exist) and check it. An
    encrypted backup (`.age`) needs the private key file (`identity`)."""
    if target.exists():
        raise FileExistsError(f"{target} exists; move it aside first")
    encrypted = backup.name.endswith(AGE)
    if encrypted and identity is None:
        raise ValueError(f"{backup.name} is encrypted: pass --identity <private key file>")
    partial = target.with_name(target.name + ".part")
    try:
        if encrypted:
            assert identity is not None
            proc = subprocess.Popen(
                ["age", "-d", "-i", str(identity), str(backup)], stdout=subprocess.PIPE
            )
            assert proc.stdout is not None
            try:
                with _unpacker(proc.stdout, backup.name) as packed, open(partial, "wb") as raw:
                    shutil.copyfileobj(packed, raw, length=CHUNK)
            except (EOFError, OSError, zstd.ZstdError):
                if proc.wait() != 0:  # nothing came out of age: say why
                    raise RuntimeError("age could not decrypt it (wrong private key?)") from None
                raise
            if proc.wait() != 0:
                raise RuntimeError("age could not decrypt it (wrong private key?)")
        else:
            with open(backup, "rb") as file, _unpacker(file, backup.name) as packed, open(
                partial, "wb"
            ) as raw:
                shutil.copyfileobj(packed, raw, length=CHUNK)
        check_integrity(partial)
    except BaseException:
        partial.unlink(missing_ok=True)
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
    recipient = settings.backup_recipient
    target = await asyncio.to_thread(
        backup_sqlite, db, Path(settings.backup_dir), settings.backup_keep, stamp, recipient
    )
    if not recipient:
        log.warning(
            "Backup is NOT encrypted: anyone with a copy can read it. Set BACKUP_RECIPIENT "
            "(docs/configuration.md#backups)."
        )
    log.info(
        "Backup written: %s (%.1f MB, keeping the newest %d)",
        target, target.stat().st_size / 1e6, settings.backup_keep,
    )
    return target


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = sys.argv[1:]
    identity: Path | None = None
    if "--identity" in args:
        i = args.index("--identity")
        if i + 1 >= len(args):
            raise SystemExit("--identity needs the private key file")
        identity = Path(args[i + 1])
        del args[i : i + 2]
    if args[:1] == ["restore"] and len(args) == 3:
        restore_sqlite(Path(args[1]), Path(args[2]), identity)
        log.info("Restored %s to %s (integrity check passed)", args[1], args[2])
    elif not args:
        asyncio.run(run_backup())
    else:
        raise SystemExit(
            "usage: python -m system.backup "
            "[restore <backup.db.zst[.age]> <new.db> [--identity <private key file>]]"
        )
