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
    "AADI.JK": "Adaro Andalan Indonesia",
    "ACES.JK": "Ace Hardware Indonesia",
    "ADHI.JK": "Adhi Karya",
    "ADMR.JK": "Adaro Minerals Indonesia",
    "ADRO.JK": "Adaro Energy",
    "AGRO.JK": "Bank Raya Indonesia",
    "AKRA.JK": "AKR Corporindo",
    "AMRT.JK": "Sumber Alfaria Trijaya",
    "ANTM.JK": "Aneka Tambang",
    "ARTO.JK": "Bank Jago",
    "ASII.JK": "Astra International",
    "BBCA.JK": "Bank Central Asia",
    "BBNI.JK": "Bank Negara Indonesia",
    "BBRI.JK": "Bank Rakyat Indonesia",
    "BBTN.JK": "Bank Tabungan Negara",
    "BJBR.JK": "Bank Pembangunan Daerah Jawa Barat",
    "BJTM.JK": "Bank Pembangunan Daerah Jawa Timur",
    "BMRI.JK": "Bank Mandiri",
    "BRIS.JK": "Bank Syariah Indonesia",
    "BRPT.JK": "Barito Pacific",
    "BSDE.JK": "Bumi Serpong Damai",
    "CPIN.JK": "Charoen Pokphand Indonesia",
    "CTRA.JK": "Ciputra Development",
    "ELSA.JK": "Elnusa",
    "ERAA.JK": "Erajaya Swasembada",
    "EXCL.JK": "XL Axiata",
    "GIAA.JK": "Garuda Indonesia",
    "GOTO.JK": "GoTo Gojek Tokopedia",
    "ICBP.JK": "Indofood CBP Sukses Makmur",
    "INCO.JK": "Vale Indonesia",
    "INDF.JK": "Indofood Sukses Makmur",
    "INTP.JK": "Indocement Tunggal Prakarsa",
    "ISAT.JK": "Indosat Ooredoo Hutchison",
    "ITMG.JK": "Indo Tambangraya Megah",
    "JPFA.JK": "Japfa Comfeed Indonesia",
    "JSMR.JK": "Jasa Marga",
    "KAEF.JK": "Kimia Farma",
    "KLBF.JK": "Kalbe Farma",
    "MAPI.JK": "Mitra Adiperkasa",
    "MBMA.JK": "Merdeka Battery Materials",
    "MDKA.JK": "Merdeka Copper Gold",
    "MEDC.JK": "Medco Energi Internasional",
    "MIKA.JK": "Mitra Keluarga Karyasehat",
    "MTEL.JK": "Dayamitra Telekomunikasi",
    "PGAS.JK": "Perusahaan Gas Negara",
    "PGEO.JK": "Pertamina Geothermal Energy",
    "PTBA.JK": "Bukit Asam",
    "PTPP.JK": "PP (Pembangunan Perumahan)",
    "PWON.JK": "Pakuwon Jati",
    "SIDO.JK": "Sido Muncul",
    "SMGR.JK": "Semen Indonesia",
    "SMRA.JK": "Summarecon Agung",
    "SRTG.JK": "Saratoga Investama Sedaya",
    "TBIG.JK": "Tower Bersama Infrastructure",
    "TINS.JK": "Timah",
    "TLKM.JK": "Telkom Indonesia",
    "TOWR.JK": "Sarana Menara Nusantara",
    "TPIA.JK": "Chandra Asri Pacific",
    "UNTR.JK": "United Tractors",
    "UNVR.JK": "Unilever Indonesia",
    "WSKT.JK": "Waskita Karya",
}

