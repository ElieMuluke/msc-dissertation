"""API tests for POST /api/analysis + report download, with the agent mocked.

No LLM inference happens here (GPU rule: sweep servers untouched; agent responses are
mocked). ``build_production_agent`` is monkeypatched with a fake honouring the shared
``arun(case, context) -> AgentResult`` contract, so these tests exercise the full
route: SSE streaming, tool tracing, report persistence and session memory.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

import app.api.routes.analysis as analysis_route
from app.agents.contract import AgentResult, RunContext
from app.agents.runner import PipelineUnavailableError
from app.api.session_memory import SessionMemory
from app.deps import get_reports, get_session_memory
from app.main import app
from app.reports import ReportConfig, build_report_system
from conftest import parse_sse_frames


class LookupArgs(BaseModel):
    account_number: str = Field(...)


def make_lookup_tool() -> StructuredTool:
    def query_accounts(account_number: str) -> str:
        return f"account {account_number}: 1 row"

    return StructuredTool.from_function(
        func=query_accounts, name="query_accounts", description="Lookup.", args_schema=LookupArgs
    )


class FakeAgent:
    """Stateless fake honouring the shared arun contract; calls its injected tools."""

    def __init__(self, pipeline: str, tools: list[StructuredTool]) -> None:
        self._pipeline = pipeline
        self._tools = tools

    async def arun(self, case, context: RunContext) -> AgentResult:
        for tool in self._tools:
            await tool.ainvoke({"account_number": case["account_id"]})
        notes = case.get("session_notes") or []
        return AgentResult(
            output_text=f"prior_analyses={len(notes)}\nFINAL DECISION: investigate",
        )


@pytest.fixture
def client(tmp_path, monkeypatch):
    reports = build_report_system(ReportConfig(directory=tmp_path / "reports"))
    memory = SessionMemory()
    app.dependency_overrides[get_reports] = lambda: reports
    app.dependency_overrides[get_session_memory] = lambda: memory
    app.dependency_overrides[analysis_route.get_production_tools] = lambda: [make_lookup_tool()]
    monkeypatch.setattr(
        analysis_route,
        "build_production_agent",
        lambda pipeline, tools, rulebook, model_factory=None: FakeAgent(pipeline, tools),
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _run_analysis(client, body):
    res = client.post("/api/analysis", json=body)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    return parse_sse_frames(res.text)


def test_analysis_streams_steps_and_done(client):
    frames = _run_analysis(client, {"account_id": "100428660", "bank": "070"})
    stages = [f["data"].get("stage") for f in frames if f["event"] == "step"]
    assert stages[0] == "accepted"
    assert "agent_started" in stages and "persisting_report" in stages
    # The traced tool boundary reports one live step per tool call.
    tool_steps = [f["data"] for f in frames if f["event"] == "step" and f["data"].get("stage") == "tool_call"]
    assert tool_steps == [{"stage": "tool_call", "tool": "query_accounts"}]
    done = frames[-1]
    assert done["event"] == "done"
    assert done["data"]["decision"] == "investigate"
    assert done["data"]["pipeline"] == "single"  # settings default
    assert done["data"]["report_id"]


def test_analysis_pipeline_override(client):
    frames = _run_analysis(client, {"account_id": "X", "pipeline": "mas"})
    assert frames[-1]["data"]["pipeline"] == "mas"


def test_analysis_report_is_persisted_and_downloadable(client):
    frames = _run_analysis(client, {"account_id": "100428660"})
    report_id = frames[-1]["data"]["report_id"]

    listed = client.get("/api/reports").json()
    assert listed[0]["id"] == report_id and listed[0]["decision"] == "investigate"

    res = client.get(f"/api/reports/{report_id}")
    assert res.status_code == 200
    text = res.text
    assert "full tool-call trace" in text
    # The trace appendix carries the tool call *with its result* (audit requirement).
    assert "query_accounts" in text and "account 100428660: 1 row" in text


def test_report_download_404(client):
    assert client.get("/api/reports/doesnotexist").status_code == 404


def test_session_memory_shared_across_consecutive_analyses(client):
    """PRD-B acceptance: two consecutive API analyses of one account share context,
    while the arun contract stays stateless (history arrives as case data)."""
    first = _run_analysis(client, {"account_id": "SAME"})
    assert "prior_analyses=0" in first[-1]["data"]["rationale"]
    second = _run_analysis(client, {"account_id": "SAME"})
    assert "prior_analyses=1" in second[-1]["data"]["rationale"]
    # A different account (different default session key) starts fresh.
    other = _run_analysis(client, {"account_id": "OTHER"})
    assert "prior_analyses=0" in other[-1]["data"]["rationale"]


def test_pipeline_unavailable_maps_to_error_frame(client, monkeypatch):
    def unavailable(pipeline, tools, rulebook, model_factory=None):
        raise PipelineUnavailableError("agent module not built yet")

    monkeypatch.setattr(analysis_route, "build_production_agent", unavailable)
    frames = _run_analysis(client, {"account_id": "X"})
    assert frames[-1]["event"] == "error"
    assert "not built yet" in frames[-1]["data"]["message"]


def test_agent_failure_maps_to_error_frame(client, monkeypatch):
    class BoomAgent:
        async def arun(self, case, context):
            raise RuntimeError("ollama exploded")

    monkeypatch.setattr(
        analysis_route,
        "build_production_agent",
        lambda pipeline, tools, rulebook, model_factory=None: BoomAgent(),
    )
    frames = _run_analysis(client, {"account_id": "X"})
    assert frames[-1]["event"] == "error"
    assert "ollama exploded" in frames[-1]["data"]["message"]


def test_experiment_progress_unavailable_then_available(client, monkeypatch, tmp_path):
    missing = tmp_path / "progress.json"
    monkeypatch.setattr(analysis_route, "_PROGRESS_PATH", missing)
    assert client.get("/api/experiment/progress").json() == {"available": False}

    missing.write_text(json.dumps({"done": 120, "total": 2300, "arms": {"single": 60, "mas": 60}}))
    payload = client.get("/api/experiment/progress").json()
    assert payload["available"] is True and payload["done"] == 120
