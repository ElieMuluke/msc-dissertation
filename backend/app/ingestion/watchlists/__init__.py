"""Sanctions + country-risk watchlists — screen names against the downloaded OFAC SDN,
HM Treasury/OFSI and UN Security Council consolidated lists, and countries against the
FATF black/grey lists.

    >>> from app.ingestion.watchlists import build_watchlist_system
    >>> watchlists = build_watchlist_system()
    >>> watchlists.screen_name("BANCO NACIONAL DE CUBA")[0].entry.list_name
    'OFAC SDN'
    >>> watchlists.country_risk("Iran").status
    'call_for_action'

List files live under ``backend/data/watchlists/`` with download provenance recorded in
``manifest.json`` there. Refreshing is manual: re-download and update the manifest.
"""

from __future__ import annotations

from .config import WatchlistConfig
from .loaders import (
    WatchlistEntry,
    iter_hmt_conlist,
    iter_ofac_sdn,
    iter_un_consolidated,
    load_fatf_lists,
)
from .service import CountryRisk, SanctionsMatch, WatchlistSystem, build_watchlist_system, normalize_name

__all__ = [
    "WatchlistConfig",
    "WatchlistEntry",
    "WatchlistSystem",
    "SanctionsMatch",
    "CountryRisk",
    "build_watchlist_system",
    "normalize_name",
    "iter_ofac_sdn",
    "iter_hmt_conlist",
    "iter_un_consolidated",
    "load_fatf_lists",
]
