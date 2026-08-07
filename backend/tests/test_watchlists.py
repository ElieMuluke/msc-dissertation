"""Tests for the sanctions/FATF watchlist loaders, SQLite ingest and lookup service."""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.ingestion.watchlists import (
    WatchlistConfig,
    WatchlistStoreNotIngestedError,
    build_watchlist_system,
    iter_hmt_conlist,
    iter_ofac_sdn,
    iter_un_consolidated,
    normalize_name,
)
from app.ingestion.watchlists.ingest import ingest_watchlists

OFAC_CSV = (
    '306,"BANCO NACIONAL DE CUBA",-0- ,"CUBA",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,"a.k.a. \'BNC\'."\n'
    '540,"HELMS SHIPPING","vessel","IRAN-EO13902",-0- ,-0- ,"Tanker",-0- ,-0- ,-0- ,-0- ,"IMO 123"\n'
)

HMT_CSV = (
    "Last Updated,03/06/2026\n"
    "Name 6,Name 1,Name 2,Name 3,Name 4,Name 5,Title,Name Non-Latin Script,Non-Latin Script Type,"
    "Non-Latin Script Language,DOB,Town of Birth,Country of Birth,Nationality,Passport Number,"
    "Passport Details,National Identification Number,National Identification Details,Position,"
    "Address 1,Address 2,Address 3,Address 4,Address 5,Address 6,Post/Zip Code,Country,"
    "Other Information,Group Type,Alias Type,Alias Quality,Regime,Listed On,"
    "UK Sanctions List Date Designated,Last Updated,Group ID\n"
    "DOE,John,,,,,,,,,,,Syria,Syria,,,,,,,,,,,,,Syria,Test person,Individual,Primary name,,Syria,"
    "01/01/2020,01/01/2020,01/01/2020,14233\n"
)

UN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST dateGenerated="2026-08-04T23:00:05.475Z">
  <INDIVIDUALS>
    <INDIVIDUAL>
      <DATAID>6907993</DATAID>
      <FIRST_NAME>ERIC</FIRST_NAME>
      <SECOND_NAME>BADEGE</SECOND_NAME>
      <UN_LIST_TYPE>DRC</UN_LIST_TYPE>
      <COMMENTS1>Test comment</COMMENTS1>
      <INDIVIDUAL_ALIAS><ALIAS_NAME>Eryc Badegge</ALIAS_NAME></INDIVIDUAL_ALIAS>
    </INDIVIDUAL>
  </INDIVIDUALS>
  <ENTITIES>
    <ENTITY>
      <DATAID>6908402</DATAID>
      <FIRST_NAME>ADF</FIRST_NAME>
      <UN_LIST_TYPE>DRC</UN_LIST_TYPE>
    </ENTITY>
  </ENTITIES>
