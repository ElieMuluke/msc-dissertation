"""Service-layer tests for TabularSystem, against an in-memory SQLite DB."""

from __future__ import annotations

from app.ingestion.tabular import TabularConfig, TabularDataType, build_tabular_system

ACCOUNTS_CSV = (
    "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\n"
    "Portugal Bank #500,240522,82655C500,2AA04EEC5D0,Corporation #82502\n"
    "Some Bank,00099,000C500,2AA04EEC5D1,Corporation #82503\n"
)

TRANSACTIONS_CSV = (
    "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,"
    "Amount Paid,Payment Currency,Payment Format,Is Laundering\n"
    "2022/08/01 00:17,020,800104D70,020,800104D70,6794.63,US Dollar,6794.63,US Dollar,Reinvestment,0\n"
    "2022/08/01 00:18,021,800104D71,022,800104D72,100.00,US Dollar,100.00,US Dollar,Cash,1\n"
)

PATTERNS_TXT = (
    "BEGIN LAUNDERING ATTEMPT - CYCLE\n"
    "2022/08/09 05:14,00952,8139F54E0,0111632,8062C56E0,5331.44,US Dollar,5331.44,US Dollar,ACH,1\n"
    "END LAUNDERING ATTEMPT - CYCLE\n"
)


def _system() -> "TabularSystem":  # noqa: F821 - forward ref for typing only
    return build_tabular_system(TabularConfig(db_url="sqlite:///:memory:"))


def test_ingest_accounts_counts_rows(tmp_path):
    tabular = _system()
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)

    ingested = tabular.ingest_accounts(str(path), source_file="accounts.csv")

    assert ingested == 2
    assert tabular.counts()["accounts"] == 2


def test_reingesting_same_accounts_file_does_not_duplicate(tmp_path):
    tabular = _system()
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)

    tabular.ingest_accounts(str(path), source_file="accounts.csv")
    second = tabular.ingest_accounts(str(path), source_file="accounts.csv")

    assert second == 0
    assert tabular.counts()["accounts"] == 2


def test_ingest_transactions_preserves_is_laundering_label(tmp_path):
    tabular = _system()
    path = tmp_path / "trans.csv"
    path.write_text(TRANSACTIONS_CSV)

    ingested = tabular.ingest_transactions(str(path), source_file="trans.csv")

    assert ingested == 2
    assert tabular.counts()["transactions"] == 2


def test_ingest_patterns_tags_pattern_type_and_group(tmp_path):
    tabular = _system()
    path = tmp_path / "patterns.txt"
    path.write_text(PATTERNS_TXT)

    ingested = tabular.ingest_patterns(str(path), source_file="patterns.txt")

    assert ingested == 1
    assert tabular.counts()["transactions"] == 1


def test_dispatcher_routes_by_data_type(tmp_path):
    tabular = _system()
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)

    ingested = tabular.ingest(TabularDataType.ACCOUNTS, str(path), source_file="accounts.csv")

    assert ingested == 2
    assert tabular.counts() == {"accounts": 2, "transactions": 0}


def test_clear_empties_both_tables(tmp_path):
    tabular = _system()
    accounts_path = tmp_path / "accounts.csv"
    accounts_path.write_text(ACCOUNTS_CSV)
    trans_path = tmp_path / "trans.csv"
    trans_path.write_text(TRANSACTIONS_CSV)
    tabular.ingest_accounts(str(accounts_path), source_file="accounts.csv")
    tabular.ingest_transactions(str(trans_path), source_file="trans.csv")

    tabular.clear()

    assert tabular.counts() == {"accounts": 0, "transactions": 0}


def test_on_batch_reports_cumulative_row_count(tmp_path):
    tabular = build_tabular_system(TabularConfig(db_url="sqlite:///:memory:", batch_size=1))
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)
    seen: list[int] = []

    ingested = tabular.ingest_accounts(str(path), source_file="accounts.csv", on_batch=seen.append)

    assert ingested == 2
    assert seen == [1, 2]
