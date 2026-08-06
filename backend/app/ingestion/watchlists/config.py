"""Configuration for the sanctions/country-risk watchlist system.

A single immutable config object is injected at build time so nothing downstream
hardcodes file locations (Dependency Inversion, mirroring ``ingestion.tabular.config``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# backend/ is the working directory the app runs from (uvicorn app.main:app), but resolve
# relative to this file so tests invoked from anywhere still find the shipped list files.
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "watchlists"


@dataclass(frozen=True)
class WatchlistConfig:
    """Settings for building a :class:`WatchlistSystem`.

    Attributes:
        directory: Directory holding the downloaded list files + ``manifest.json``.
        ofac_sdn_file: OFAC SDN CSV filename within ``directory``.
        hmt_conlist_file: HM Treasury/OFSI consolidated list CSV filename.
        un_consolidated_file: UN Security Council consolidated list XML filename.
        fatf_file: FATF high-risk/increased-monitoring jurisdictions JSON filename.
        match_threshold: Minimum similarity ratio (0-1) for a fuzzy name match to count
            as a hit. 0.85 keeps obvious transliteration variants while excluding noise.
    """

    directory: Path = field(default=_DEFAULT_DIR)
    ofac_sdn_file: str = "sdn.csv"
    hmt_conlist_file: str = "ConList.csv"
    un_consolidated_file: str = "un_consolidated.xml"
    fatf_file: str = "fatf_high_risk.json"
    match_threshold: float = 0.85