</CONSOLIDATED_LIST>
"""

FATF_JSON = {
    "as_of": "2026-06-19",
    "call_for_action": ["Iran", "Myanmar"],
    "increased_monitoring": ["Monaco", "Vietnam"],
    "aliases": {"burma": "Myanmar", "viet nam": "Vietnam"},
}


MANIFEST_JSON = {
    "generated": "2026-08-05",
    "files": {
        "sdn.csv": {
            "list": "OFAC SDN",
            "source_url": "https://www.treasury.gov/ofac/downloads/sdn.csv",
            "downloaded": "2026-08-05",
        }
    },
}


def _config(tmp_path) -> WatchlistConfig:
    return WatchlistConfig(directory=tmp_path, db_path=tmp_path / "watchlists_db.sqlite")


@pytest.fixture
def watchlists(tmp_path):
    (tmp_path / "sdn.csv").write_text(OFAC_CSV, encoding="latin-1")
    (tmp_path / "ConList.csv").write_text(HMT_CSV, encoding="utf-8")
    (tmp_path / "un_consolidated.xml").write_text(UN_XML, encoding="utf-8")
    (tmp_path / "fatf_high_risk.json").write_text(json.dumps(FATF_JSON), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(MANIFEST_JSON), encoding="utf-8")
    config = _config(tmp_path)
    ingest_watchlists(config)
    return build_watchlist_system(config)


def test_normalize_name_strips_accents_case_punctuation():
    assert normalize_name("  Côte-d'Ivoire ") == "cote d ivoire"


def test_iter_ofac_sdn_parses_nulls_and_programs(tmp_path):
    path = tmp_path / "sdn.csv"
    path.write_text(OFAC_CSV, encoding="latin-1")
    entries = list(iter_ofac_sdn(path))
    assert len(entries) == 2
    assert entries[0].name == "BANCO NACIONAL DE CUBA"
    assert entries[0].entity_type == "entity"  # "-0-" type defaults to entity
    assert entries[0].programs == ("CUBA",)
    assert entries[1].entity_type == "vessel"


def test_iter_hmt_conlist_joins_name_parts(tmp_path):
    path = tmp_path / "ConList.csv"
    path.write_text(HMT_CSV, encoding="utf-8")
    entries = list(iter_hmt_conlist(path))
    assert len(entries) == 1
    assert entries[0].name == "John DOE"
    assert entries[0].entry_id == "14233"
    assert entries[0].programs == ("Syria",)


def test_iter_un_consolidated_includes_aliases(tmp_path):
    path = tmp_path / "un.xml"
    path.write_text(UN_XML, encoding="utf-8")
    entries = list(iter_un_consolidated(path))
    names = {e.name for e in entries}
    assert names == {"ERIC BADEGE", "Eryc Badegge", "ADF"}


def test_screen_name_exact_match(watchlists):
    matches = watchlists.screen_name("Banco Nacional de Cuba")
    assert matches and matches[0].match_type == "exact" and matches[0].score == 1.0
    assert matches[0].entry.list_name == "OFAC SDN"


def test_screen_name_fuzzy_match(watchlists):
    matches = watchlists.screen_name("Banco Nacionale de Cuba")
    assert matches and matches[0].match_type == "fuzzy"
    assert matches[0].score >= 0.85


def test_screen_name_no_match(watchlists):
    assert watchlists.screen_name("Completely Clean Company Ltd") == []


def test_country_risk_statuses_and_aliases(watchlists):
    assert watchlists.country_risk("Iran").status == "call_for_action"
    assert watchlists.country_risk("burma").status == "call_for_action"
    assert watchlists.country_risk("Viet Nam").status == "increased_monitoring"
    assert watchlists.country_risk("France").status == "not_listed"


def test_counts_per_list(watchlists):
    counts = watchlists.counts()
    assert counts == {"OFAC SDN": 2, "HMT": 1, "UN": 3}


def test_missing_source_files_are_skipped_by_ingest(tmp_path):
    """Ingesting an empty directory still builds a (empty) store that answers cleanly."""
    config = _config(tmp_path)
    summary = ingest_watchlists(config)
    assert summary["sanctions_total"] == 0
    system = build_watchlist_system(config)
    assert system.counts() == {}
    assert system.screen_name("anyone") == []
    assert system.country_risk("Iran").status == "not_listed"


def test_unbuilt_store_raises_not_ingested(tmp_path):
    """Without the SQLite store, lookups raise the explicit not-ingested error."""
    system = build_watchlist_system(_config(tmp_path))  # never ingested
    with pytest.raises(WatchlistStoreNotIngestedError, match="watchlist store not ingested"):
        system.screen_name("anyone")
    with pytest.raises(WatchlistStoreNotIngestedError, match="watchlist store not ingested"):
        system.country_risk("Iran")


def test_ingest_summary_and_provenance(watchlists, tmp_path):
    """Ingest records manifest provenance (source URLs, retrieved dates) in the store."""
    with sqlite3.connect(tmp_path / "watchlists_db.sqlite") as conn:
        rows = conn.execute(
            "SELECT filename, list_name, source_url, downloaded FROM provenance"
        ).fetchall()
        meta = dict(conn.execute("SELECT key, value FROM meta"))
    assert rows == [
        ("sdn.csv", "OFAC SDN", "https://www.treasury.gov/ofac/downloads/sdn.csv", "2026-08-05")
    ]
    assert meta["fatf_as_of"] == "2026-06-19"
    assert meta["manifest_generated"] == "2026-08-05"
    assert meta["ingested_at"]


def test_real_store_reproduces_expected_counts():
    """The production store (built by `python -m app.ingestion.watchlists.ingest` from the
    real downloaded lists) must reproduce the pre-refactor 42,705-entry load count."""
    config = WatchlistConfig()
    if not config.db_path.is_file():
        pytest.skip("production watchlist store not ingested")
    counts = build_watchlist_system(config).counts()
    assert counts == {"OFAC SDN": 19178, "HMT": 19761, "UN": 3766}
    assert sum(counts.values()) == 42705
