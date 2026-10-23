"""
scripts/convert_db.py
---------------------
Copy a SQLite database from before the 2026-10-23 schema squash into a new
database with the current schema. The old file is opened read-only.

    python scripts/convert_db.py data/bursa.db data/bursa.new.db

Stop the backend first (so the old file doesn't change during the copy), then
swap the files: keep the old one as a backup until the new one looks right.

What changes on the way:
* stock codes lose Yahoo's ".JK" suffix ("BBCA.JK" -> "BBCA");
* `stock_prices` splits into `daily_bars` (one row per trading day) and
  `intraday_bars`; `stock_quotes` is rebuilt from the daily bars;
* `index_quotes` becomes `indices`; `stock_indices.index_name` -> `index_code`;
* the per-stock job timestamps on `stocks` move to `sync_state`;
* key/value `user_preferences` become one typed `user_settings` row per user;
* tables keyed by an id they didn't need (watchlist, dividends, ...) lose it.
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from clock import as_utc  # noqa: E402
from database import Base  # noqa: E402
from db.migrate import migrate  # noqa: E402
from db.upsert import upsert  # noqa: E402
from market.indices import INDICES  # noqa: E402
from market.quotes import refresh_quotes  # noqa: E402
from models import Stock, UserSettings  # noqa: E402

# A stock code as stored now (every old code had the suffix; this is safe either way).
CODE = "CASE WHEN {c} LIKE '%.JK' THEN substr({c}, 1, length({c}) - 3) ELSE {c} END"

# Old `stocks` column -> `sync_state` job.
SYNC_JOBS = {
    "idx_synced_at": "listing",
    "history_backfilled_at": "history_backfill",
    "full_history_at": "full_history",
    "splits_checked_at": "splits",
    "fundamentals_checked_at": "fundamentals",
}

# Tables copied column by column (same name, the columns both versions have),
# parents before children. The rest are built by hand below.
COPIED = [
    "users", "stocks", "stock_profiles", "fundamentals", "dividends", "splits",
    "index_bars", "rating_snapshots", "watchlist", "transactions", "alerts",
    "alert_events", "rating_state", "sessions", "invites", "password_resets",
    "recovery_codes", "mfa_challenges", "trusted_devices", "assistant_chats",
    "assistant_chat_messages",
]

# Column expressions that aren't a plain copy.
EXPRESSIONS = {
    ("fundamentals", "source"): "coalesce(source, 'statements')",  # old rows: statements
    ("transactions", "quantity"): "CAST(quantity AS INTEGER)",  # whole shares
}


def columns(con: sqlite3.Connection, schema: str, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA {schema}.table_info({table})")]


def copy_table(con: sqlite3.Connection, table: str) -> None:
    old = set(columns(con, "old", table))
    cols = [c for c in columns(con, "main", table) if c in old]
    exprs = [
        CODE.format(c=c) if c == "ticker" else EXPRESSIONS.get((table, c), c) for c in cols
    ]
    con.execute(
        f"INSERT INTO main.{table} ({', '.join(cols)}) "
        f"SELECT {', '.join(exprs)} FROM old.{table}"
    )


def copy_market(con: sqlite3.Connection) -> None:
    """Index catalog + memberships, price bars and sync state."""
    codes = sorted(
        {i.code for i in INDICES}
        | {r[0] for r in con.execute("SELECT code FROM old.index_bars")}
        | {r[0] for r in con.execute("SELECT index_name FROM old.stock_indices")}
    )
    con.executemany("INSERT INTO main.indices (code) VALUES (?)", [(c,) for c in codes])
    con.execute(
        "UPDATE main.indices SET (last, previous_close, updated_at, full_history_at) = "
        "(SELECT q.last, q.previous_close, q.updated_at, q.full_history_at "
        " FROM old.index_quotes q WHERE q.code = indices.code) "
        "WHERE code IN (SELECT code FROM old.index_quotes)"
    )
    con.execute(
        "INSERT INTO main.stock_indices (index_code, ticker) "
        f"SELECT index_name, {CODE.format(c='ticker')} FROM old.stock_indices"
    )
    bar = "open, high, low, close, volume"
    con.execute(
        f"INSERT INTO main.daily_bars (ticker, day, {bar}) "
        f"SELECT {CODE.format(c='ticker')}, substr(timestamp, 1, 10), {bar} "
        "FROM old.stock_prices WHERE interval = '1d'"
    )
    con.execute(
        f"INSERT INTO main.intraday_bars (ticker, timestamp, {bar}) "
        f"SELECT {CODE.format(c='ticker')}, timestamp, {bar} "
        "FROM old.stock_prices WHERE interval = '1m'"
    )
    old_cols = set(columns(con, "old", "stocks"))
    for column, job in SYNC_JOBS.items():
        if column in old_cols:
            con.execute(
                "INSERT INTO main.sync_state (ticker, job, done_at) "
                f"SELECT {CODE.format(c='ticker')}, ?, {column} FROM old.stocks "
                f"WHERE {column} IS NOT NULL",
                (job,),
            )


def old_settings(con: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    """Old key/value preferences -> {user_id: {user_settings column: value}}."""
    out: dict[int, dict[str, Any]] = {}
    for user_id, key, value in con.execute(
        "SELECT user_id, key, value FROM old.user_preferences WHERE user_id IS NOT NULL"
    ):
        row = out.setdefault(user_id, {})
        match key:
            case "investing_style":
                row["investing_style"] = value
            case "assistant_personal_data" | "assistant_save_chats" | "daily_digest":
                row[key] = value == "true"
            case "display_settings":
                row["display"] = json.loads(value)
            case "trading_costs":
                row["trading_costs"] = json.loads(value)
            case "alerts_seen_at":
                row["alerts_seen_at"] = as_utc(datetime.fromisoformat(value))
            case _:
                print(f"  skipped unknown preference {key!r} of user {user_id}")
    return out


async def finish(url: str, settings_rows: dict[int, dict[str, Any]]) -> None:
    """User settings and latest quotes, written by the app's own code."""
    engine = create_async_engine(url)
    async with async_sessionmaker(engine)() as session:
        for user_id, values in settings_rows.items():
            await upsert(session, UserSettings, {"user_id": user_id, **values}, keys=["user_id"])
        tickers = list((await session.execute(select(Stock.ticker))).scalars())
        await refresh_quotes(session, tickers)
        await session.commit()
    await engine.dispose()


