"""Stream the three HI-Large AML source files into row dicts.

Pure generator functions: no DB session, no batching, no side effects beyond reading the
file. ``iter_accounts``/``iter_transactions`` stream via ``pandas.read_csv(chunksize=...)``
so multi-million-row "HI-Large" files never need to fit in memory at once; ``iter_patterns``
still reads line-by-line with the stdlib ``csv`` module (see its docstring for why). The
service layer owns batching + commits (pure core / thin shell).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .models import TabularDataType

_TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M"

# Row count per pandas chunk for iter_accounts/iter_transactions. Not configurable (YAGNI);
# large enough to keep read_csv overhead low, small enough to bound peak memory.
_CHUNK_SIZE = 50_000

# Header columns iter_accounts/iter_transactions require, used by parse_csv_text to
# validate pasted CSV text up front (before any DB write). Keep in sync with the
# row-dict keys those two generators read.
_EXPECTED_HEADERS: dict[TabularDataType, tuple[str, ...]] = {
    TabularDataType.ACCOUNTS: ("Bank Name", "Bank ID", "Account Number", "Entity ID", "Entity Name"),
    TabularDataType.TRANSACTIONS: (
        "Timestamp",
        "From Bank",
        "Account",
        "To Bank",
        "Account.1",
        "Amount Received",
        "Receiving Currency",
        "Amount Paid",
        "Payment Currency",
        "Payment Format",
        "Is Laundering",
    ),
}


class CsvValidationError(Exception):
    """Raised when pasted CSV text fails validation before any DB write is attempted.

    Carries every problem found (not just the first) as ``errors``, so a caller (e.g. the
    API layer) can surface all of them at once instead of round-tripping error-by-error.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def iter_accounts(path: str) -> Iterator[dict]:
    """Yield one row dict per line of ``HI-Large_accounts.csv``.

    Header: ``Bank Name, Bank ID, Account Number, Entity ID, Entity Name``. ``bank_id``
    and ``account_number`` are kept as strings (leading zeros must be preserved).
    """
    dtype = {"Bank ID": str, "Account Number": str, "Entity ID": str}
    for chunk in pd.read_csv(path, dtype=dtype, chunksize=_CHUNK_SIZE):
        for row in chunk.to_dict("records"):
            yield {
                "bank_name": row["Bank Name"],
                "bank_id": row["Bank ID"],
                "account_number": row["Account Number"],
                "entity_id": row["Entity ID"],
                "entity_name": row["Entity Name"],
            }


def _parse_transaction_fields(fields: list[str]) -> dict:
    """Parse one 11-field positional transaction row (shared by transactions + patterns).

    Fields, in order: Timestamp, From Bank, Account (from), To Bank, Account (to),
    Amount Received, Receiving Currency, Amount Paid, Payment Currency, Payment Format,
    Is Laundering. Parsed positionally (not ``csv.DictReader``) because the header has
    two columns both literally named "Account".
    """
    (
        timestamp,
        from_bank,
        from_account,
        to_bank,
        to_account,
        amount_received,
        receiving_currency,
        amount_paid,
        payment_currency,
        payment_format,
        is_laundering,
    ) = fields
    return {
        "timestamp": datetime.strptime(timestamp, _TIMESTAMP_FORMAT),
        "from_bank": from_bank,
        "from_account": from_account,
        "to_bank": to_bank,
        "to_account": to_account,
        "amount_received": float(amount_received),
        "receiving_currency": receiving_currency,
        "amount_paid": float(amount_paid),
        "payment_currency": payment_currency,
        "payment_format": payment_format,
        "is_laundering": int(is_laundering),
    }


def iter_transactions(path: str) -> Iterator[dict]:
    """Yield one row dict per line of ``HI-Large_Trans.csv`` (real, unlabeled-by-pattern rows).

    ``pattern_type``/``pattern_group_id`` are always ``None`` here (they only apply to
    rows sourced from the patterns file). The header has two columns both literally named
    "Account"; pandas' C parser auto-dedupes the second occurrence to ``Account.1``, which
    we rely on instead of positional parsing.
    """
    dtype = {"From Bank": str, "Account": str, "To Bank": str, "Account.1": str}
    for chunk in pd.read_csv(path, dtype=dtype, chunksize=_CHUNK_SIZE):
        chunk["Timestamp"] = pd.to_datetime(chunk["Timestamp"], format=_TIMESTAMP_FORMAT)
        for row in chunk.to_dict("records"):
            yield {
                "timestamp": row["Timestamp"].to_pydatetime(),
                "from_bank": row["From Bank"],
                "from_account": row["Account"],
                "to_bank": row["To Bank"],
                "to_account": row["Account.1"],
                "amount_received": float(row["Amount Received"]),
                "receiving_currency": row["Receiving Currency"],
                "amount_paid": float(row["Amount Paid"]),
                "payment_currency": row["Payment Currency"],
                "payment_format": row["Payment Format"],
                "is_laundering": int(row["Is Laundering"]),
                "pattern_type": None,
                "pattern_group_id": None,
            }


