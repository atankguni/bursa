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
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger("bursa.idx_site")

LISTING_URL = (
    "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
    "?start=0&length=3000&language=en-us"
)

# IDX boards: Main, Development, Acceleration, Watchlist (Papan Pemantauan
# Khusus = special monitoring), Ekonomi Baru (new economy).
SPECIAL_MONITORING = "Watchlist"


class ListingRow(TypedDict):
    ticker: str  # IDX code, e.g. BBCA
    name: str
    board: str | None
    listed_on: date | None
    shares: float | None


def _date(value: object) -> date | None:
    try:
        return datetime.fromisoformat(str(value)).date() if value else None
    except ValueError:
        return None


class IdxSecurity(BaseModel):
    """One row of the endpoint's JSON (only the fields used; others are ignored)."""

    model_config = ConfigDict(extra="ignore")

    code: str | None = Field(default=None, alias="Code")
    name: str | None = Field(default=None, alias="Name")
    listing_board: str | None = Field(default=None, alias="ListingBoard")
    listing_date: str | None = Field(default=None, alias="ListingDate")
    shares: float | None = Field(default=None, alias="Shares")


class IdxListing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[IdxSecurity] = []


def fetch_securities(timeout: float = 40.0) -> list[IdxSecurity]:
    """Blocking fetch of the endpoint's rows, validated (raises on an unexpected shape)."""
    resp = requests.get(LISTING_URL, impersonate="chrome", timeout=timeout)
    resp.raise_for_status()
    return IdxListing.model_validate_json(resp.content).data


def fetch_listing(timeout: float = 40.0) -> list[ListingRow]:
    """Blocking fetch of the full IDX listing."""
    rows: list[ListingRow] = []
    for x in fetch_securities(timeout):
        code = (x.code or "").strip().upper()
        if not code:
            continue
        rows.append({
            "ticker": code,
            "name": (x.name or "").strip() or code,
            "board": (x.listing_board or "").strip() or None,
            "listed_on": _date(x.listing_date),
            "shares": x.shares or None,
        })
    return rows
