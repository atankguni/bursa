"""
market/indices.py
-----------------
IDX stock indices ("indeks saham") shown on the Market page.

Yahoo serves today's value + previous close for all of these. Full daily
history is only available for the `^` symbols marked `history=True`; the rest
build their own history from each day's close stored by the app.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexDef:
    code: str  # IDX index code
    name: str
    group: str
    symbol: str  # provider (Yahoo) symbol
    history: bool = False  # provider has full daily history


GROUPS = ["Benchmark", "Sharia", "Dividend & SOE", "Thematic & ESG", "Sector", "Board"]

INDICES: list[IndexDef] = [
    # Benchmark / liquidity
    IndexDef("COMPOSITE", "IHSG (Composite)", "Benchmark", "^JKSE", history=True),
    IndexDef("LQ45", "LQ45", "Benchmark", "^JKLQ45", history=True),
    IndexDef("IDX30", "IDX30", "Benchmark", "IDX30.JK"),
    IndexDef("IDX80", "IDX80", "Benchmark", "IDX80.JK"),
    IndexDef("KOMPAS100", "Kompas100", "Benchmark", "KOMPAS100.JK"),
    # Sharia
    IndexDef("JII", "Jakarta Islamic Index", "Sharia", "^JKII", history=True),
    IndexDef("JII70", "Jakarta Islamic Index 70", "Sharia", "JII70.JK"),
    IndexDef("ISSI", "Indonesia Sharia Stock Index", "Sharia", "ISSI.JK"),
    # Dividend & state-owned
    IndexDef("IDXHIDIV20", "IDX High Dividend 20", "Dividend & SOE", "IDXHIDIV20.JK"),
    IndexDef("IDXBUMN20", "IDX BUMN20", "Dividend & SOE", "IDXBUMN20.JK"),
    # Thematic, factor & ESG
    IndexDef("IDXQ30", "IDX Quality30", "Thematic & ESG", "IDXQ30.JK"),
    IndexDef("IDXV30", "IDX Value30", "Thematic & ESG", "IDXV30.JK"),
    IndexDef("IDXG30", "IDX Growth30", "Thematic & ESG", "IDXG30.JK"),
    IndexDef("IDXSMC-LIQ", "IDX SMC Liquid", "Thematic & ESG", "IDXSMC-LIQ.JK"),
    IndexDef("ECONOMIC30", "IDX Economic30", "Thematic & ESG", "ECONOMIC30.JK"),
    IndexDef("SRI-KEHATI", "SRI-KEHATI", "Thematic & ESG", "SRI-KEHATI.JK"),
    IndexDef("IDXESGL", "IDX ESG Leaders", "Thematic & ESG", "IDXESGL.JK"),
    IndexDef("BISNIS-27", "Bisnis-27", "Thematic & ESG", "BISNIS-27.JK"),
    IndexDef("INFOBANK15", "Infobank15", "Thematic & ESG", "INFOBANK15.JK"),
    IndexDef("MNC36", "MNC36", "Thematic & ESG", "MNC36.JK"),
    # IDX-IC sectors (all 11)
    IndexDef("IDXENERGY", "Energy", "Sector", "IDXENERGY.JK"),
    IndexDef("IDXBASIC", "Basic Materials", "Sector", "IDXBASIC.JK"),
    IndexDef("IDXINDUST", "Industrials", "Sector", "IDXINDUST.JK"),
    IndexDef("IDXNONCYC", "Consumer Non-Cyclicals", "Sector", "IDXNONCYC.JK"),
    IndexDef("IDXCYCLIC", "Consumer Cyclicals", "Sector", "IDXCYCLIC.JK"),
    IndexDef("IDXHEALTH", "Healthcare", "Sector", "IDXHEALTH.JK"),
    IndexDef("IDXFINANCE", "Financials", "Sector", "IDXFINANCE.JK"),
    IndexDef("IDXPROPERT", "Properties & Real Estate", "Sector", "IDXPROPERT.JK"),
    IndexDef("IDXTECHNO", "Technology", "Sector", "IDXTECHNO.JK"),
    IndexDef("IDXINFRA", "Infrastructures", "Sector", "IDXINFRA.JK"),
    IndexDef("IDXTRANS", "Transportation & Logistic", "Sector", "IDXTRANS.JK"),
    # Listing boards
    IndexDef("MBX", "Main Board", "Board", "^JKMBX"),
    IndexDef("DBX", "Development Board", "Board", "^JKDBX"),
]

BY_CODE: dict[str, IndexDef] = {i.code: i for i in INDICES}
BY_SYMBOL: dict[str, IndexDef] = {i.symbol: i for i in INDICES}
