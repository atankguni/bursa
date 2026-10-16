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
