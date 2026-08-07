"""SQLite write path for the watchlist store (schema + rebuild).

The ingest step (:mod:`.ingest`) parses the downloaded list files with :mod:`.loaders`
and hands the rows to :func:`write_store`, which rebuilds ``watchlists_db.sqlite``
atomically (build into a temp file, then replace). The runtime read path lives in
:mod:`.service`; nothing at runtime touches the source files.

Tables:
    sanctions_entries   one row per (possibly alias) name across OFAC SDN / HMT / UN,
                        with the pre-computed ``normalized_name`` the matcher keys on.
                        Row ``id`` order preserves loader yield order — the matcher's
                        candidate ordering (and therefore tie-breaking) depends on it.
    fatf_jurisdictions  normalized name/alias -> FATF status + canonical jurisdiction,
                        pre-resolved exactly as the old in-memory lookup table was.
    provenance          one row per source file, from ``manifest.json`` (source URL,
                        retrieved date, list date, format notes).
    meta                key/value: ``fatf_as_of``, ``ingested_at``, manifest header.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from .loaders import WatchlistEntry
from .service import normalize_name

_SCHEMA = """
CREATE TABLE sanctions_entries (
    id INTEGER PRIMARY KEY,
    list_name TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    programs TEXT NOT NULL,
    remarks TEXT NOT NULL
);
CREATE INDEX ix_sanctions_normalized_name ON sanctions_entries (normalized_name);
CREATE TABLE fatf_jurisdictions (
    normalized_key TEXT PRIMARY KEY,
    jurisdiction TEXT NOT NULL,
    status TEXT NOT NULL,
    is_alias INTEGER NOT NULL
);
CREATE TABLE provenance (
    filename TEXT PRIMARY KEY,
    list_name TEXT,
    source_url TEXT,
    status TEXT,
    downloaded TEXT,
    list_date TEXT,
    format TEXT
);
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _fatf_rows(fatf: dict) -> list[tuple[str, str, str, int]]:
    """Resolve the FATF dict into lookup rows, mirroring the old in-memory table.

    Canonical jurisdictions first; aliases only when their canonical is itself listed,
    carrying the canonical's (status, jurisdiction) pair. Later keys overwrite earlier
    ones (dict semantics), hence the intermediate dict.
    """
    rows: dict[str, tuple[str, str, int]] = {}
    for status_key in ("call_for_action", "increased_monitoring"):
        for jurisdiction in fatf.get(status_key, []):
            rows[normalize_name(jurisdiction)] = (jurisdiction, status_key, 0)
    for alias, canonical in fatf.get("aliases", {}).items():
        canonical_key = normalize_name(canonical)
        if canonical_key in rows:
            jurisdiction, status, _ = rows[canonical_key]
            rows[normalize_name(alias)] = (jurisdiction, status, 1)
    return [(key, *value) for key, value in rows.items()]


def write_store(
    db_path: Union[str, Path],
    entries: Iterable[WatchlistEntry],
    fatf: dict,
    manifest: dict,
) -> dict:
    """Rebuild the watchlist SQLite file from parsed rows; return a summary dict.

    Builds into ``<db_path>.building`` and atomically replaces ``db_path``, so a crash
    mid-ingest never leaves a half-written store behind.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_name(db_path.name + ".building")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(_SCHEMA)
        sanctions_counts: dict[str, int] = {}
        for entry in entries:
            conn.execute(
                "INSERT INTO sanctions_entries"
                " (list_name, entry_id, name, normalized_name, entity_type, programs, remarks)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.list_name,
                    entry.entry_id,
                    entry.name,
                    normalize_name(entry.name),
                    entry.entity_type,
                    json.dumps(list(entry.programs), ensure_ascii=False),
                    entry.remarks,
                ),
            )
            sanctions_counts[entry.list_name] = sanctions_counts.get(entry.list_name, 0) + 1

        fatf_rows = _fatf_rows(fatf)
        conn.executemany(
            "INSERT INTO fatf_jurisdictions (normalized_key, jurisdiction, status, is_alias)"
            " VALUES (?, ?, ?, ?)",
            fatf_rows,
        )

        for filename, info in (manifest.get("files") or {}).items():
            conn.execute(
                "INSERT INTO provenance"
                " (filename, list_name, source_url, status, downloaded, list_date, format)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    filename,
                    info.get("list"),
                    info.get("source_url"),
                    info.get("status"),
                    info.get("downloaded"),
                    info.get("list_date"),
                    info.get("format"),
                ),
            )

        ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta = {
            "fatf_as_of": fatf.get("as_of", ""),
            "ingested_at": ingested_at,
            "manifest_generated": manifest.get("generated", ""),
        }
        conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", meta.items())
        conn.commit()
    finally:
        conn.close()

    os.replace(tmp_path, db_path)
    return {
        "db_path": str(db_path),
        "sanctions_counts": sanctions_counts,
        "sanctions_total": sum(sanctions_counts.values()),
        "fatf_keys": len(fatf_rows),
        "fatf_aliases": sum(1 for row in fatf_rows if row[3]),
        "provenance_rows": len(manifest.get("files") or {}),
        "ingested_at": ingested_at,
    }
