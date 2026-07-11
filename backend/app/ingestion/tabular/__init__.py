"""Tabular AML dataset ingestion — load the IBM/Kaggle "HI-Large" AML CSV/TXT files into
SQLite via SQLAlchemy ORM.

    >>> from app.ingestion.tabular import build_tabular_system, TabularDataType
    >>> tabular = build_tabular_system()
    >>> tabular.ingest(TabularDataType.ACCOUNTS, "HI-Large_accounts.csv")
    1000

Three source files map onto two tables: ``accounts`` and ``transactions`` (rows sourced
from the labeled patterns file reuse ``transactions`` with provenance columns — see
:mod:`app.ingestion.tabular.models`). Loaders stream rows so multi-million-row files never
load into memory at once; the service layer batches inserts. Swap the store by editing
:func:`build_tabular_system`.
"""

from __future__ import annotations

from .config import TabularConfig
from .loaders import count_rows, iter_accounts, iter_patterns, iter_transactions
from .models import Account, TabularDataType, Transaction
from .service import TabularSystem, build_tabular_system

__all__ = [
    "TabularConfig",
    "TabularDataType",
    "Account",
    "Transaction",
    "TabularSystem",
    "build_tabular_system",
    "iter_accounts",
    "iter_transactions",
    "iter_patterns",
    "count_rows",
]
