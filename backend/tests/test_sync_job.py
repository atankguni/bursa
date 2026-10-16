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
