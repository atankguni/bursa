"""
tickers.py
----------
Seed universe of IDX (Bursa Efek Indonesia) tickers.

These are the default tracked constituents combining LQ45 / IDX30 blue chips.
yfinance uses the ".JK" suffix for Indonesia. Edit this list to personalise.
"""

# ticker -> (display name, index membership)
TRACKED_STOCKS: list[dict[str, str]] = [
    {"ticker": "BBCA.JK", "name": "Bank Central Asia", "index_name": "IDX30"},
    {"ticker": "BBRI.JK", "name": "Bank Rakyat Indonesia", "index_name": "IDX30"},
    {"ticker": "BMRI.JK", "name": "Bank Mandiri", "index_name": "IDX30"},
    {"ticker": "BBNI.JK", "name": "Bank Negara Indonesia", "index_name": "IDX30"},
    {"ticker": "TLKM.JK", "name": "Telkom Indonesia", "index_name": "IDX30"},
    {"ticker": "ASII.JK", "name": "Astra International", "index_name": "IDX30"},
    {"ticker": "UNVR.JK", "name": "Unilever Indonesia", "index_name": "IDX30"},
    {"ticker": "ICBP.JK", "name": "Indofood CBP Sukses Makmur", "index_name": "IDX30"},
    {"ticker": "INDF.JK", "name": "Indofood Sukses Makmur", "index_name": "IDX30"},
    {"ticker": "KLBF.JK", "name": "Kalbe Farma", "index_name": "IDX30"},
    {"ticker": "ANTM.JK", "name": "Aneka Tambang", "index_name": "LQ45"},
    {"ticker": "ADRO.JK", "name": "Adaro Energy", "index_name": "LQ45"},
    {"ticker": "PTBA.JK", "name": "Bukit Asam", "index_name": "LQ45"},
    {"ticker": "ITMG.JK", "name": "Indo Tambangraya Megah", "index_name": "LQ45"},
    {"ticker": "INCO.JK", "name": "Vale Indonesia", "index_name": "LQ45"},
    {"ticker": "MDKA.JK", "name": "Merdeka Copper Gold", "index_name": "LQ45"},
    {"ticker": "BRPT.JK", "name": "Barito Pacific", "index_name": "LQ45"},
    {"ticker": "TPIA.JK", "name": "Chandra Asri Pacific", "index_name": "LQ45"},
    {"ticker": "CPIN.JK", "name": "Charoen Pokphand Indonesia", "index_name": "LQ45"},
    {"ticker": "JPFA.JK", "name": "Japfa Comfeed Indonesia", "index_name": "LQ45"},
    {"ticker": "SMGR.JK", "name": "Semen Indonesia", "index_name": "LQ45"},
    {"ticker": "INTP.JK", "name": "Indocement Tunggal Prakarsa", "index_name": "LQ45"},
    {"ticker": "BRIS.JK", "name": "Bank Syariah Indonesia", "index_name": "LQ45"},
    {"ticker": "ARTO.JK", "name": "Bank Jago", "index_name": "LQ45"},
    {"ticker": "GOTO.JK", "name": "GoTo Gojek Tokopedia", "index_name": "IDX30"},
    {"ticker": "EXCL.JK", "name": "XL Axiata", "index_name": "LQ45"},
    {"ticker": "TOWR.JK", "name": "Sarana Menara Nusantara", "index_name": "LQ45"},
    {"ticker": "MTEL.JK", "name": "Dayamitra Telekomunikasi", "index_name": "LQ45"},
    {"ticker": "PGAS.JK", "name": "Perusahaan Gas Negara", "index_name": "LQ45"},
    {"ticker": "MEDC.JK", "name": "Medco Energi Internasional", "index_name": "LQ45"},
]

# Convenience: just the yfinance symbols.
TICKERS: list[str] = [s["ticker"] for s in TRACKED_STOCKS]
