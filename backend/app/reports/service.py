"""Persistence facade for analysis reports: SQLite index + rendered markdown files.

Mirrors ``ingestion.tabular.service``'s pure-core/thin-shell split: :mod:`.render` is
pure, this module owns the side effects (DB writes, file writes).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .config import ReportConfig
from .models import AnalysisReportRow, Base
from .render import render_markdown


@dataclass(frozen=True)
class AnalysisRecord:
    """Everything one completed analysis must persist (PRD-B §4)."""

    account_id: str
    pipeline: str
    decision: str
    rationale: str
    bank: Optional[str] = None
    model: Optional[str] = None
    model_digest: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    #: Prior-session summaries injected into the case (API session memory) —
    #: persisted so an external auditor can reconstruct the agent's full input.
    session_notes: list[str] = field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    wall_clock_s: Optional[float] = None


class ReportSystem:
    """Persist analyses and serve them back for download."""

    def __init__(self, session_factory: sessionmaker[Session], directory: Path) -> None:
        self._session_factory = session_factory
        self._directory = directory

    def persist(self, record: AnalysisRecord) -> AnalysisReportRow:
        """Write one analysis to the index and render its markdown report file.

        Returns the stored row (with generated ``id`` and ``report_path``).
        """
        report_id = uuid.uuid4().hex
        row = AnalysisReportRow(
            id=report_id,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            account_id=record.account_id,
            bank=record.bank,
            pipeline=record.pipeline,
            model=record.model,
            model_digest=record.model_digest,
            decision=record.decision,
            rationale=record.rationale,
            trace_json=json.dumps(record.tool_calls, ensure_ascii=False, default=str),
            citations_json=json.dumps(record.citations, ensure_ascii=False),
            session_notes_json=json.dumps(record.session_notes, ensure_ascii=False),
            started_at=record.started_at,
            finished_at=record.finished_at,
            wall_clock_s=record.wall_clock_s,
            report_path=str(self._directory / f"{report_id}.md"),
        )
        self._directory.mkdir(parents=True, exist_ok=True)
        Path(row.report_path).write_text(render_markdown(row), encoding="utf-8")
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
        return row

    def get(self, report_id: str) -> Optional[AnalysisReportRow]:
        """Fetch one report row by id (detached), or ``None``."""
        with self._session_factory() as session:
            row = session.get(AnalysisReportRow, report_id)
            if row is not None:
                session.expunge(row)
            return row

    def list(self, limit: int = 50) -> list[AnalysisReportRow]:
        """Most recent reports first (detached rows)."""
        stmt = select(AnalysisReportRow).order_by(AnalysisReportRow.created_at.desc()).limit(limit)
        with self._session_factory() as session:
            rows = list(session.scalars(stmt))
            for row in rows:
                session.expunge(row)
            return rows


def build_report_system(config: Optional[ReportConfig] = None) -> ReportSystem:
    """Wire an engine + sessionmaker into a ready :class:`ReportSystem`.

    Ensures the reports directory and schema exist, so callers never create either.
    """
    config = config or ReportConfig()
    config.directory.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config.resolved_db_url(), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    _migrate_columns(engine)
    return ReportSystem(sessionmaker(bind=engine), config.directory)


def _migrate_columns(engine) -> None:
    """Add columns introduced after first deployment (SQLite ``create_all`` never
    alters existing tables). Currently: ``session_notes_json`` (2026-08-06)."""
    if not engine.url.get_backend_name().startswith("sqlite"):
        return
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(analysis_reports)")}
        if cols and "session_notes_json" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE analysis_reports ADD COLUMN session_notes_json TEXT DEFAULT '[]'"
            )
            conn.commit()
