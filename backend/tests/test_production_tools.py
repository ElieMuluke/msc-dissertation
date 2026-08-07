"""Tests for the production agent tools (tabular queries + sanctions + country risk)."""

from __future__ import annotations

import json

import pytest

from app.agents.production_tools import (
    build_country_risk_tool,
    build_production_tools,
    build_query_accounts_tool,
    build_query_transactions_tool,
    build_sanctions_check_tool,
)
from app.ingestion.tabular import TabularConfig, TabularDataType, build_tabular_system
from app.ingestion.watchlists import WatchlistSystem, write_store
from app.ingestion.watchlists.loaders import WatchlistEntry

ACCOUNTS_CSV = (
    "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\n"
    "Bank A,070,100428660,E1,Corporation #4482\n"
    "Bank B,214,900332145,E2,Nevada Spirit Company Limited\n"
)

TRANSACTIONS_CSV = (
    "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,"
    "Amount Paid,Payment Currency,Payment Format,Is Laundering\n"
    "2022/09/01 10:12,070,100428660,214,900332145,9400.00,US Dollar,9400.00,US Dollar,Wire,1\n"
    "2022/09/02 08:20,214,900332145,070,100428660,150.00,US Dollar,150.00,US Dollar,ACH,0\n"
    "2022/09/03 09:00,070,100428660,214,900332145,50.00,US Dollar,50.00,US Dollar,Cheque,0\n"
)


@pytest.fixture
def tabular():
    system = build_tabular_system(TabularConfig(db_url="sqlite:///:memory:"))
    system.ingest_text(TabularDataType.ACCOUNTS, ACCOUNTS_CSV)
    system.ingest_text(TabularDataType.TRANSACTIONS, TRANSACTIONS_CSV)
    return system


@pytest.fixture
def watchlists(tmp_path):
    entries = [
        WatchlistEntry("OFAC SDN", "306", "BANCO NACIONAL DE CUBA", "entity", ("CUBA",), "a.k.a. BNC"),
        WatchlistEntry("UN", "6907993", "ERIC BADEGE", "individual", ("DRC",), ""),
    ]
    fatf = {"as_of": "2026-06-19", "call_for_action": ["Iran"], "increased_monitoring": ["Monaco"], "aliases": {}}
    db_path = tmp_path / "watchlists_db.sqlite"
    write_store(db_path, entries, fatf, manifest={})
    return WatchlistSystem(db_path, match_threshold=0.85)


def test_query_accounts_tool_by_entity_name(tabular):
    tool = build_query_accounts_tool(tabular)
    payload = json.loads(tool.invoke({"entity_name": "nevada spirit"}))
    assert len(payload["accounts"]) == 1
    assert payload["accounts"][0]["account_number"] == "900332145"
    assert payload["row_ids"] == [payload["accounts"][0]["id"]]


def test_query_accounts_tool_requires_a_filter(tabular):
    tool = build_query_accounts_tool(tabular)
    assert "at least one filter" in tool.invoke({})


def test_query_transactions_tool_filters_direction_amount_dates(tabular):
    tool = build_query_transactions_tool(tabular)
    payload = json.loads(
        tool.invoke(
            {
                "account_number": "100428660",
                "direction": "out",
                "min_amount": 1000,
                "since": "2022-09-01",
                "until": "2022-09-02",
            }
        )
    )
    assert len(payload["transactions"]) == 1
    txn = payload["transactions"][0]
    assert txn["to_account"] == "900332145"
    assert txn["amount_paid"] == 9400.0
    # Ground-truth label must never be exposed to the agent (data leakage).
    assert "is_laundering" not in txn


def test_query_transactions_tool_rejects_bad_direction(tabular):
    tool = build_query_transactions_tool(tabular)
    with pytest.raises(Exception, match="direction"):
        tool.invoke({"account_number": "100428660", "direction": "sideways"})


def test_sanctions_check_tool_hit_and_miss(watchlists):
    tool = build_sanctions_check_tool(watchlists)
    payload = json.loads(tool.invoke({"name": "Banco Nacional de Cuba"}))
    assert payload["matches"][0]["list"] == "OFAC SDN"
    assert payload["matches"][0]["score"] == 1.0
    assert "No sanctions-list matches" in tool.invoke({"name": "Squeaky Clean Ltd"})


def test_country_risk_tool(watchlists):
    tool = build_country_risk_tool(watchlists)
    assert json.loads(tool.invoke({"country": "Iran"}))["status"] == "call_for_action"
    assert json.loads(tool.invoke({"country": "Monaco"}))["status"] == "increased_monitoring"
    assert json.loads(tool.invoke({"country": "Germany"}))["status"] == "not_listed"


def test_country_risk_tool_flags_non_jurisdiction_input(watchlists):
    """Regression: agents passed bank names ('Oasis Bancorp') and read the resulting
    not_listed as a clean jurisdiction screen. Unrecognised input must return an
    explicit warning instead of a status."""
    tool = build_country_risk_tool(watchlists)

    message = tool.invoke({"country": "Oasis Bancorp"})
    assert "does not look like a country/jurisdiction" in message
    assert "no jurisdiction/country column" in message
    # It must not be parseable as a normal status payload.
    with pytest.raises(json.JSONDecodeError):
        json.loads(message)

    # Known countries and their aliases still get a real status...
    assert json.loads(tool.invoke({"country": "USA"}))["status"] == "not_listed"
    assert json.loads(tool.invoke({"country": "United Kingdom"}))["status"] == "not_listed"
    # ...and FATF-listed jurisdictions are unaffected by the guard.
    assert json.loads(tool.invoke({"country": "Iran"}))["status"] == "call_for_action"
    # The description must warn that the dataset carries no country column.
    assert "no country column" in tool.description


def test_watchlist_tools_report_missing_store_without_crashing(tmp_path):
    """If the SQLite watchlist store was never ingested, both watchlist tools must
    return an explicit 'watchlist store not ingested' message, not raise."""
    system = WatchlistSystem(tmp_path / "never_built.sqlite", match_threshold=0.85)
    sanctions_msg = build_sanctions_check_tool(system).invoke({"name": "anyone"})
    country_msg = build_country_risk_tool(system).invoke({"country": "Iran"})
    for message in (sanctions_msg, country_msg):
        assert "watchlist store not ingested" in message
        assert "app.ingestion.watchlists.ingest" in message


def test_build_production_tools_names_and_order(tabular, watchlists):
    class FakeRag:
        def search(self, query, k=4):
            return []

    tools = build_production_tools(FakeRag(), tabular, watchlists)
    assert [t.name for t in tools] == [
        "query_accounts",
        "query_transactions",
        "sanctions_check",
        "country_risk",
        "search_aml_corpus",
    ]
