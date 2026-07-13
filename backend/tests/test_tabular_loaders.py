"""Unit tests for the pure tabular loaders (no DB, no network)."""

from __future__ import annotations

import io
from datetime import datetime

import pytest

from app.ingestion.tabular.loaders import (
    ByteCountingReader,
    CsvValidationError,
    iter_accounts,
    iter_patterns,
    iter_transactions,
    parse_csv_text,
)
from app.ingestion.tabular.models import TabularDataType

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
    # A row appearing before any BEGIN block has no current pattern (null tags).
    "2022/08/01 00:17,020,800104D70,020,800104D70,6794.63,US Dollar,6794.63,US Dollar,Reinvestment,0\n"
    "BEGIN LAUNDERING ATTEMPT - CYCLE\n"
    "2022/08/09 05:14,00952,8139F54E0,0111632,8062C56E0,5331.44,US Dollar,5331.44,US Dollar,ACH,1\n"
    "END LAUNDERING ATTEMPT - CYCLE\n"
)


def test_iter_accounts_preserves_leading_zero_strings(tmp_path):
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)

    rows = list(iter_accounts(str(path)))

    assert len(rows) == 2
    assert rows[0] == {
        "bank_name": "Portugal Bank #500",
        "bank_id": "240522",
        "account_number": "82655C500",
        "entity_id": "2AA04EEC5D0",
        "entity_name": "Corporation #82502",
    }
    # Leading zeros preserved as strings, never cast to int.
    assert rows[1]["bank_id"] == "00099"
    assert isinstance(rows[1]["bank_id"], str)


def test_iter_transactions_parses_positionally(tmp_path):
    path = tmp_path / "trans.csv"
    path.write_text(TRANSACTIONS_CSV)

    rows = list(iter_transactions(str(path)))

    assert len(rows) == 2
    first = rows[0]
    assert first["timestamp"] == datetime(2022, 8, 1, 0, 17)
    assert first["from_bank"] == "020"
    assert first["from_account"] == "800104D70"
    assert first["to_bank"] == "020"
    assert first["to_account"] == "800104D70"
    assert first["amount_received"] == 6794.63
    assert first["receiving_currency"] == "US Dollar"
    assert first["amount_paid"] == 6794.63
    assert first["payment_currency"] == "US Dollar"
    assert first["payment_format"] == "Reinvestment"
    assert first["is_laundering"] == 0
    assert first["pattern_type"] is None
    assert first["pattern_group_id"] is None
    assert rows[1]["is_laundering"] == 1


def test_iter_patterns_tags_block_rows_and_leaves_others_null(tmp_path):
    path = tmp_path / "patterns.txt"
    path.write_text(PATTERNS_TXT)

    rows = list(iter_patterns(str(path)))

    assert len(rows) == 2
    plain_row, pattern_row = rows

    # Row before any BEGIN block: no pattern tags.
    assert plain_row["pattern_type"] is None
    assert plain_row["pattern_group_id"] is None

    assert pattern_row["pattern_type"] == "CYCLE"
    assert pattern_row["pattern_group_id"] == 1
    assert pattern_row["from_bank"] == "00952"
    assert pattern_row["to_bank"] == "0111632"
    assert pattern_row["is_laundering"] == 1


def test_iter_accounts_accepts_binary_file_object(tmp_path):
    path = tmp_path / "accounts.csv"
    path.write_text(ACCOUNTS_CSV)

    with path.open("rb") as fh:
        reader = ByteCountingReader(fh)
        rows = list(iter_accounts(reader))

    assert len(rows) == 2
    assert reader.bytes_read == len(ACCOUNTS_CSV.encode())


def test_iter_patterns_accepts_binary_file_object_and_counts_bytes(tmp_path):
    path = tmp_path / "patterns.txt"
    path.write_text(PATTERNS_TXT)

    with path.open("rb") as fh:
        reader = ByteCountingReader(fh)
        rows = list(iter_patterns(reader))

    assert len(rows) == 2
    assert rows[1]["pattern_type"] == "CYCLE"
    assert reader.bytes_read == len(PATTERNS_TXT.encode())


def test_byte_counting_reader_delegates_unknown_attributes():
    raw = io.BytesIO(b"hello world")
    reader = ByteCountingReader(raw)

    assert reader.read(5) == b"hello"
    assert reader.bytes_read == 5
    assert reader.tell() == 5  # delegated to the wrapped BytesIO via __getattr__


def test_parse_csv_text_accounts_returns_rows():
    rows = parse_csv_text(TabularDataType.ACCOUNTS, ACCOUNTS_CSV)

    assert len(rows) == 2
    assert rows[0]["bank_name"] == "Portugal Bank #500"
    assert rows[1]["bank_id"] == "00099"


def test_parse_csv_text_transactions_returns_rows():
    rows = parse_csv_text(TabularDataType.TRANSACTIONS, TRANSACTIONS_CSV)

    assert len(rows) == 2
    assert rows[0]["timestamp"] == datetime(2022, 8, 1, 0, 17)
    assert rows[1]["is_laundering"] == 1


def test_parse_csv_text_patterns_returns_rows():
    rows = parse_csv_text(TabularDataType.PATTERNS, PATTERNS_TXT)

    assert len(rows) == 2
    assert rows[1]["pattern_type"] == "CYCLE"


def test_parse_csv_text_missing_column_raises_with_column_name():
    bad_csv = "Bank Name,Bank ID,Account Number,Entity ID\nA,1,2,3\n"

    with pytest.raises(CsvValidationError) as exc_info:
        parse_csv_text(TabularDataType.ACCOUNTS, bad_csv)

    assert "Entity Name" in str(exc_info.value)


def test_parse_csv_text_malformed_row_raises():
    bad_csv = (
        "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,"
        "Amount Paid,Payment Currency,Payment Format,Is Laundering\n"
        "not-a-timestamp,020,800104D70,020,800104D70,6794.63,US Dollar,6794.63,US Dollar,Reinvestment,0\n"
    )

    with pytest.raises(CsvValidationError):
        parse_csv_text(TabularDataType.TRANSACTIONS, bad_csv)


def test_parse_csv_text_empty_string_raises():
    with pytest.raises(CsvValidationError):
        parse_csv_text(TabularDataType.ACCOUNTS, "")
