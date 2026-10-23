"""Data-health report: sections, share-count mismatches, job outcome tracking."""


from sqlalchemy import select

from clock import utcnow
from database import AsyncSessionLocal
from market.models import Fundamental, Stock


async def test_report_sections_and_share_mismatch(client):
    async with AsyncSessionLocal() as s:
        bbni = (await s.execute(select(Stock).where(Stock.ticker == "BBNI"))).scalar_one()
        bbni.idx_shares = 37.3e9  # official IDX count
        s.add(Fundamental(  # Yahoo's broken sharesOutstanding (BBNI case)
            ticker="BBNI", fiscal_year=2025, financial_currency="IDR",
            total_shares=0.58e9, equity=1.7e14, source="statements",
            updated_at=utcnow(),
        ))
        await s.commit()

    r = (await client.get("/api/data-health")).json()
    sec = r["sections"]
    assert set(sec) == {"jobs", "providers", "prices", "fundamentals", "indices",
                        "listing", "suspicious"}
    assert all(v["status"] in ("ok", "warn", "error") for v in sec.values())
    assert sec["prices"]["stocks"] > 900
    assert sec["fundamentals"]["statements"] == 1
    mism = sec["suspicious"]["share_mismatches"]
    assert [m["ticker"] for m in mism] == ["BBNI"]
    assert sec["suspicious"]["status"] == "warn"


async def test_job_outcomes_and_the_worker_are_reported(client):
    from clock import utcnow
    from system import worker_state

    await worker_state.record_jobs([
        ("backfill_daily", "Daily bars", None), ("old_job", "Gone", None),
    ])
    await worker_state.record_jobs([("backfill_daily", "Daily bars", None)])
    await worker_state.record_run("backfill_daily", "Yahoo said no", None)
    jobs = (await client.get("/api/data-health")).json()["sections"]["jobs"]
    assert [(j["id"], j["ok"]) for j in jobs["items"]] == [("backfill_daily", False)]
    assert "Yahoo said no" in jobs["items"][0]["error"]
    assert jobs["worker_running"] is False and jobs["status"] == "error"

    await worker_state.heartbeat(utcnow())
    jobs = (await client.get("/api/data-health")).json()["sections"]["jobs"]
    assert jobs["worker_running"] is True


async def test_reconcile_shares_uses_idx_register(client):
    from market.fundamentals import reconcile_shares

    async with AsyncSessionLocal() as s:
        for t, idx, yahoo in [("AISA", 9.3118e9, 3.8057e9), ("BBCA", 1.2328e11, 1.228e11)]:
            stock = (await s.execute(select(Stock).where(Stock.ticker == t))).scalar_one()
            stock.idx_shares = idx
            for fy in (2024, 2025):
                s.add(Fundamental(ticker=t, fiscal_year=fy, financial_currency="IDR",
                                  source="statements", total_shares=yahoo,
                                  updated_at=utcnow()))
        await s.commit()

    assert await reconcile_shares() == 1  # only AISA is off by more than 20%
    async with AsyncSessionLocal() as s:
        got = dict((await s.execute(
            select(Fundamental.ticker, Fundamental.total_shares)
            .where(Fundamental.fiscal_year == 2025)
        )).all())
        old = (await s.execute(
            select(Fundamental.total_shares).where(Fundamental.ticker == "AISA",
                                                   Fundamental.fiscal_year == 2024)
        )).scalar_one()
    assert got["AISA"] == 9.3118e9   # latest row: IDX register
    assert got["BBCA"] == 1.228e11   # within 20%: provider value kept
    assert old == 3.8057e9              # history untouched


async def test_a_restarting_worker_keeps_job_history(client):
    from system import worker_state

    await worker_state.record_jobs([("backfill_daily", "Daily bars", None)])
    await worker_state.record_run("backfill_daily", None, None)
    await worker_state.record_jobs([])  # first heartbeat, scheduler not started yet
    jobs = (await client.get("/api/data-health")).json()["sections"]["jobs"]["items"]
    assert [(j["id"], j["ok"]) for j in jobs] == [("backfill_daily", True)]
