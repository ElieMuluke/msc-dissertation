"""SQLAlchemy ORM models for the tabular AML dataset (accounts + transactions).

Only two tables exist: ``accounts`` and ``transactions``. Rows sourced from the IBM-AML
"patterns" file reuse the ``transactions`` table (a pattern row *is* a transaction row
with extra provenance columns) rather than duplicating the schema (DRY).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by all tabular-ingestion ORM models."""


class TabularDataType(str, Enum):
    """Which of the three HI-Large source files/tables an upload targets.

    Used by the API layer to pick the loader/table for an uploaded file, and by the
    frontend to let the user select a data type before uploading.
    """

    ACCOUNTS = "accounts"
    TRANSACTIONS = "transactions"
    PATTERNS = "patterns"


class Account(Base):
    """One bank account, as listed in ``HI-Large_accounts.csv``.

    ``bank_id`` and ``account_number`` are free-form strings — they carry leading zeros
    in the transactions file and must never be cast to int. Unique on
    ``(bank_id, account_number)`` so re-ingesting the same accounts file is idempotent.
    """

    __tablename__ = "accounts"
    # Soft uniqueness only (not a cross-table FK target): accounts/transactions/patterns
    # can be ingested independently and in any order/partially, so referential integrity
    # across the three source files can't be guaranteed. Do not add real FK constraints.
    __table_args__ = (UniqueConstraint("bank_id", "account_number", name="uq_accounts_bank_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_name: Mapped[str] = mapped_column(String)
    bank_id: Mapped[str] = mapped_column(String, index=True)
    account_number: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[str] = mapped_column(String)
    entity_name: Mapped[str] = mapped_column(String)
    source_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Transaction(Base):
    """One transaction row, from either ``HI-Large_Trans.csv`` or ``HI-Large_Patterns.txt``.

    ``pattern_type``/``pattern_group_id`` are null for ordinary transactions and set for
    rows sourced from the labeled patterns file, tagging which laundering-pattern block
    (and its type) a row belongs to. No uniqueness constraint: legitimate duplicate
    transactions can occur, so ingestion is a plain bulk insert.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    # Soft relationships to Account.bank_id/account_number, deliberately NOT ForeignKey:
    # accounts/transactions/patterns files are ingested independently and in any order or
    # partially, so cross-file referential integrity can't be guaranteed. Indexed for joins
    # only. Do not add real FK constraints here.
    from_bank: Mapped[str] = mapped_column(String, index=True)
    from_account: Mapped[str] = mapped_column(String, index=True)
    to_bank: Mapped[str] = mapped_column(String, index=True)
    to_account: Mapped[str] = mapped_column(String, index=True)
    amount_received: Mapped[float] = mapped_column(Float)
    receiving_currency: Mapped[str] = mapped_column(String)
    amount_paid: Mapped[float] = mapped_column(Float)
    payment_currency: Mapped[str] = mapped_column(String)
    payment_format: Mapped[str] = mapped_column(String)
    # Ground-truth label ONLY (0/1) for evaluating an AML detection system after the
    # fact. This must NEVER be fed to the system as a detection input feature — doing
    # so is data leakage (the target leaking into its own predictors).
    is_laundering: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pattern_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    pattern_group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)
