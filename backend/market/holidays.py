"""
market/holidays.py
------------------
IDX (Bursa Efek Indonesia) market holidays, as ISO date strings.

Only the STABLE fixed-date national holidays are listed here. The variable ones
(Idul Fitri, Nyepi, Waisak, Ascension, Isra Mikraj, etc.) change every year and
must be added from the official IDX trading calendar:
    https://www.idx.co.id/en/about-idx/trading-hours-and-holidays

Update this set annually; a missing holiday only makes the status indicator say
"open" when the exchange is actually closed.
"""

IDX_HOLIDAYS: set[str] = {
    # Fixed-date national holidays (stable across years).
    "2026-01-01",  # New Year's Day
    "2026-08-17",  # Independence Day
    "2026-12-25",  # Christmas Day
    # NOTE: add variable holidays for the year from the IDX calendar, e.g.
    # "2026-03-20",  # Idul Fitri (verify date)
}
