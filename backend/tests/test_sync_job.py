"""Tests for the screener sync job + fundamentals sync flag."""

import services.fundamentals as fundamentals
import services.sync_job as sync_job


def test_status_shape():
    st = sync_job.status()
    assert set(st) >= {"running", "total", "done", "remaining", "last_error"}
    assert st["remaining"] >= 0


def test_start_rejects_while_running(monkeypatch):
    monkeypatch.setitem(sync_job._state, "running", True)
    assert sync_job.start(["BBCA.JK"]) is False


async def test_sync_many_passes_with_dividends_flag(monkeypatch):
    calls: list[tuple[str, bool]] = []

    async def fake_sync(ticker: str, with_dividends: bool = True) -> int:
        calls.append((ticker, with_dividends))
        return 1

    monkeypatch.setattr(fundamentals, "sync_ticker", fake_sync)
    total = await fundamentals.sync_many(
        ["A.JK", "B.JK"], throttle=0, with_dividends=False
    )

    assert total == 2
    assert calls == [("A.JK", False), ("B.JK", False)]


async def test_missing_tickers_rotates_tried_ones_to_the_back(client):
    # Regression: tickers the provider has no statements for used to stay at
    # the front (alphabetical), so every capped run retried the same ones.
    before = await sync_job.missing_tickers()
    first = before[0]

    await sync_job._mark_checked(first)
    after = await sync_job.missing_tickers()

    assert after[0] != first
    assert after[-1] == first
    assert sorted(after) == sorted(before)
    assert await sync_job.missing_count() == len(before)


async def test_status_endpoint_reports_missing(client):
    r = await client.get("/api/screener/sync/status")
    assert r.status_code == 200
    assert r.json()["missing"] > 0


async def test_statements_supersede_summary_rows(client, monkeypatch):
    from datetime import datetime

    from sqlalchemy import select

    from config import settings
    from database import AsyncSessionLocal
    from models import Fundamental

    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)

    def row(year, source):
        return {"ticker": "BBCA.JK", "fiscal_year": year, "financial_currency": "IDR",
                "total_shares": 1.0, "revenue": 1.0, "net_income": 1.0, "total_assets": 2.0,
                "total_liabilities": 1.0, "equity": 1.0, "source": source,
                "updated_at": datetime.utcnow()}

    class _P:
        name = "fake"

        def __init__(self, rows):
            self.rows = rows

        def fetch_fundamentals(self, ticker):
            return self.rows, None

    # First sync: only a summary row (dated to the latest quarter, 2026).
    monkeypatch.setattr(fundamentals, "fundamentals_provider", lambda: _P([row(2026, "summary")]))
    await fundamentals.sync_ticker("BBCA.JK", with_dividends=False)
    # Later the statements appear (FY2025): the 2026 summary row must not linger as "latest".
    monkeypatch.setattr(fundamentals, "fundamentals_provider",
                        lambda: _P([row(2024, "statements"), row(2025, "statements")]))
    await fundamentals.sync_ticker("BBCA.JK", with_dividends=False)

    async with AsyncSessionLocal() as s:
        got = (await s.execute(
            select(Fundamental.fiscal_year, Fundamental.source)
            .where(Fundamental.ticker == "BBCA.JK").order_by(Fundamental.fiscal_year)
        )).all()
    assert got == [(2024, "statements"), (2025, "statements")]


def test_missed_jobs_run_on_wake_not_dropped():
    import scheduler as sched

    # APScheduler's default grace is 1s: a job missed while the host slept was lost.
    assert sched.scheduler._job_defaults["misfire_grace_time"] >= 3600
    assert sched.scheduler._job_defaults["coalesce"] is True


async def test_catch_up_intraday_ignores_market_hours(monkeypatch):
    import scheduler as sched

    calls = []

    async def fake_sync(tickers, period, interval):
        calls.append((len(tickers), period, interval))
        return 0

    async def fake_active():
        return ["BBCA.JK", "TLKM.JK"]

    monkeypatch.setattr(sched, "sync_batch", fake_sync)
    monkeypatch.setattr(sched, "active_tickers", fake_active)
    monkeypatch.setattr(sched, "is_open", lambda: False)  # after the close / weekend
    await sched.catch_up_intraday("5d")
    assert calls == [(2, "5d", "1m")]


