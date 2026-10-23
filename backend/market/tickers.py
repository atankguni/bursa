"""
tickers.py
----------
Seed universe of IDX (Bursa Efek Indonesia) tickers.

Because a stock can belong to several indices at once (e.g. BBRI is in LQ45,
IDXBUMN20 and IDXHIDIV20), membership is modelled as a many-to-many mapping:

    STOCK_NAMES : ticker -> company display name (metadata)
    INDICES     : index name -> list of constituent tickers

These are a reasonable snapshot of the IDX semi-annual evaluations. Index
memberships change ~twice a year, so edit these lists freely.

NOTE: ISSI (Indonesia Sharia Stock Index) actually contains hundreds of names;
only a well-known subset is seeded here for performance. Extend as needed.

The full IDX listing lives in `market/idx_listed.py` (generated separately);
`all_tickers()` unions it with the index constituents above.
"""

from market.idx_listed import LISTED

# Display order of the index selector in the UI.
INDEX_ORDER: list[str] = [
    "LQ45",
    "IDX30",
    "JII",
    "ISSI",
    "IDXHIDIV20",
    "IDXBUMN20",
]

# ticker -> company name.
STOCK_NAMES: dict[str, str] = {
    "AADI": "Adaro Andalan Indonesia",
    "ACES": "Ace Hardware Indonesia",
    "ADHI": "Adhi Karya",
    "ADMR": "Adaro Minerals Indonesia",
    "ADRO": "Adaro Energy",
    "AGRO": "Bank Raya Indonesia",
    "AKRA": "AKR Corporindo",
    "AMRT": "Sumber Alfaria Trijaya",
    "ANTM": "Aneka Tambang",
    "ARTO": "Bank Jago",
    "ASII": "Astra International",
    "BBCA": "Bank Central Asia",
    "BBNI": "Bank Negara Indonesia",
    "BBRI": "Bank Rakyat Indonesia",
    "BBTN": "Bank Tabungan Negara",
    "BJBR": "Bank Pembangunan Daerah Jawa Barat",
    "BJTM": "Bank Pembangunan Daerah Jawa Timur",
    "BMRI": "Bank Mandiri",
    "BRIS": "Bank Syariah Indonesia",
    "BRPT": "Barito Pacific",
    "BSDE": "Bumi Serpong Damai",
    "CPIN": "Charoen Pokphand Indonesia",
    "CTRA": "Ciputra Development",
    "ELSA": "Elnusa",
    "ERAA": "Erajaya Swasembada",
    "EXCL": "XL Axiata",
    "GIAA": "Garuda Indonesia",
    "GOTO": "GoTo Gojek Tokopedia",
    "ICBP": "Indofood CBP Sukses Makmur",
    "INCO": "Vale Indonesia",
    "INDF": "Indofood Sukses Makmur",
    "INTP": "Indocement Tunggal Prakarsa",
    "ISAT": "Indosat Ooredoo Hutchison",
    "ITMG": "Indo Tambangraya Megah",
    "JPFA": "Japfa Comfeed Indonesia",
    "JSMR": "Jasa Marga",
    "KAEF": "Kimia Farma",
    "KLBF": "Kalbe Farma",
    "MAPI": "Mitra Adiperkasa",
    "MBMA": "Merdeka Battery Materials",
    "MDKA": "Merdeka Copper Gold",
    "MEDC": "Medco Energi Internasional",
    "MIKA": "Mitra Keluarga Karyasehat",
    "MTEL": "Dayamitra Telekomunikasi",
    "PGAS": "Perusahaan Gas Negara",
    "PGEO": "Pertamina Geothermal Energy",
    "PTBA": "Bukit Asam",
    "PTPP": "PP (Pembangunan Perumahan)",
    "PWON": "Pakuwon Jati",
    "SIDO": "Sido Muncul",
    "SMGR": "Semen Indonesia",
    "SMRA": "Summarecon Agung",
    "SRTG": "Saratoga Investama Sedaya",
    "TBIG": "Tower Bersama Infrastructure",
    "TINS": "Timah",
    "TLKM": "Telkom Indonesia",
    "TOWR": "Sarana Menara Nusantara",
    "TPIA": "Chandra Asri Pacific",
    "UNTR": "United Tractors",
    "UNVR": "Unilever Indonesia",
    "WSKT": "Waskita Karya",
}

