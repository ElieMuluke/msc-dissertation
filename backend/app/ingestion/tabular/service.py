"""Batched ingestion facade over the tabular AML store.

Loaders (:mod:`.loaders`) stream rows purely from a path or an already-open binary
file-like object; this module owns the only side effects — chunked bulk inserts and
commits — keeping a pure-core/thin-shell split.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from itertools import islice
from typing import IO, Optional, Union

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker

from .config import TabularConfig
from .loaders import iter_accounts, iter_patterns, iter_transactions, parse_csv_text
from .models import Account, TabularDataType, Transaction
from .store import build_engine, build_sessionmaker, init_db


def _batched(rows: Iterable[dict], size: int) -> Iterator[list[dict]]:
    """Chunk a (possibly huge, streamed) iterable of row dicts into lists of ``size``."""
    it = iter(rows)
    while batch := list(islice(it, size)):
        yield batch


# Commit every N batches rather than every batch. `on_batch` (progress reporting) still
# fires every batch — it's a cheap in-memory callback — but `commit()` triggers a disk
# fsync (see store.build_engine), so committing every 2000-row batch on a million-row file
# means tens of thousands of fsyncs. Committing every 25 batches (~50k rows at the default
# batch_size) cuts that by ~25x while still keeping crash-recovery granularity reasonable.
_COMMIT_EVERY_N_BATCHES = 25


class TabularSystem:
    """Ingest the three HI-Large AML source files into SQLite, batched and streamed."""

    def __init__(self, session_factory: sessionmaker, batch_size: int) -> None:
        self._session_factory = session_factory
        self._batch_size = batch_size
        # Lazily-populated, kept in sync by ingest/clear below. `counts()` is polled by the
        # frontend on every page load; at dataset scale (100M+ transaction rows) a fresh
        # `SELECT COUNT(*)` every time is slow enough to occasionally look like a failure.
        # One scan per process lifetime instead of one per request.
        self._counts_cache: Optional[dict[str, int]] = None

    def ingest_accounts(
        self,
        path: Union[str, IO[bytes]],
        source_file: Optional[str] = None,
        on_batch: Optional[Callable[[int], None]] = None,
    ) -> int:
        """Stream+bulk-insert ``HI-Large_accounts.csv``.

        ``path`` may be a filesystem path or an already-open binary file-like object (e.g.
        a ``ByteCountingReader`` the caller wraps for progress reporting — see
        ``app/api/routes/tabular.py``); both are accepted transparently by the underlying
        ``iter_accounts`` loader. Idempotent on ``(bank_id, account_number)``: re-ingesting
        the same file does not duplicate rows (``INSERT OR IGNORE``). Returns the number of
        rows newly inserted. ``on_batch``, if given, is called with the cumulative row count
        after each batch commits (e.g. for progress reporting).
        """
        rows = ({**row, "source_file": source_file} for row in iter_accounts(path))
        return self._insert_ignore_duplicates(Account, rows, ["bank_id", "account_number"], on_batch)

    def ingest_transactions(
        self,
        path: Union[str, IO[bytes]],
        source_file: Optional[str] = None,
        on_batch: Optional[Callable[[int], None]] = None,
    ) -> int:
        """Stream+bulk-insert ``HI-Large_Trans.csv`` (plain insert; duplicates allowed).

        ``path`` may be a filesystem path or an already-open binary file-like object (see
        :meth:`ingest_accounts`). Returns the number of rows inserted. ``on_batch``, if
        given, is called with the cumulative row count after each batch commits.
        """
        rows = ({**row, "source_file": source_file} for row in iter_transactions(path))
        return self._insert(Transaction, rows, on_batch)

    def ingest_patterns(
        self,
        path: Union[str, IO[bytes]],
        source_file: Optional[str] = None,
        on_batch: Optional[Callable[[int], None]] = None,
    ) -> int:
        """Stream+bulk-insert ``HI-Large_Patterns.txt`` into ``transactions`` with provenance.

        ``path`` may be a filesystem path or an already-open binary file-like object (see
        :meth:`ingest_accounts`). Returns the number of rows inserted. ``on_batch``, if
        given, is called with the cumulative row count after each batch commits.
        """
        rows = ({**row, "source_file": source_file} for row in iter_patterns(path))
        return self._insert(Transaction, rows, on_batch)

    def ingest(
        self,
        data_type: TabularDataType,
        path: Union[str, IO[bytes]],
        source_file: Optional[str] = None,
        on_batch: Optional[Callable[[int], None]] = None,
    ) -> int:
        """Dispatch to the right loader/table for ``data_type``.

        Lets the API route stay free of per-type branching. ``path`` may be a filesystem
        path or an already-open binary file-like object (see :meth:`ingest_accounts`).
        ``on_batch`` is threaded through to whichever of the three ingest methods is
        dispatched to.
        """
        dispatch = {
            TabularDataType.ACCOUNTS: self.ingest_accounts,
            TabularDataType.TRANSACTIONS: self.ingest_transactions,
            TabularDataType.PATTERNS: self.ingest_patterns,
        }
        return dispatch[data_type](path, source_file=source_file, on_batch=on_batch)

    def ingest_text(self, data_type: TabularDataType, text: str, source_file: Optional[str] = None) -> int:
        """Validate + bulk-insert pasted CSV/TXT ``text`` for ``data_type``, all-or-nothing.

        Unlike ``ingest_accounts``/``ingest_transactions``/``ingest_patterns`` (streamed,
        for on-disk files), ``text`` is fully parsed and validated by
        :func:`~.loaders.parse_csv_text` *before* any DB write is attempted: if it raises
        :class:`~.loaders.CsvValidationError`, nothing has been touched yet, so the error
        simply propagates. No ``on_batch`` progress callback — pasted text is small enough
        that this is a single, synchronous-feeling insert, unlike the streaming file paths.
        """
        rows = parse_csv_text(data_type, text)
        tagged_rows = [{**row, "source_file": source_file} for row in rows]
        if data_type is TabularDataType.ACCOUNTS:
            return self._insert_ignore_duplicates(Account, tagged_rows, ["bank_id", "account_number"])
        return self._insert(Transaction, tagged_rows)

    def counts(self) -> dict[str, int]:
        """Row counts per table, e.g. for a frontend ingested-volumes display.

        Cached after the first call (see ``__init__``) and kept in sync by ingest/``clear``,
        rather than re-running ``SELECT COUNT(*)`` on every call.
        """
        if self._counts_cache is None:
            with self._session_factory() as session:
                self._counts_cache = {
                    "accounts": session.scalar(select(func.count()).select_from(Account)) or 0,
                    "transactions": session.scalar(select(func.count()).select_from(Transaction)) or 0,
                }
        return dict(self._counts_cache)

    def clear(self) -> None:
        """Delete all rows from both tables (transactions first, then accounts)."""
        with self._session_factory() as session:
            session.execute(delete(Transaction))
            session.execute(delete(Account))
            session.commit()
        self._counts_cache = {"accounts": 0, "transactions": 0}

    def _insert(self, model: type, rows: Iterable[dict], on_batch: Optional[Callable[[int], None]] = None) -> int:
        inserted = 0
        with self._session_factory() as session:
            for i, batch in enumerate(_batched(rows, self._batch_size), start=1):
                session.execute(model.__table__.insert(), batch)
                inserted += len(batch)
                if i % _COMMIT_EVERY_N_BATCHES == 0:
                    session.commit()
                if on_batch is not None:
                    on_batch(inserted)
            session.commit()  # flush whatever remains since the last periodic commit
        self._bump_counts_cache(model, inserted)
        return inserted

    def _insert_ignore_duplicates(
        self,
        model: type,
        rows: Iterable[dict],
        conflict_columns: list[str],
        on_batch: Optional[Callable[[int], None]] = None,
    ) -> int:
        # "INSERT OR IGNORE" via executemany doesn't reliably report affected-row counts
        # across DBAPI/SQLAlchemy versions, so measure the delta in table size instead.
        count_stmt = select(func.count()).select_from(model)
        processed = 0
        with self._session_factory() as session:
            before = session.scalar(count_stmt) or 0
            for i, batch in enumerate(_batched(rows, self._batch_size), start=1):
                stmt = sqlite_insert(model).on_conflict_do_nothing(index_elements=conflict_columns)
                session.execute(stmt, batch)
                processed += len(batch)
                if i % _COMMIT_EVERY_N_BATCHES == 0:
                    session.commit()
                if on_batch is not None:
                    on_batch(processed)
            session.commit()  # flush whatever remains since the last periodic commit
            after = session.scalar(count_stmt) or 0
        delta = after - before
        self._bump_counts_cache(model, delta)
        return delta

    def _bump_counts_cache(self, model: type, delta: int) -> None:
        if self._counts_cache is not None:
            key = model.__tablename__
            self._counts_cache[key] = self._counts_cache.get(key, 0) + delta


def build_tabular_system(config: Optional[TabularConfig] = None) -> TabularSystem:
    """Wire an engine + sessionmaker into a ready :class:`TabularSystem` from a :class:`TabularConfig`.

    Ensures the schema exists (``init_db``) before returning, so callers never need to
    create tables themselves.
    """
    config = config or TabularConfig()
    engine = build_engine(config)
    init_db(engine)
    session_factory = build_sessionmaker(engine)
    return TabularSystem(session_factory, config.batch_size)
