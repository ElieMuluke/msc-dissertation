"""Stream the three HI-Large AML source files into row dicts.

Pure generator functions: no DB session, no batching, no side effects beyond reading the
file. ``iter_accounts``/``iter_transactions`` stream via ``pandas.read_csv(chunksize=...)``
so multi-million-row "HI-Large" files never need to fit in memory at once; ``iter_patterns``
still reads line-by-line with the stdlib ``csv`` module (see its docstring for why). The
service layer owns batching + commits (pure core / thin shell).
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .models import TabularDataType

_TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M"

# Row count per pandas chunk for iter_accounts/iter_transactions. Not configurable (YAGNI);
# large enough to keep read_csv overhead low, small enough to bound peak memory.
_CHUNK_SIZE = 50_000


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


def iter_patterns(path: str) -> Iterator[dict]:
    """Yield one row dict per transaction line inside ``HI-Large_Patterns.txt``.

    Blocks are delimited by ``BEGIN LAUNDERING ATTEMPT - <TYPE>`` / ``END LAUNDERING
    ATTEMPT - <TYPE>`` marker lines (case-insensitive). A ``BEGIN`` line sets the current
    pattern type (the text after the last ``" - "``) and increments a running
    pattern-group counter; an ``END`` line is a no-op; every other non-blank line is a
    transaction row, parsed with the same positional logic as :func:`iter_transactions`
    and tagged with the current ``pattern_type``/``pattern_group_id``.
    """
    pattern_type: Optional[str] = None
    pattern_group_id: Optional[int] = None
    with Path(path).open(encoding="utf-8") as f:
        for raw_line in f:
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
