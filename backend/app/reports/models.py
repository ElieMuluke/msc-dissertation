"""SQLAlchemy ORM model for the analysis-report audit index.

One row per completed analysis (PRD-B §4): input, pipeline, model + digest, decision,
rationale, timestamps, and the full tool-call trace as JSON. The rendered markdown
report file sits next to the index under ``backend/data/reports/``.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for report-persistence models (separate DB from tabular)."""


class AnalysisReportRow(Base):
    """One persisted analysis: the audit-trail row an external audit firm reviews."""

    __tablename__ = "analysis_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid4 hex
    created_at: Mapped[str] = mapped_column(String, index=True)  # ISO-8601 UTC
    account_id: Mapped[str] = mapped_column(String, index=True)
    bank: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pipeline: Mapped[str] = mapped_column(String)  # "single" | "mas"
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_digest: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String, index=True)
    rationale: Mapped[str] = mapped_column(Text)
    # Full tool-call trace [{"name", "args", "result"}, ...] + rule citations, as JSON.
    trace_json: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    # Prior-session summaries injected into the case (JSON list of strings) —
    # part of the agent's input, so the audit report must reproduce them.
    session_notes_json: Mapped[str] = mapped_column(Text, default="[]")
    started_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    wall_clock_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    report_path: Mapped[str] = mapped_column(String)
