"""Case-analysis endpoints (PRD-B §3-§6): run a pipeline over an account, stream agent
steps as SSE, persist an audit report, and serve report downloads plus the experiment
progress panel.

``POST /api/analysis`` streams (same SSE conventions as ``routes/tabular.py``):
``event: step`` frames (coarse stages from this route plus one ``tool_call`` step per
production tool invocation, captured at the tool boundary), an ``event: error`` frame
on failure, and one final ``event: done`` frame
(``{"decision", "rationale", "report_id", "pipeline"}``).

The agents themselves are the shared ``app.agents.single``/``app.agents.mas`` modules
behind the stateless ``arun(case, context)`` contract; this route constructs them per
request via ``app.agents.runner`` with the production tool set and rulebook injected.
Session memory lives here in the API layer (``app.api.session_memory``): prior-analysis
summaries are passed *into* the case as plain data and appended after the run — the
shared agent modules never gain state (PRD-B §5).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.tools import StructuredTool

from app.agents.contract import RunContext
from app.agents.production_tools import build_production_tools
from app.agents.runner import (
    PipelineUnavailableError,
    build_production_agent,
    default_model_name,
    force_final_answer,
    get_model_digest,
    needs_forced_final_answer,
    normalize_result,
    wrap_tools_with_trace,
)
from app.api.schemas import AnalysisRequest, ReportMeta
from app.api.session_memory import SessionMemory
from app.api.sse import sse_frame
from app.deps import (
    get_default_pipeline,
    get_rag,
    get_reports,
    get_rulebook,
    get_session_memory,
    get_tabular,
    get_watchlists,
)
from app.ingestion.rag import RagSystem
from app.ingestion.tabular import TabularSystem
from app.ingestion.watchlists import WatchlistSystem
from app.reports import AnalysisRecord, ReportSystem

router = APIRouter(prefix="/api", tags=["analysis"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

# backend/experiments/results/progress.json, written by the PRD-A runner after
# every run (experiments package relocated under backend/ on 2026-08-06).
_PROGRESS_PATH = Path(__file__).resolve().parents[3] / "experiments" / "results" / "progress.json"

_DONE = object()


def get_production_tools(
    rag: RagSystem = Depends(get_rag),
    tabular: TabularSystem = Depends(get_tabular),
    watchlists: WatchlistSystem = Depends(get_watchlists),
) -> list[StructuredTool]:
    """Assemble the production tool set for injection into the shared agent modules."""
    return build_production_tools(rag, tabular, watchlists)


@router.post("/analysis")
async def run_analysis(
    request: AnalysisRequest,
    tools: list[StructuredTool] = Depends(get_production_tools),
    rulebook: str = Depends(get_rulebook),
    reports: ReportSystem = Depends(get_reports),
    memory: SessionMemory = Depends(get_session_memory),
    default_pipeline: str = Depends(get_default_pipeline),
) -> StreamingResponse:
    """Analyse one account with the selected pipeline, streaming progress as SSE."""
    pipeline = request.pipeline or default_pipeline
    session_key = request.session_id or f"account:{request.account_id}"

    async def event_stream() -> AsyncIterator[str]:
        yield sse_frame("step", {"stage": "accepted", "pipeline": pipeline, "account_id": request.account_id})

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_tool_call(frame: dict) -> None:
            # Thread-safe: StructuredTool sync funcs run in worker threads under ainvoke.
            loop.call_soon_threadsafe(queue.put_nowait, {"stage": "tool_call", **frame})

        traced_tools, trace = wrap_tools_with_trace(tools, on_call=on_tool_call)
        try:
            agent = build_production_agent(pipeline, traced_tools, rulebook)
        except (PipelineUnavailableError, ValueError) as exc:
            yield sse_frame("error", {"message": str(exc)})
            return

        history = memory.history(session_key)
        case = {
            "account_id": request.account_id,
            "bank": request.bank,
            "session_notes": [
                f"{entry['created_at']}: {entry['decision']} ({entry['pipeline']}) — {entry['rationale']}"
                for entry in history
            ],
        }
        run_context = RunContext(
            run_id=uuid.uuid4().hex,
            case_id=request.account_id,
            seed=None,
            temperature=float(os.getenv("ANALYSIS_TEMPERATURE", "0.0")),
            metadata={"entry_point": "api", "session_key": session_key},
        )

        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        t0 = time.perf_counter()
        yield sse_frame("step", {"stage": "agent_started", "pipeline": pipeline})

        async def run_and_signal():
            try:
                return await agent.arun(case, run_context)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _DONE)

        task = asyncio.create_task(run_and_signal())
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            yield sse_frame("step", item)
        try:
            raw_result = await task
        except Exception as exc:  # noqa: BLE001 - surfaced to the client as an error frame
            yield sse_frame("error", {"message": f"Analysis failed: {exc}"})
            return
        # Production hardening (adapter layer, app.agents.runner): a run that exhausts
        # its tool budget mid-tool-call returns no final text → one tools-disabled
        # retry for the FINAL DECISION line, recorded in the trace as its own step.
        if needs_forced_final_answer(raw_result):
            yield sse_frame("step", {"stage": "forced_final_answer", "pipeline": pipeline})
            raw_result = await force_final_answer(
                raw_result, pipeline, rulebook, case, run_context, trace
            )
        try:
            # Digest from the analysis server (cached per process): the audit
            # report must pin the exact weights, not just the model tag.
            digest = await asyncio.to_thread(get_model_digest)
            result = normalize_result(
                raw_result, trace, model=default_model_name(), model_digest=digest
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the client as an error frame
            yield sse_frame("error", {"message": f"Analysis failed: {exc}"})
            return

        yield sse_frame("step", {"stage": "persisting_report"})
        record = AnalysisRecord(
            account_id=request.account_id,
            bank=request.bank,
            pipeline=pipeline,
            decision=result.decision,
            rationale=result.rationale,
            model=result.model,
            model_digest=result.model_digest,
            tool_calls=result.tool_calls,
            citations=result.citations,
            session_notes=list(case["session_notes"]),
            started_at=started,
            finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            wall_clock_s=round(time.perf_counter() - t0, 3),
        )
        row = await asyncio.to_thread(reports.persist, record)
        memory.append(
            session_key,
            {
                "report_id": row.id,
                "account_id": request.account_id,
                "pipeline": pipeline,
                "decision": result.decision,
                "rationale": result.rationale[:300],
                "created_at": row.created_at,
            },
        )
        yield sse_frame(
            "done",
            {
                "decision": result.decision,
                "rationale": result.rationale,
                "report_id": row.id,
                "pipeline": pipeline,
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/reports", response_model=list[ReportMeta])
def list_reports(reports: ReportSystem = Depends(get_reports)) -> list[ReportMeta]:
    """Most recent analysis reports, for the frontend's report list/history."""
    return [
        ReportMeta(
            id=row.id,
            created_at=row.created_at,
            account_id=row.account_id,
            bank=row.bank,
            pipeline=row.pipeline,
            decision=row.decision,
        )
        for row in reports.list()
    ]


@router.get("/reports/{report_id}")
def download_report(report_id: str, reports: ReportSystem = Depends(get_reports)) -> FileResponse:
    """Download one analysis report (markdown, with the full tool-call trace appendix)."""
    row = reports.get(report_id)
    if row is None or not Path(row.report_path).is_file():
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return FileResponse(
        row.report_path,
        media_type="text/markdown",
        filename=f"aml-analysis-{report_id}.md",
    )


@router.get("/experiment/progress")
def experiment_progress() -> dict:
    """Thin read of ``experiments/results/progress.json`` for the progress panel (PRD-B §6).

    ``{"available": false}`` until the PRD-A runner has written the file — the frontend
    renders that as "no sweep running" rather than an error.
    """
    if not _PROGRESS_PATH.is_file():
        return {"available": False}
    try:
        data = json.loads(_PROGRESS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False}
    return {"available": True, **data}
