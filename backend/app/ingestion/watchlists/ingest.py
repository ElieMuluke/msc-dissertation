"""Ingest step: parse the downloaded watchlist files into ``watchlists_db.sqlite``.

Run from ``backend/``::

    python -m app.ingestion.watchlists.ingest

List refresh is a two-step manual process: (1) re-download the source files into
``backend/data/watchlists/`` and update ``manifest.json`` there (URLs, retrieved and
list dates — the manifest is copied into the store's ``provenance`` table), then
(2) re-run this command, which rebuilds every table from scratch. The app only ever
reads the SQLite store; missing source files are skipped (their list is simply absent),
mirroring the old file-loading behaviour.
"""

from __future__ import annotations

import json
from typing import Optional

from .config import WatchlistConfig
from .loaders import (
    WatchlistEntry,
    iter_hmt_conlist,
    iter_ofac_sdn,
    iter_un_consolidated,
    load_fatf_lists,
)
from .store import write_store

_MANIFEST_FILE = "manifest.json"


def ingest_watchlists(config: Optional[WatchlistConfig] = None) -> dict:
    """Rebuild the watchlist store from the files named in ``config``; return the summary."""
    config = config or WatchlistConfig()
    entries: list[WatchlistEntry] = []
    loaders = (
        (config.ofac_sdn_file, iter_ofac_sdn),
        (config.hmt_conlist_file, iter_hmt_conlist),
        (config.un_consolidated_file, iter_un_consolidated),
    )
    for filename, loader in loaders:
        path = config.directory / filename
        if path.is_file():
            entries.extend(loader(path))

    fatf_path = config.directory / config.fatf_file
    fatf = load_fatf_lists(fatf_path) if fatf_path.is_file() else {}

    manifest_path = config.directory / _MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}

    return write_store(config.db_path, entries, fatf, manifest)


def main() -> None:
    """CLI entry point: rebuild the store and print the ingest summary."""
    summary = ingest_watchlists()
    print(f"watchlist store rebuilt: {summary['db_path']}")
    for list_name, count in summary["sanctions_counts"].items():
        print(f"  {list_name}: {count}")
    print(f"  total sanctions entries: {summary['sanctions_total']}")
    print(f"  FATF lookup keys: {summary['fatf_keys']} ({summary['fatf_aliases']} aliases)")
    print(f"  provenance rows: {summary['provenance_rows']}")
    print(f"  ingested at: {summary['ingested_at']}")
    print(
        "list refresh = re-download the source files into backend/data/watchlists/ "
        "(see manifest.json there), update the manifest, then re-run this command."
    )


if __name__ == "__main__":
    main()
