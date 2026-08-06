"""Tests for analysis-report persistence and markdown rendering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.reports import AnalysisRecord, ReportConfig, build_report_system


@pytest.fixture
def reports(tmp_path):
    return build_report_system(ReportConfig(directory=tmp_path / "reports"))


def _record(**overrides) -> AnalysisRecord:
    base = dict(
        account_id="100428660",
        bank="070",
        pipeline="single",
        decision="escalate",
        rationale="Structuring pattern to a sanctioned counterparty.",
        model="qwen3.5:9b",
        model_digest="sha256:abc",
        tool_calls=[
            {"name": "query_transactions", "args": {"account_number": "100428660"}, "result": {"row_ids": [4, 5, 6]}},
            {"name": "sanctions_check", "args": {"name": "Nevada Spirit Company Limited"}, "result": "match"},
        ],
        citations=["JMLSG Part I, 5.7 (MON-2)", "FATF R.19 (EDD-1)"],
        started_at="2026-08-05T21:00:00+00:00",
        finished_at="2026-08-05T21:00:42+00:00",
        wall_clock_s=42.0,
    )
    base.update(overrides)
    return AnalysisRecord(**base)


def test_persist_writes_row_and_markdown_file(reports):
    row = reports.persist(_record())
    assert row.id and row.decision == "escalate"
    path = Path(row.report_path)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert f"# AML Analysis Report `{row.id}`" in text
    assert "**ESCALATE**" in text
    assert "full tool-call trace" in text
    assert "query_transactions" in text and "sanctions_check" in text
    assert "JMLSG Part I, 5.7 (MON-2)" in text
    # Trace round-trips through the index row too.
    assert json.loads(row.trace_json)[0]["name"] == "query_transactions"


def test_get_and_list(reports):
    first = reports.persist(_record(account_id="A1"))
    second = reports.persist(_record(account_id="A2", decision="dismiss"))

    fetched = reports.get(first.id)
    assert fetched is not None and fetched.account_id == "A1"
    assert reports.get("nope") is None

    listed = reports.list()
    assert {row.id for row in listed} == {first.id, second.id}


def test_render_handles_empty_trace_and_citations(reports):
    row = reports.persist(_record(tool_calls=[], citations=[], rationale=""))
    text = Path(row.report_path).read_text(encoding="utf-8")
    assert "0 tool call(s)" in text
    assert "no rulebook/corpus citations recorded" in text
    assert "_(none recorded)_" in text
    assert "this analysis ran without prior session context" in text


def test_session_notes_persisted_and_rendered(reports):
    """Injected session context is part of the agent's input — the audit
    report must reproduce it (goals-audit item 5)."""
    notes = [
        "2026-08-05T21:00:42+00:00: escalate (single) — structuring pattern.",
        "2026-08-06T09:12:00+00:00: investigate (mas) — new counterparty.",
    ]
    row = reports.persist(_record(session_notes=notes))
    assert json.loads(row.session_notes_json) == notes
    text = Path(row.report_path).read_text(encoding="utf-8")
    assert "session context provided to the agent" in text
    assert "2 prior-analysis summaries" in text
    for note in notes:
        assert note in text


def test_session_notes_column_migrates_existing_db(tmp_path):
    """An index created before the column existed must be migrated, not crash."""
    import sqlite3

    directory = tmp_path / "reports"
    directory.mkdir()
    db = directory / "reports.sqlite"
    with sqlite3.connect(db) as conn:  # legacy schema, no session_notes_json
        conn.execute(
            "CREATE TABLE analysis_reports (id VARCHAR PRIMARY KEY, created_at VARCHAR,"
            " account_id VARCHAR, bank VARCHAR, pipeline VARCHAR, model VARCHAR,"
            " model_digest VARCHAR, decision VARCHAR, rationale TEXT, trace_json TEXT,"
            " citations_json TEXT, started_at VARCHAR, finished_at VARCHAR,"
            " wall_clock_s FLOAT, report_path VARCHAR)"
        )
    system = build_report_system(ReportConfig(directory=directory))
    row = system.persist(_record(session_notes=["prior note"]))
    assert json.loads(row.session_notes_json) == ["prior note"]
