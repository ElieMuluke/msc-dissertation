"""Configuration for the tabular AML ingestion system.

A single immutable config object is injected into the system at build time so nothing
downstream hardcodes the database URL or batch size (Dependency Inversion).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TabularConfig:
    """Settings for building a :class:`TabularSystem`.

    Attributes:
        db_url: SQLAlchemy database URL for the SQLite store.
        batch_size: Number of rows per bulk-insert batch (streamed, chunked ingestion).
    """

    db_url: str = "sqlite:///./tabular_data_db.sqlite"
    batch_size: int = 2000
