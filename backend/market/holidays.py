"""
market/holidays.py
------------------
IDX (Bursa Efek Indonesia) exchange holidays (libur bursa), as ISO date strings.

Weekdays only: weekend holidays don't change trading. Copied from IDX's yearly
"Kalender Libur Bursa" announcements, which follow the government's decree on
national holidays and collective leave (cuti bersama):
    https://www.idx.co.id/en/about-idx/trading-hours-and-holidays

IDX publishes the next year's calendar each September and sometimes revises it
mid-year (e.g. an extra cuti bersama): add the new year then, and apply any
revision. A missing day makes the status indicator say "open" while the
exchange is closed, and puts sale settlement dates a day early.
"""

IDX_HOLIDAYS: set[str] = {
    # 2026: Peng-00171/BEI.POP/09-2025 (22 days, 239 trading days).
    "2026-01-01",  # New Year
    "2026-01-16",  # Isra Mikraj
    "2026-02-16",  # Cuti bersama Imlek
    "2026-02-17",  # Imlek 2577
    "2026-03-18",  # Cuti bersama Nyepi
    "2026-03-19",  # Nyepi
    "2026-03-20",  # Cuti bersama Idul Fitri
    "2026-03-23",  # Cuti bersama Idul Fitri
    "2026-03-24",  # Cuti bersama Idul Fitri
    "2026-04-03",  # Good Friday
    "2026-05-01",  # Labour Day
    "2026-05-14",  # Ascension Day
    "2026-05-15",  # Cuti bersama Ascension
    "2026-05-27",  # Idul Adha
    "2026-05-28",  # Cuti bersama Idul Adha
    "2026-06-01",  # Pancasila Day
    "2026-06-16",  # Islamic New Year
    "2026-08-17",  # Independence Day
    "2026-08-25",  # Maulid Nabi
    "2026-12-24",  # Cuti bersama Christmas
    "2026-12-25",  # Christmas
    "2026-12-31",  # Year-end exchange holiday
    # 2027: Peng-00169/BEI.POP/09-2026 (20 days, 241 trading days).
    "2027-01-01",  # New Year
    "2027-01-05",  # Isra Mikraj
    "2027-02-05",  # Cuti bersama Imlek
    "2027-03-08",  # Nyepi
    "2027-03-09",  # Cuti bersama Idul Fitri
    "2027-03-10",  # Idul Fitri
    "2027-03-11",  # Idul Fitri
    "2027-03-12",  # Cuti bersama Idul Fitri
    "2027-03-15",  # Cuti bersama Idul Fitri
    "2027-03-25",  # Cuti bersama Good Friday
    "2027-03-26",  # Good Friday
    "2027-05-06",  # Ascension Day
    "2027-05-17",  # Idul Adha
    "2027-05-18",  # Cuti bersama Idul Adha
    "2027-05-19",  # Cuti bersama Waisak
    "2027-05-20",  # Waisak
    "2027-06-01",  # Pancasila Day
    "2027-08-17",  # Independence Day
    "2027-12-24",  # Cuti bersama Christmas
    "2027-12-31",  # Year-end exchange holiday
}
