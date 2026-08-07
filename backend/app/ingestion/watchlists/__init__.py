"""Sanctions + country-risk watchlists — screen names against the OFAC SDN, HM
Treasury/OFSI and UN Security Council consolidated lists, and countries against the
FATF black/grey lists, all served from the SQLite watchlist store.

    >>> from app.ingestion.watchlists import build_watchlist_system
    >>> watchlists = build_watchlist_system()
    >>> watchlists.screen_name("BANCO NACIONAL DE CUBA")[0].entry.list_name
    'OFAC SDN'
    >>> watchlists.country_risk("Iran").status
    'call_for_action'

Runtime reads go through ``backend/watchlists_db.sqlite`` only; the downloaded list
files under ``backend/data/watchlists/`` (provenance in ``manifest.json`` there) are
ingest-time inputs. Refreshing is manual: re-download the files, update the manifest,
then rebuild the store with ``python -m app.ingestion.watchlists.ingest``. If the store
has not been built, lookups raise :class:`WatchlistStoreNotIngestedError`.
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
from .service import (
    CountryRisk,
    SanctionsMatch,
    WatchlistStoreNotIngestedError,
    WatchlistSystem,
    build_watchlist_system,
    normalize_name,
)
from .store import write_store

__all__ = [
    "WatchlistConfig",
    "WatchlistEntry",
    "WatchlistSystem",
    "WatchlistStoreNotIngestedError",
    "SanctionsMatch",
    "CountryRisk",
    "build_watchlist_system",
    "write_store",
    "normalize_name",
    "iter_ofac_sdn",
    "iter_hmt_conlist",
    "iter_un_consolidated",
    "load_fatf_lists",
]