def _iter_pattern_lines(lines: Iterable[str]) -> Iterator[dict]:
    """Yield one row dict per transaction line among ``lines`` (the parsing core of :func:`iter_patterns`).

    Split out from :func:`iter_patterns` so :func:`parse_csv_text` can run the exact same
    block-tracking/parsing logic over ``text.splitlines()`` (pasted text) with zero
    duplicated logic. See :func:`iter_patterns` for the block-marker semantics.
    """
    pattern_type: Optional[str] = None
    pattern_group_id: Optional[int] = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("BEGIN"):
            pattern_group_id = (pattern_group_id or 0) + 1
            pattern_type = line.rsplit(" - ", 1)[-1].strip()
            continue
        if line.upper().startswith("END"):
            continue
        fields = next(csv.reader([line]))
        row = _parse_transaction_fields(fields)
        row["pattern_type"] = pattern_type
        row["pattern_group_id"] = pattern_group_id
        yield row


def iter_patterns(path: str) -> Iterator[dict]:
    """Yield one row dict per transaction line inside ``HI-Large_Patterns.txt``.

    Blocks are delimited by ``BEGIN LAUNDERING ATTEMPT - <TYPE>`` / ``END LAUNDERING
    ATTEMPT - <TYPE>`` marker lines (case-insensitive). A ``BEGIN`` line sets the current
    pattern type (the text after the last ``" - "``) and increments a running
    pattern-group counter; an ``END`` line is a no-op; every other non-blank line is a
    transaction row, parsed with the same positional logic as :func:`iter_transactions`
    and tagged with the current ``pattern_type``/``pattern_group_id``.
    """
    with Path(path).open(encoding="utf-8") as f:
        yield from _iter_pattern_lines(f)


def parse_csv_text(data_type: TabularDataType, text: str) -> list[dict]:
    """Validate + fully parse pasted CSV/TXT ``text`` for ``data_type``, all-or-nothing.

    Unlike the streaming ``iter_*`` generators (meant for on-disk, possibly huge files),
    this materializes the full row list up front so a caller (``TabularSystem.ingest_text``)
    can guarantee no partial DB writes: if anything is malformed, :class:`CsvValidationError`
    is raised before a single row is returned, and nothing has been inserted.

    For ``ACCOUNTS``/``TRANSACTIONS``, the header is checked first (missing expected
    columns fail fast with a clear message); rows are then parsed with the same
    ``iter_accounts``/``iter_transactions`` logic via an in-memory ``StringIO``. For
    ``PATTERNS``, rows are parsed with :func:`_iter_pattern_lines` over ``text.splitlines()``.
    Any parse failure (bad float, bad timestamp, bad int, ...) is caught and re-raised as
    a :class:`CsvValidationError` instead of propagating a raw exception.
    """
    if not text.strip():
        raise CsvValidationError(["CSV text is empty."])

    if data_type is TabularDataType.PATTERNS:
        try:
            rows = list(_iter_pattern_lines(text.splitlines()))
        except Exception as exc:
            raise CsvValidationError([str(exc)]) from exc
    else:
        expected = _EXPECTED_HEADERS[data_type]
        header = pd.read_csv(io.StringIO(text), nrows=0).columns.tolist()
        missing = [column for column in expected if column not in header]
        if missing:
            raise CsvValidationError(
                [f"Missing required column(s) for {data_type.value}: {', '.join(missing)}"]
            )
        loader = iter_accounts if data_type is TabularDataType.ACCOUNTS else iter_transactions
        try:
            rows = list(loader(io.StringIO(text)))
        except Exception as exc:
            raise CsvValidationError([str(exc)]) from exc

    if not rows:
        raise CsvValidationError(["No data rows found."])
    return rows


def count_rows(path: str, data_type: TabularDataType) -> int:
    """Fast, non-pandas count of the data rows a matching ``iter_*`` would yield.

    Used only for progress-bar percentages (e.g. the WebSocket ingestion progress in
    ``app/api/routes/tabular.py``), so it deliberately skips parsing/type-conversion and
    just counts lines. For ``ACCOUNTS``/``TRANSACTIONS`` (plain CSV with a header): total
    lines minus one. For ``PATTERNS``: non-blank lines that aren't ``BEGIN``/``END``
    marker lines (case-insensitive), matching what :func:`iter_patterns` yields.
    """
    if data_type is TabularDataType.PATTERNS:
        with Path(path).open(encoding="utf-8") as f:
            return sum(
                1
                for raw_line in f
                if (line := raw_line.strip()) and not line.upper().startswith(("BEGIN", "END"))
            )
    with Path(path).open(newline="", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1
