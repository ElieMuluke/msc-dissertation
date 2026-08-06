"""In-memory lookup facade over the downloaded sanctions + FATF list files.

Loaders (:mod:`.loaders`) stream file rows; this module owns the only state — a
name index built once at construction — keeping the same pure-core/thin-shell split
as ``ingestion.tabular``. List files are small enough (tens of MB) that an in-memory
index is simpler and faster than a second SQLite store.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from .config import WatchlistConfig
from .loaders import (
    WatchlistEntry,
    iter_hmt_conlist,
    iter_ofac_sdn,
    iter_un_consolidated,
    load_fatf_lists,
)

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def normalize_name(name: str) -> str:
    """Normalise a name for matching: strip accents, punctuation, case, extra spaces."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(_NON_ALNUM.sub(" ", ascii_only).split())


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
    """Screen names against OFAC/HMT/UN lists and countries against the FATF lists."""

    def __init__(self, entries: list[WatchlistEntry], fatf: dict, match_threshold: float) -> None:
        self._entries = entries
        self._threshold = match_threshold
        # normalized name -> indices into _entries (exact-match fast path); plus the
        # unique normalized-name list difflib scans for fuzzy candidates.
        self._by_name: dict[str, list[int]] = {}
        for i, entry in enumerate(entries):
            self._by_name.setdefault(normalize_name(entry.name), []).append(i)
        self._names = list(self._by_name)

        self._fatf = fatf
        self._fatf_status: dict[str, tuple[str, str]] = {}
        for status_key in ("call_for_action", "increased_monitoring"):
            for jurisdiction in fatf.get(status_key, []):
                self._fatf_status[normalize_name(jurisdiction)] = (status_key, jurisdiction)
        for alias, canonical in fatf.get("aliases", {}).items():
            canonical_key = normalize_name(canonical)
            if canonical_key in self._fatf_status:
                self._fatf_status[normalize_name(alias)] = self._fatf_status[canonical_key]

    def counts(self) -> dict[str, int]:
        """Entry counts per source list, e.g. for a health/status display."""
        result: dict[str, int] = {}
        for entry in self._entries:
            result[entry.list_name] = result.get(entry.list_name, 0) + 1
        return result

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

        matches: dict[tuple[str, str, str], SanctionsMatch] = {}

        def add(index: int, matched: str, score: float, match_type: str) -> None:
            entry = self._entries[index]
            key = (entry.list_name, entry.entry_id, entry.name)
            existing = matches.get(key)
            if existing is None or score > existing.score:
                matches[key] = SanctionsMatch(entry=entry, matched_name=matched, score=score, match_type=match_type)

        for index in self._by_name.get(query, []):
            add(index, query, 1.0, "exact")

        padded_query = f" {query} "
        for candidate in self._names:
            if f" {candidate} " in padded_query or padded_query in f" {candidate} ":
                score = min(len(query), len(candidate)) / max(len(query), len(candidate))
                for index in self._by_name[candidate]:
                    add(index, candidate, round(0.99 * score, 4), "substring")

        for candidate in difflib.get_close_matches(query, self._names, n=max_results, cutoff=self._threshold):
            score = difflib.SequenceMatcher(None, query, candidate).ratio()
            for index in self._by_name[candidate]:
                add(index, candidate, round(score, 4), "fuzzy")

        ranked = sorted(matches.values(), key=lambda m: m.score, reverse=True)
        return ranked[:max_results]

    def country_risk(self, country: str) -> CountryRisk:
        """Look up ``country`` on the FATF call-for-action / increased-monitoring lists."""
        key = normalize_name(country)
        as_of = self._fatf.get("as_of", "")
        source = "FATF High-Risk Jurisdictions / Jurisdictions under Increased Monitoring statements"
        hit = self._fatf_status.get(key)
        if hit is None:
            return CountryRisk(country=country, matched_jurisdiction=None, status="not_listed", list_date=as_of, source=source)
        status, jurisdiction = hit
        return CountryRisk(country=country, matched_jurisdiction=jurisdiction, status=status, list_date=as_of, source=source)


def build_watchlist_system(config: Optional[WatchlistConfig] = None) -> WatchlistSystem:
    """Load every list file named in ``config`` into a ready :class:`WatchlistSystem`.

    Missing files are skipped (with the corresponding list simply absent from
    :meth:`WatchlistSystem.counts`) rather than fatal, so a fresh checkout without the
    downloaded lists still boots — ``manifest.json`` documents how to fetch them.
    """
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
    return WatchlistSystem(entries, fatf, config.match_threshold)
