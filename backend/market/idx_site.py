"""
market/idx_site.py
------------------
The IDX website's (undocumented) stock-listing endpoint: every listed company
with its listing board, listing date and official share count.

It sits behind Cloudflare, so curl_cffi browser impersonation is used (already
a dependency via yfinance). Being undocumented, it may change or be blocked;
callers must treat failures as "no update" rather than errors.
"""

import logging
from datetime import date, datetime
from typing import TypedDict

from curl_cffi import requests

log = logging.getLogger("bursa.idx_site")

LISTING_URL = (
    "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
    "?start=0&length=3000&language=en-us"
)

# IDX boards: Main, Development, Acceleration, Watchlist (Papan Pemantauan
# Khusus = special monitoring), Ekonomi Baru (new economy).
SPECIAL_MONITORING = "Watchlist"


class ListingRow(TypedDict):
    ticker: str  # Yahoo-style, e.g. BBCA.JK
    name: str
    board: str | None
    listed_on: date | None
    shares: float | None


def _date(value: object) -> date | None:
    try:
        return datetime.fromisoformat(str(value)).date() if value else None
    except ValueError:
        return None


def fetch_listing(timeout: float = 40.0) -> list[ListingRow]:
    """Blocking fetch of the full IDX listing."""
    resp = requests.get(LISTING_URL, impersonate="chrome", timeout=timeout)
    resp.raise_for_status()
    rows: list[ListingRow] = []
    for x in resp.json().get("data", []):
        code = (x.get("Code") or "").strip().upper()
        if not code:
            continue
        shares = x.get("Shares")
        rows.append({
            "ticker": f"{code}.JK",
            "name": (x.get("Name") or "").strip() or code,
            "board": (x.get("ListingBoard") or "").strip() or None,
            "listed_on": _date(x.get("ListingDate")),
            "shares": float(shares) if shares else None,
        })
    return rows
