"""Analysis-report persistence: SQLite audit index + rendered markdown report files
under ``backend/data/reports/`` (PRD-B §4).

    >>> from app.reports import AnalysisRecord, build_report_system
    >>> reports = build_report_system()
    >>> row = reports.persist(AnalysisRecord(
    ...     account_id="100428660", pipeline="single",
    ...     decision="investigate", rationale="…",
    ... ))
    >>> row.report_path
    '.../data/reports/<id>.md'
"""

from __future__ import annotations

from .config import ReportConfig
from .models import AnalysisReportRow
from .render import render_markdown
from .service import AnalysisRecord, ReportSystem, build_report_system

__all__ = [
    "ReportConfig",
    "AnalysisReportRow",
    "AnalysisRecord",
    "ReportSystem",
    "build_report_system",
    "render_markdown",
]