# index name -> constituent tickers.
INDICES: dict[str, list[str]] = {
    "LQ45": [
        "AADI", "ACES", "ADMR", "ADRO", "AKRA", "AMRT",
        "ANTM", "ARTO", "ASII", "BBCA", "BBNI", "BBRI",
        "BBTN", "BMRI", "BRIS", "BRPT", "CPIN", "CTRA",
        "EXCL", "GOTO", "ICBP", "INCO", "INDF", "INTP",
        "ISAT", "ITMG", "JPFA", "JSMR", "KLBF", "MAPI",
        "MBMA", "MDKA", "MEDC", "PGAS", "PGEO", "PTBA",
        "SIDO", "SMGR", "SMRA", "TLKM", "TOWR", "TPIA",
        "UNTR", "UNVR",
    ],
    "IDX30": [
        "ACES", "ADRO", "AKRA", "AMRT", "ANTM", "ARTO",
        "ASII", "BBCA", "BBNI", "BBRI", "BMRI", "BRIS",
        "BRPT", "CPIN", "EXCL", "GOTO", "ICBP", "INCO",
        "INDF", "INTP", "KLBF", "MDKA", "MEDC", "PGAS",
        "PTBA", "SMGR", "TLKM", "TOWR", "TPIA", "UNVR",
    ],
    "JII": [  # Jakarta Islamic Index (30 sharia-compliant names)
        "AADI", "ADRO", "AKRA", "AMRT", "ANTM", "BRIS",
        "CPIN", "CTRA", "EXCL", "ICBP", "INCO", "INDF",
        "INTP", "ISAT", "JPFA", "JSMR", "KLBF", "MAPI",
        "MDKA", "MEDC", "PGAS", "PGEO", "PTBA", "SMGR",
        "SMRA", "TLKM", "TOWR", "TPIA", "UNTR", "UNVR",
    ],
    "ISSI": [  # Indonesia Sharia Stock Index (seeded subset)
        "AADI", "ACES", "ADRO", "AKRA", "AMRT", "ANTM",
        "ARTO", "BRIS", "CPIN", "CTRA", "ERAA", "EXCL",
        "ICBP", "INCO", "INDF", "INTP", "ISAT", "JPFA",
        "JSMR", "KLBF", "MAPI", "MDKA", "MEDC", "MIKA",
        "PGAS", "PGEO", "PTBA", "PWON", "SIDO", "SMGR",
        "SMRA", "SRTG", "TBIG", "TLKM", "TOWR", "TPIA",
        "UNTR", "UNVR",
    ],
    "IDXHIDIV20": [  # IDX High Dividend 20
        "ADRO", "ANTM", "ASII", "BBCA", "BBNI", "BBRI",
        "BMRI", "EXCL", "ICBP", "INDF", "INTP", "ITMG",
        "MEDC", "PGAS", "PTBA", "SMGR", "TLKM", "TOWR",
        "UNTR", "UNVR",
    ],
    "IDXBUMN20": [  # IDX BUMN20 (state-owned enterprises)
        "AGRO", "ANTM", "BBNI", "BBRI", "BBTN", "BJBR",
        "BJTM", "BMRI", "BRIS", "ELSA", "GIAA", "JSMR",
        "KAEF", "PGAS", "PTBA", "PTPP", "SMGR", "TINS",
        "TLKM", "WSKT",
    ],
}


def all_tickers() -> list[str]:
    """Every unique ticker across all indices AND the full IDX catalog."""
    seen: dict[str, None] = {}
    for members in INDICES.values():
        for t in members:
            seen[t] = None
    for t in LISTED:
        seen[t] = None
    return sorted(seen)


def name_for(ticker: str) -> str:
    """Company name, falling back to the bare ticker if unknown."""
    return (
        STOCK_NAMES.get(ticker)
        or LISTED.get(ticker)
        or ticker
    )


def associations() -> list[tuple[str, str]]:
    """Flatten INDICES into (ticker, index_name) pairs."""
    return [(t, idx) for idx, members in INDICES.items() for t in members]
