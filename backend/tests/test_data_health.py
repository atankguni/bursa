"""Data-health report: sections, share-count mismatches, job outcome tracking."""


from sqlalchemy import select

from clock import utcnow
from database import AsyncSessionLocal
from models import Fundamental, Stock


async def test_report_sections_and_share_mismatch(client):
    async with AsyncSessionLocal() as s:
        bbni = (await s.execute(select(Stock).where(Stock.ticker == "BBNI.JK"))).scalar_one()
        bbni.idx_shares = 37.3e9  # official IDX count
        s.add(Fundamental(  # Yahoo's broken sharesOutstanding (BBNI case)
            ticker="BBNI.JK", fiscal_year=2025, financial_currency="IDR",
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
    assert [m["ticker"] for m in mism] == ["BBNI.JK"]
    assert sec["suspicious"]["status"] == "warn"


def test_job_outcomes_are_recorded():
    import scheduler as sched

    class _Event:
        job_id = "backfill_daily"
        exception = RuntimeError("Yahoo said no")

    sched._record_job(_Event())  # type: ignore[arg-type]
    assert sched.job_runs["backfill_daily"]["ok"] is False
    assert "Yahoo said no" in (sched.job_runs["backfill_daily"]["error"] or "")


async def test_reconcile_shares_uses_idx_register(client):
    from services.fundamentals import reconcile_shares

    async with AsyncSessionLocal() as s:
        for t, idx, yahoo in [("AISA.JK", 9.3118e9, 3.8057e9), ("BBCA.JK", 1.2328e11, 1.228e11)]:
            stock = (await s.execute(select(Stock).where(Stock.ticker == t))).scalar_one()
            stock.idx_shares = idx
            for fy in (2024, 2025):
                s.add(Fundamental(ticker=t, fiscal_year=fy, financial_currency="IDR",
                                  total_shares=yahoo, updated_at=utcnow()))
        await s.commit()

    assert await reconcile_shares() == 1  # only AISA is off by more than 20%
    async with AsyncSessionLocal() as s:
        got = dict((await s.execute(
            select(Fundamental.ticker, Fundamental.total_shares)
            .where(Fundamental.fiscal_year == 2025)
        )).all())
        old = (await s.execute(
            select(Fundamental.total_shares).where(Fundamental.ticker == "AISA.JK",
                                                   Fundamental.fiscal_year == 2024)
        )).scalar_one()
    assert got["AISA.JK"] == 9.3118e9   # latest row: IDX register
    assert got["BBCA.JK"] == 1.228e11   # within 20%: provider value kept
    assert old == 3.8057e9              # history untouched