def report(con: sqlite3.Connection) -> None:
    def count(sql: str) -> int:
        return con.execute(sql).fetchone()[0]

    checks = {
        "stock_prices 1d -> daily_bars": (
            "SELECT count(*) FROM old.stock_prices WHERE interval = '1d'",
            "SELECT count(*) FROM main.daily_bars",
        ),
        "stock_prices 1m -> intraday_bars": (
            "SELECT count(*) FROM old.stock_prices WHERE interval = '1m'",
            "SELECT count(*) FROM main.intraday_bars",
        ),
        "index_quotes -> indices (with a quote)": (
            "SELECT count(*) FROM old.index_quotes",
            "SELECT count(*) FROM main.indices WHERE updated_at IS NOT NULL",
        ),
        "stock_indices": (
            "SELECT count(*) FROM old.stock_indices", "SELECT count(*) FROM main.stock_indices",
        ),
        **{
            t: (f"SELECT count(*) FROM old.{t}", f"SELECT count(*) FROM main.{t}")
            for t in COPIED
        },
    }
    bad = False
    for name, (before, after) in checks.items():
        a, b = count(before), count(after)
        bad |= a != b
        print(f"  {name:42} {a:>10} -> {b:<10}{'' if a == b else '  MISMATCH'}")
    print(f"  {'sync_state':42} {count('SELECT count(*) FROM main.sync_state'):>24}")
    print(f"  {'stock_quotes':42} {count('SELECT count(*) FROM main.stock_quotes'):>24}")
    print(f"  {'user_settings':42} {count('SELECT count(*) FROM main.user_settings'):>24}")
    problems = con.execute("PRAGMA main.foreign_key_check").fetchall()
    integrity = con.execute("PRAGMA main.integrity_check").fetchone()[0]
    print(f"  foreign key problems: {len(problems)}; integrity: {integrity}")
    if bad or problems or integrity != "ok":
        raise SystemExit("Conversion check failed; the new database is incomplete.")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[1])
    parser.add_argument("old", type=Path, help="database from before the squash")
    parser.add_argument("new", type=Path, help="file to create (must not exist)")
    args = parser.parse_args()
    old: Path = args.old.resolve()
    new: Path = args.new.resolve()
    if not old.is_file():
        raise SystemExit(f"{old} not found")
    if new.exists():
        raise SystemExit(f"{new} already exists")

    url = f"sqlite+aiosqlite:///{new}"
    engine = create_async_engine(url)
    asyncio.run(migrate(engine))
    asyncio.run(engine.dispose())
    print(f"Created {new} ({len(Base.metadata.tables)} tables)")

    # URI filenames, so the old file can be attached read-only.
    con = sqlite3.connect(f"file:{new}", uri=True, isolation_level=None)
    try:
        con.execute("ATTACH DATABASE ? AS old", (f"file:{old}?mode=ro",))
        if "stock_prices" not in {r[0] for r in con.execute(
            "SELECT name FROM old.sqlite_master WHERE type = 'table'"
        )}:
            raise SystemExit(f"{old} isn't a database from before the squash")
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("BEGIN")
        copy_table(con, "users")
        copy_table(con, "stocks")
        copy_market(con)
        for table in COPIED[2:]:
            copy_table(con, table)
        con.execute("COMMIT")
        settings_rows = old_settings(con)
    finally:
        con.close()

    asyncio.run(finish(url, settings_rows))

    con = sqlite3.connect(f"file:{new}", uri=True)
    try:
        con.execute("ATTACH DATABASE ? AS old", (f"file:{old}?mode=ro",))
        report(con)
        con.execute("VACUUM main")
    finally:
        con.close()
    print("Done.")


if __name__ == "__main__":
    main()
