"""Configuration for analysis-report persistence.

A single immutable config object is injected at build time (Dependency Inversion,
mirroring ``ingestion.tabular.config``): the SQLite index and the rendered report files
both live under ``backend/data/reports/`` (PRD-B §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"


@dataclass(frozen=True)
class ReportConfig:
    """Settings for building a :class:`ReportSystem`.

    Attributes:
        directory: Directory for rendered report files (``{report_id}.md``) and the
            SQLite index (``reports.sqlite``) unless ``db_url`` overrides it.
        db_url: SQLAlchemy URL for the report index; empty string means
            ``sqlite:///<directory>/reports.sqlite`` resolved at build time.
    """

    directory: Path = field(default=_DEFAULT_DIR)
    db_url: str = ""

    def resolved_db_url(self) -> str:
        """The effective database URL (defaulting into ``directory``)."""
        return self.db_url or f"sqlite:///{self.directory / 'reports.sqlite'}"
