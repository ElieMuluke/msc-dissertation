"""Configuration for the sanctions/country-risk watchlist system.

A single immutable config object is injected at build time so nothing downstream
hardcodes file locations (Dependency Inversion, mirroring ``ingestion.tabular.config``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# backend/ is the working directory the app runs from (uvicorn app.main:app), but resolve
# relative to this file so tests invoked from anywhere still find the shipped list files.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_DIR = _BACKEND_DIR / "data" / "watchlists"

# The watchlist store is deliberately a SEPARATE SQLite file from the tabular store
# (``backend/tabular_data_db.sqlite``): the tabular db is a multi-GB production store
# that must never be locked/rewritten by a list refresh, while this file is small
# (tens of MB) and rebuilt wholesale by ``python -m app.ingestion.watchlists.ingest``
# every time the source lists are re-downloaded. "Tabular DB" remains the store *layer*;
# it just spans two files.
_DEFAULT_DB = _BACKEND_DIR / "watchlists_db.sqlite"


@dataclass(frozen=True)
class WatchlistConfig:
    """Settings for the watchlist store (ingest inputs + SQLite output).

    Attributes:
        directory: Directory holding the downloaded list files + ``manifest.json``
            (ingest-time inputs only; the app never reads them at runtime).
        db_path: SQLite file the ingest step writes and :class:`WatchlistSystem` queries.
        ofac_sdn_file: OFAC SDN CSV filename within ``directory``.
        hmt_conlist_file: HM Treasury/OFSI consolidated list CSV filename.
        un_consolidated_file: UN Security Council consolidated list XML filename.
        fatf_file: FATF high-risk/increased-monitoring jurisdictions JSON filename.
        match_threshold: Minimum similarity ratio (0-1) for a fuzzy name match to count
            as a hit. 0.85 keeps obvious transliteration variants while excluding noise.
    """

    directory: Path = field(default=_DEFAULT_DIR)
    db_path: Path = field(default=_DEFAULT_DB)
    ofac_sdn_file: str = "sdn.csv"
    hmt_conlist_file: str = "ConList.csv"
    un_consolidated_file: str = "un_consolidated.xml"
    fatf_file: str = "fatf_high_risk.json"
    match_threshold: float = 0.85
