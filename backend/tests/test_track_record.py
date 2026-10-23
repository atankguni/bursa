"""Rating labels and the track record (backtest summary + live snapshots)."""

from datetime import date, timedelta

from database import AsyncSessionLocal
from models import RatingSnapshot
from schemas import RatingRecordOut
from services import track_record
from services.recommendation import rating_code, rating_label
from tests.conftest import add_daily_bars


def test_labels_and_codes_round_trip():
    assert rating_label("Strong Buy") == "Very positive"
    assert rating_label("Avoid") == "Very negative"
    assert rating_code("positive") == "Buy"
    assert rating_code("Strong Buy") == "Strong Buy"
    assert rating_code(" neutral ") == "Hold"
    assert rating_code("moon") is None
    assert rating_code(None) is None


def test_beat_rates_compare_with_the_same_dates_median():
    rows = [
        # Day 1 median = 0.02: the Buy beats it, the Avoid doesn't.
        ("d1", "Buy", 0.05), ("d1", "Hold", 0.02), ("d1", "Avoid", -0.01),
        # Day 2 median = -0.10: everyone fell, the Buy fell least.
        ("d2", "Buy", -0.05), ("d2", "Hold", -0.10), ("d2", "Avoid", -0.20),
    ]
    rates = {r.rating: r for r in track_record.beat_rates(rows)}
    assert rates["Buy"] == RatingRecordOut(rating="Buy", n=2, beat=1.0)
    assert rates["Avoid"].beat == 0.0
    assert "Strong Buy" not in rates  # no rows, no claim


async def _bars(ticker: str, start: date, closes: list[float]) -> None:
    async with AsyncSessionLocal() as s:
        await add_daily_bars(s, [
            {"ticker": ticker, "day": start + timedelta(days=i),
             "open": c, "high": c, "low": c, "close": c, "volume": 0}
            for i, c in enumerate(closes)
        ])
        await s.commit()


async def test_live_record_waits_for_the_horizon(client, monkeypatch):
    monkeypatch.setitem(track_record.HORIZON, "trader", ("4w", 3))
    track_record._live_cache.clear()
    start = date(2026, 1, 5)
    await _bars("BBCA", start, [100, 101, 102, 110, 111])  # +10% after 3 bars
    await _bars("BBRI", start, [100, 100, 100, 95, 95])    # -5%
    async with AsyncSessionLocal() as s:
        s.add_all([
            RatingSnapshot(day=start, style="trader", ticker="BBCA", rating="Buy",
                           score=70, liquid=True),
            RatingSnapshot(day=start, style="trader", ticker="BBRI", rating="Avoid",
                           score=20, liquid=True),
            # Too recent: its horizon hasn't passed yet.
            RatingSnapshot(day=start + timedelta(days=3), style="trader", ticker="BBCA",
                           rating="Hold", score=50, liquid=True),
        ])
        await s.commit()

    body = (await client.get("/api/track-record")).json()  # admin default style: investor
    assert body["style"] == "investor" and body["live"]["days"] == 0

    await client.put("/api/preferences", json={"investing_style": "trader"})
    body = (await client.get("/api/track-record")).json()
    live = body["live"]
    assert body["horizon"] == "4w"
    assert live["since"] == "2026-01-05" and live["days"] == 2 and live["matured_days"] == 1
    rates = {r["rating"]: r["beat"] for r in live["ratings"]}
    assert rates == {"Buy": 1.0, "Avoid": 0.0}