# index name -> constituent tickers.
INDICES: dict[str, list[str]] = {
    "LQ45": [
        "AADI.JK", "ACES.JK", "ADMR.JK", "ADRO.JK", "AKRA.JK", "AMRT.JK",
        "ANTM.JK", "ARTO.JK", "ASII.JK", "BBCA.JK", "BBNI.JK", "BBRI.JK",
        "BBTN.JK", "BMRI.JK", "BRIS.JK", "BRPT.JK", "CPIN.JK", "CTRA.JK",
        "EXCL.JK", "GOTO.JK", "ICBP.JK", "INCO.JK", "INDF.JK", "INTP.JK",
        "ISAT.JK", "ITMG.JK", "JPFA.JK", "JSMR.JK", "KLBF.JK", "MAPI.JK",
        "MBMA.JK", "MDKA.JK", "MEDC.JK", "PGAS.JK", "PGEO.JK", "PTBA.JK",
        "SIDO.JK", "SMGR.JK", "SMRA.JK", "TLKM.JK", "TOWR.JK", "TPIA.JK",
        "UNTR.JK", "UNVR.JK",
    ],
    "IDX30": [
        "ACES.JK", "ADRO.JK", "AKRA.JK", "AMRT.JK", "ANTM.JK", "ARTO.JK",
        "ASII.JK", "BBCA.JK", "BBNI.JK", "BBRI.JK", "BMRI.JK", "BRIS.JK",
        "BRPT.JK", "CPIN.JK", "EXCL.JK", "GOTO.JK", "ICBP.JK", "INCO.JK",
        "INDF.JK", "INTP.JK", "KLBF.JK", "MDKA.JK", "MEDC.JK", "PGAS.JK",
        "PTBA.JK", "SMGR.JK", "TLKM.JK", "TOWR.JK", "TPIA.JK", "UNVR.JK",
    ],
    "JII": [  # Jakarta Islamic Index (30 sharia-compliant names)
        "AADI.JK", "ADRO.JK", "AKRA.JK", "AMRT.JK", "ANTM.JK", "BRIS.JK",
        "CPIN.JK", "CTRA.JK", "EXCL.JK", "ICBP.JK", "INCO.JK", "INDF.JK",
        "INTP.JK", "ISAT.JK", "JPFA.JK", "JSMR.JK", "KLBF.JK", "MAPI.JK",
        "MDKA.JK", "MEDC.JK", "PGAS.JK", "PGEO.JK", "PTBA.JK", "SMGR.JK",
        "SMRA.JK", "TLKM.JK", "TOWR.JK", "TPIA.JK", "UNTR.JK", "UNVR.JK",
    ],
    "ISSI": [  # Indonesia Sharia Stock Index (seeded subset)
        "AADI.JK", "ACES.JK", "ADRO.JK", "AKRA.JK", "AMRT.JK", "ANTM.JK",
        "ARTO.JK", "BRIS.JK", "CPIN.JK", "CTRA.JK", "ERAA.JK", "EXCL.JK",
        "ICBP.JK", "INCO.JK", "INDF.JK", "INTP.JK", "ISAT.JK", "JPFA.JK",
        "JSMR.JK", "KLBF.JK", "MAPI.JK", "MDKA.JK", "MEDC.JK", "MIKA.JK",
        "PGAS.JK", "PGEO.JK", "PTBA.JK", "PWON.JK", "SIDO.JK", "SMGR.JK",
        "SMRA.JK", "SRTG.JK", "TBIG.JK", "TLKM.JK", "TOWR.JK", "TPIA.JK",
        "UNTR.JK", "UNVR.JK",
    ],
    "IDXHIDIV20": [  # IDX High Dividend 20
        "ADRO.JK", "ANTM.JK", "ASII.JK", "BBCA.JK", "BBNI.JK", "BBRI.JK",
        "BMRI.JK", "EXCL.JK", "ICBP.JK", "INDF.JK", "INTP.JK", "ITMG.JK",
        "MEDC.JK", "PGAS.JK", "PTBA.JK", "SMGR.JK", "TLKM.JK", "TOWR.JK",
        "UNTR.JK", "UNVR.JK",
    ],
    "IDXBUMN20": [  # IDX BUMN20 (state-owned enterprises)
        "AGRO.JK", "ANTM.JK", "BBNI.JK", "BBRI.JK", "BBTN.JK", "BJBR.JK",
        "BJTM.JK", "BMRI.JK", "BRIS.JK", "ELSA.JK", "GIAA.JK", "JSMR.JK",
        "KAEF.JK", "PGAS.JK", "PTBA.JK", "PTPP.JK", "SMGR.JK", "TINS.JK",
        "TLKM.JK", "WSKT.JK",
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
        or ticker.replace(".JK", "")
    )


def associations() -> list[tuple[str, str]]:
    """Flatten INDICES into (ticker, index_name) pairs."""
    return [(t, idx) for idx, members in INDICES.items() for t in members]