async def _fake_sync_factory(monkeypatch, gives_data):
    """sync_ticker stand-in: writes a profile when `gives_data(ticker)` is true."""
    from database import AsyncSessionLocal
    from models import StockProfile

    calls: list[str] = []

    async def fake(ticker, with_dividends=True):
        calls.append(ticker)
        if gives_data(ticker):
            async with AsyncSessionLocal() as s:
                s.add(StockProfile(ticker=ticker, sector="Tech"))
                await s.commit()
        return 0

    monkeypatch.setattr(sync_job, "sync_ticker", fake)
    return calls


async def _wait_done():
    import asyncio

    for _ in range(200):
        if not sync_job.status()["running"]:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("sync job did not finish")


async def test_sync_all_works_through_every_never_tried_stock(client, monkeypatch):
    from config import settings

    for k, v in {"screener_sync_limit": 300, "screener_sync_batch_pause": 0,
                 "screener_sync_throttle": 0}.items():
        monkeypatch.setattr(settings, k, v)
    calls = await _fake_sync_factory(monkeypatch, lambda t: True)
    total = len(await sync_job.never_tried())

    r = (await client.post("/api/screener/sync", params={"all": True})).json()
    assert r["running"] and r["total"] == total
    await _wait_done()
    assert len(calls) == total and len(set(calls)) == total  # each once, in batches of 300
    assert await sync_job.never_tried() == []


async def test_sync_all_stops_when_batches_come_back_empty(client, monkeypatch):
    from config import settings

    for k, v in {"screener_sync_limit": 5, "screener_sync_batch_pause": 0,
                 "screener_sync_blocked_wait": 0, "screener_sync_throttle": 0,
                 "screener_sync_max_empty_batches": 2}.items():
        monkeypatch.setattr(settings, k, v)
    calls = await _fake_sync_factory(monkeypatch, lambda t: False)  # "blocked"
    await sync_job.start_all()
    await _wait_done()
    assert len(calls) == 10  # two empty batches of 5, then it gives up
    assert "rate-limiting" in sync_job.status()["last_error"]


async def test_sync_all_can_be_cancelled(client, monkeypatch):
    import asyncio

    from config import settings

    for k, v in {"screener_sync_limit": 5, "screener_sync_batch_pause": 30,
                 "screener_sync_throttle": 0}.items():
        monkeypatch.setattr(settings, k, v)
    calls = await _fake_sync_factory(monkeypatch, lambda t: True)
    await sync_job.start_all()
    for _ in range(100):  # wait until the first batch is done and it's pausing
        if len(calls) >= 5:
            break
        await asyncio.sleep(0.02)
    r = (await client.post("/api/screener/sync/cancel")).json()
    assert r["note"] == "Stopping…"
    await _wait_done()  # stops during the 30s pause, not after it
    assert len(calls) == 5


async def test_history_backfill_marks_done_and_resumes(client, monkeypatch):
    from sqlalchemy import func, select

    import services.history as history
    from config import settings
    from database import AsyncSessionLocal
    from models import Stock

    monkeypatch.setattr(settings, "provider_chunk_size", 400)
    calls = []
    down = {"once": True}

    async def fake_sync(tickers, period, interval):
        calls.append((len(tickers), period, interval))
        if len(calls) == 2 and down.pop("once", False):
            return 0  # the second chunk of the first run: provider down
        return len(tickers)

    monkeypatch.setattr(history, "sync_batch", fake_sync)
    async with AsyncSessionLocal() as s:
        total = await s.scalar(select(func.count()).select_from(Stock))
    assert total and total > 400

    first = await history.backfill_history()
    assert first == 400  # stopped at the empty chunk, nothing past it marked
    assert calls[0] == (400, f"{settings.daily_history_years}y", "1d")

    calls.clear()
    second = await history.backfill_history()  # resumes with the rest only
    assert second == total - 400 and sum(n for n, _, _ in calls) == total - 400
    assert await history.backfill_history() == 0  # all done: no provider call
