"""SQLite-backed lookup facade over the ingested sanctions + FATF watchlist store.

Runtime data access goes through ``watchlists_db.sqlite`` only (built by
``python -m app.ingestion.watchlists.ingest``); the downloaded list files are
ingest-time inputs and are never read here. Every lookup opens a short-lived
read-only connection — there is no in-memory index to build or drift, and the
matching semantics (exact / substring / fuzzy passes, scores, ordering) are
byte-for-byte those of the previous in-memory implementation: candidate names are
scanned in first-occurrence order (``MIN(id)``), which the ingest step preserves
from loader yield order.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .config import WatchlistConfig
from .loaders import WatchlistEntry

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def normalize_name(name: str) -> str:
    """Normalise a name for matching: strip accents, punctuation, case, extra spaces."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(_NON_ALNUM.sub(" ", ascii_only).split())


class WatchlistStoreNotIngestedError(RuntimeError):
    """The watchlist SQLite store is missing — the ingest step has not been run."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(
            f"watchlist store not ingested: {db_path} is missing or empty. Build it with "
            "`python -m app.ingestion.watchlists.ingest` (run from backend/); the source "
            "list files and their download instructions are documented in "
            "backend/data/watchlists/manifest.json."
        )


@dataclass(frozen=True)
class SanctionsMatch:
    """One sanctions-list hit for a screened name."""

    entry: WatchlistEntry
    matched_name: str
    score: float
    match_type: str  # "exact" | "substring" | "fuzzy"


@dataclass(frozen=True)
class CountryRisk:
    """FATF standing of one jurisdiction."""

    country: str
    matched_jurisdiction: Optional[str]
    status: str  # "call_for_action" | "increased_monitoring" | "not_listed"
    list_date: str
    source: str


class WatchlistSystem:
    """Screen names against OFAC/HMT/UN lists and countries against the FATF lists.

    Construction never touches the database (so the app boots without it); every
    method opens a read-only connection and raises
    :class:`WatchlistStoreNotIngestedError` if the store is absent.
    """

    def __init__(self, db_path: Union[str, Path], match_threshold: float) -> None:
        self._db_path = Path(db_path)
        self._threshold = match_threshold

    def _connect(self) -> sqlite3.Connection:
        if not self._db_path.is_file():
            raise WatchlistStoreNotIngestedError(self._db_path)
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        ingested = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sanctions_entries'"
        ).fetchone()
        if ingested is None:
            conn.close()
            raise WatchlistStoreNotIngestedError(self._db_path)
        return conn

    @staticmethod
    def _entries_for(conn: sqlite3.Connection, normalized: str) -> list[WatchlistEntry]:
        rows = conn.execute(
            "SELECT list_name, entry_id, name, entity_type, programs, remarks"
            " FROM sanctions_entries WHERE normalized_name = ? ORDER BY id",
            (normalized,),
        ).fetchall()
        return [
            WatchlistEntry(
                list_name=list_name,
                entry_id=entry_id,
                name=name,
                entity_type=entity_type,
                programs=tuple(json.loads(programs)),
                remarks=remarks,
            )
            for list_name, entry_id, name, entity_type, programs, remarks in rows
        ]

    def counts(self) -> dict[str, int]:
        """Entry counts per source list, e.g. for a health/status display."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT list_name, COUNT(*) FROM sanctions_entries"
                " GROUP BY list_name ORDER BY MIN(id)"
            ).fetchall()
        return dict(rows)

    def screen_name(self, name: str, max_results: int = 10) -> list[SanctionsMatch]:
        """Screen ``name`` against all loaded lists, best matches first.

        Three passes, cheapest first: exact normalized match, whole-word substring
        containment (either direction), then difflib fuzzy match at
        ``match_threshold``. Duplicate entries across passes are kept once at their
        strongest match.
        """
        query = normalize_name(name)
        if not query:
            return []

        with closing(self._connect()) as conn:
            # Unique candidate names in first-occurrence order — the same order the old
            # in-memory index iterated, which fuzzy-tie-breaking and ranking rely on.
            names = [
                row[0]
                for row in conn.execute(
                    "SELECT normalized_name FROM sanctions_entries"
                    " GROUP BY normalized_name ORDER BY MIN(id)"
                )
            ]

            matches: dict[tuple[str, str, str], SanctionsMatch] = {}

            def add(entry: WatchlistEntry, matched: str, score: float, match_type: str) -> None:
                key = (entry.list_name, entry.entry_id, entry.name)
                existing = matches.get(key)
                if existing is None or score > existing.score:
                    matches[key] = SanctionsMatch(
                        entry=entry, matched_name=matched, score=score, match_type=match_type
                    )

            for entry in self._entries_for(conn, query):
                add(entry, query, 1.0, "exact")

            padded_query = f" {query} "
            for candidate in names:
                if f" {candidate} " in padded_query or padded_query in f" {candidate} ":
                    score = min(len(query), len(candidate)) / max(len(query), len(candidate))
                    for entry in self._entries_for(conn, candidate):
                        add(entry, candidate, round(0.99 * score, 4), "substring")

            for candidate in difflib.get_close_matches(query, names, n=max_results, cutoff=self._threshold):
                score = difflib.SequenceMatcher(None, query, candidate).ratio()
                for entry in self._entries_for(conn, candidate):
                    add(entry, candidate, round(score, 4), "fuzzy")

        ranked = sorted(matches.values(), key=lambda m: m.score, reverse=True)
        return ranked[:max_results]

    def country_risk(self, country: str) -> CountryRisk:
        """Look up ``country`` on the FATF call-for-action / increased-monitoring lists."""
        key = normalize_name(country)
        source = "FATF High-Risk Jurisdictions / Jurisdictions under Increased Monitoring statements"
        with closing(self._connect()) as conn:
            as_of_row = conn.execute("SELECT value FROM meta WHERE key = 'fatf_as_of'").fetchone()
            hit = conn.execute(
                "SELECT status, jurisdiction FROM fatf_jurisdictions WHERE normalized_key = ?",
                (key,),
            ).fetchone()
        as_of = as_of_row[0] if as_of_row else ""
        if hit is None:
            return CountryRisk(country=country, matched_jurisdiction=None, status="not_listed", list_date=as_of, source=source)
        status, jurisdiction = hit
        return CountryRisk(country=country, matched_jurisdiction=jurisdiction, status=status, list_date=as_of, source=source)


def build_watchlist_system(config: Optional[WatchlistConfig] = None) -> WatchlistSystem:
    """Point a :class:`WatchlistSystem` at the configured SQLite store.

    Never fails at build time: if the store has not been ingested yet, lookups raise
    :class:`WatchlistStoreNotIngestedError`, which the agent tools surface as an
    explicit "watchlist store not ingested" message rather than a crash.
    """
    config = config or WatchlistConfig()
    return WatchlistSystem(config.db_path, config.match_threshold)
