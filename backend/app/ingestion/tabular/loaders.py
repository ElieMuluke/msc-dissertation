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
from typing import IO, Optional, Union

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


class ByteCountingReader:
    """Wraps a binary file-like object, counting bytes consumed via ``.read()``.

    Lets the API routes (``app/api/routes/tabular.py``) derive an upload/ingest progress
    percentage from bytes actually read — a free byproduct of the read pandas/csv parsing
    already performs — instead of a separate full-file pass just to size a percentage (see
    the removed ``count_rows``, which this supersedes). Delegates every other attribute to
    the wrapped file object, so an instance is a transparent drop-in anywhere a binary
    file-like object is expected: ``pandas.read_csv`` accepts it directly (see
    :func:`iter_accounts`/:func:`iter_transactions`), and :func:`_iter_binary_lines` reads
    from it for the non-pandas ``PATTERNS`` ``.txt`` path (see :func:`iter_patterns`).
    """

    def __init__(self, fileobj: IO[bytes]) -> None:
        self._fileobj = fileobj
        self.bytes_read = 0

    def read(self, *args, **kwargs) -> bytes:
        chunk = self._fileobj.read(*args, **kwargs)
        self.bytes_read += len(chunk)
        return chunk

    # pandas' C parser prefers `read1` over `read` for real (fileno()-backed) file objects —
    # without this override, `__getattr__` would delegate `read1` straight to the wrapped
    # file, silently bypassing `read()` above and undercounting bytes (confirmed empirically:
    # a plain `__getattr__`-only delegate reports 0 bytes read against a real open file,
    # while it works fine against an `io.BytesIO`, which pandas drives via `.read()` instead).
    def read1(self, *args, **kwargs) -> bytes:
        return self.read(*args, **kwargs)

    def readable(self) -> bool:
        return True

    def __getattr__(self, name):
        return getattr(self._fileobj, name)


def _iter_binary_lines(reader: IO[bytes], encoding: str = "utf-8", chunk_size: int = 1 << 16) -> Iterator[str]:
    """Yield decoded text lines from a binary ``reader``, reading in fixed-size chunks.

    Used instead of ``io.TextIOWrapper`` so that a wrapping :class:`ByteCountingReader`'s
    ``.read()`` override actually gets invoked — ``TextIOWrapper`` calls lower-level buffer
    protocol methods (``read1``/``readinto``) that would silently bypass a plain ``.read()``
    override and undercount bytes.
    """
    buffer = b""
    while chunk := reader.read(chunk_size):
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line.decode(encoding)
    if buffer:
        yield buffer.decode(encoding)


def iter_accounts(source: Union[str, IO[bytes]]) -> Iterator[dict]:
    """Yield one row dict per line of ``HI-Large_accounts.csv``.

    Header: ``Bank Name, Bank ID, Account Number, Entity ID, Entity Name``. ``bank_id``
    and ``account_number`` are kept as strings (leading zeros must be preserved). ``source``
    may be a path or an already-open binary file-like object (e.g. a
    :class:`ByteCountingReader`) — ``pandas.read_csv`` accepts either transparently.
    """
    dtype = {"Bank ID": str, "Account Number": str, "Entity ID": str}
    for chunk in pd.read_csv(source, dtype=dtype, chunksize=_CHUNK_SIZE):
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


def iter_transactions(source: Union[str, IO[bytes]]) -> Iterator[dict]:
    """Yield one row dict per line of ``HI-Large_Trans.csv`` (real, unlabeled-by-pattern rows).

    ``pattern_type``/``pattern_group_id`` are always ``None`` here (they only apply to
    rows sourced from the patterns file). The header has two columns both literally named
    "Account"; pandas' C parser auto-dedupes the second occurrence to ``Account.1``, which
    we rely on instead of positional parsing. ``source`` may be a path or an already-open
    binary file-like object, same as :func:`iter_accounts`.
    """
    dtype = {"From Bank": str, "Account": str, "To Bank": str, "Account.1": str}
    for chunk in pd.read_csv(source, dtype=dtype, chunksize=_CHUNK_SIZE):
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


def iter_patterns(source: Union[str, IO[bytes]]) -> Iterator[dict]:
    """Yield one row dict per transaction line inside ``HI-Large_Patterns.txt``.

    Blocks are delimited by ``BEGIN LAUNDERING ATTEMPT - <TYPE>`` / ``END LAUNDERING
    ATTEMPT - <TYPE>`` marker lines (case-insensitive). A ``BEGIN`` line sets the current
    pattern type (the text after the last ``" - "``) and increments a running
    pattern-group counter; an ``END`` line is a no-op; every other non-blank line is a
    transaction row, parsed with the same positional logic as :func:`iter_transactions`
    and tagged with the current ``pattern_type``/``pattern_group_id``.

    ``source`` may be a path (opened here, text mode) or an already-open binary file-like
    object (e.g. a :class:`ByteCountingReader`), read line-by-line via
    :func:`_iter_binary_lines` — unlike :func:`iter_accounts`/:func:`iter_transactions`,
    this loader doesn't go through pandas, so it needs its own binary-source branch.
    """
    if isinstance(source, (str, Path)):
        with Path(source).open(encoding="utf-8") as f:
            yield from _iter_pattern_lines(f)
    else:
        yield from _iter_pattern_lines(_iter_binary_lines(source))


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
