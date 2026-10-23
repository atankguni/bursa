"""The database schema: stock codes, latest quotes, constraints, the migration guard."""

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from database import AsyncSessionLocal
from db.migrate import OutdatedDatabase, migrate
from market.models import StockQuote
from market.quotes import refresh_quotes
from portfolio.models import Transaction
from schemas import stock_code
from tests.conftest import add_daily_bars


def test_stock_codes_are_stored_without_the_yahoo_suffix():
    assert stock_code(" BBCA.JK ") == "BBCA"
    assert stock_code("bbca") == "BBCA"


async def test_old_links_with_the_suffix_still_work(client):
    r = await client.get("/api/stocks/BBCA.JK")
    assert r.status_code == 200 and r.json()["ticker"] == "BBCA"
    added = await client.post("/api/watchlist/bbca.jk")
    assert added.status_code == 201
    assert [w["ticker"] for w in (await client.get("/api/watchlist")).json()] == ["BBCA"]


async def test_quotes_follow_the_newest_two_bars(db):
    bar = {"open": 1.0, "high": 1.0, "low": 1.0, "volume": 10}
    async with AsyncSessionLocal() as s:
        await add_daily_bars(s, [
            {"ticker": "BBCA", "day": date(2026, 10, d), "close": c, **bar}
            for d, c in ((20, 100.0), (21, 110.0))
        ])
        await s.commit()
        q = await s.get(StockQuote, "BBCA")
        assert q is not None
        assert (q.day, q.close, q.prev_close) == (date(2026, 10, 21), 110.0, 100.0)

        newest = {"ticker": "BBCA", "day": date(2026, 10, 22), "close": 99.0, **bar}
        await add_daily_bars(s, [newest])
        await s.commit()
        q = await s.get(StockQuote, "BBCA", populate_existing=True)
        assert q is not None and (q.close, q.prev_close) == (99.0, 110.0)
        assert await refresh_quotes(s, []) == 0
        rows = (await s.execute(select(StockQuote.ticker))).scalars().all()
        assert rows == ["BBCA"]


@pytest.mark.parametrize(("field", "value"), [("quantity", 0), ("price", -1.0), ("side", "hold")])
async def test_check_constraints_reject_bad_values(client, field, value):
    row = {"user_id": client.user_id, "ticker": "BBCA", "side": "buy", "quantity": 100,
           "price": 1000.0, "fees": 0.0, "trade_date": date(2026, 10, 1)}
    async with AsyncSessionLocal() as s:
        s.add(Transaction(**(row | {field: value})))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_a_database_from_before_the_squash_is_refused(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/old.db")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        await conn.execute(text("INSERT INTO alembic_version VALUES ('20261022_213600')"))
        await conn.execute(text("CREATE TABLE stocks (id INTEGER)"))
    with pytest.raises(OutdatedDatabase, match="convert_db"):
        await migrate(engine)
    await engine.dispose()
