"""Tests for the production adapter around the shared agent modules (app/agents/runner.py)."""

from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agents import mas as mas_module
from app.agents import single as single_module
from app.agents.contract import RunContext
from app.agents.runner import (
    FORCED_FINAL_STEP,
    PipelineUnavailableError,
    build_model_factory,
    build_production_agent,
    extract_citations,
    force_final_answer,
    needs_forced_final_answer,
    normalize_result,
    parse_decision,
    wrap_tools_with_trace,
)
from app.agents.contract import AgentResult, ToolCallRecord


def test_build_model_factory_parity_with_harness():
    """Production factory must match the measured wire config: thinking OFF
    (qwen3.5 thinks by default otherwise), same num_ctx/num_predict as the
    experiment harness; temperature/seed stay per-request."""
    context = RunContext(run_id="r", case_id="c", seed=7, temperature=0.3)
    llm = build_model_factory()(context)
    assert llm.reasoning is False
    assert llm.num_ctx == 16384
    assert llm.num_predict == 2048
    assert llm.temperature == 0.3
    assert llm.seed == 7


class EchoArgs(BaseModel):
    query: str = Field(...)


def make_echo_tool() -> StructuredTool:
    def echo(query: str) -> str:
        return f"echo:{query}"

    return StructuredTool.from_function(func=echo, name="echo", description="Echo.", args_schema=EchoArgs)


def test_parse_decision_last_match_wins_and_malformed():
    assert parse_decision("bla\nFINAL DECISION: escalate") == "escalate"
    assert parse_decision("contract says 'FINAL DECISION: dismiss'\n…\nFINAL DECISION: investigate") == "investigate"
    assert parse_decision("no verdict here") == "malformed"
    assert parse_decision("") == "malformed"


def test_wrap_tools_with_trace_records_calls_and_reports_live():
    live: list[dict] = []
    wrapped, trace = wrap_tools_with_trace([make_echo_tool()], on_call=live.append)
    result = wrapped[0].invoke({"query": "hi"})
    assert result == "echo:hi"
    assert trace == [{"name": "echo", "args": {"query": "hi"}, "result": "echo:hi"}]
    assert live == [{"tool": "echo"}]


def test_extract_citations_from_rag_trace():
    trace = [
        {
            "name": "search_aml_corpus",
            "args": {"query": "PEP"},
            "result": "[c1] (source=JMLSG Part I.pdf, page=112, score=0.81)\nsome text",
        },
        {"name": "query_accounts", "args": {}, "result": "{}"},
    ]
    assert extract_citations(trace) == ["JMLSG Part I.pdf, page 112 [c1]"]


def test_build_production_agent_uses_shared_modules():
    """PRD-B acceptance: harness and API import the same app.agents modules."""
    factory = lambda context: object()  # noqa: E731 - no LLM needed to construct
    tools = [make_echo_tool()]
    single_agent = build_production_agent("single", tools, "RULEBOOK", model_factory=factory)
    assert isinstance(single_agent, single_module.SingleAgent)
    mas_agent = build_production_agent("mas", tools, "RULEBOOK", model_factory=factory)
    assert isinstance(mas_agent, mas_module.MasAgent)
    with pytest.raises(ValueError, match="pipeline"):
        build_production_agent("triple", tools, "RULEBOOK", model_factory=factory)


class FakeChatModel:
    """Tools-disabled stand-in for ChatOllama: records messages, returns fixed text."""

    def __init__(self, reply: str):
        self.reply = reply
        self.seen_messages = None

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage

        self.seen_messages = messages
        return AIMessage(content=self.reply)


def test_needs_forced_final_answer_only_on_pending_tool_call_signature():
    pending = AgentResult(output_text="", tool_calls=(ToolCallRecord(name="echo"),))
    assert needs_forced_final_answer(pending)
    # Prose without the FINAL DECISION line is malformed but NOT retried (not a
    # pending tool call), and a parsable decision is never retried.
    assert not needs_forced_final_answer(
        AgentResult(output_text="some rationale", tool_calls=(ToolCallRecord(name="echo"),))
    )
    assert not needs_forced_final_answer(
        AgentResult(output_text="FINAL DECISION: dismiss", tool_calls=(ToolCallRecord(name="echo"),))
    )
    # No tool calls at all → an empty run, not a cut-off investigation.
    assert not needs_forced_final_answer(AgentResult(output_text=""))


def test_force_final_answer_retries_without_tools_and_records_trace_step():
    result = AgentResult(output_text="", tool_calls=(ToolCallRecord(name="echo"),), agent_messages=8)
    trace = [{"name": "echo", "args": {"query": "x"}, "result": "echo:" + "x" * 5000}]
    llm = FakeChatModel("Gap in data.\nFINAL DECISION: investigate")
    context = RunContext(run_id="r", case_id="c", seed=None, temperature=0.0)

    fixed = asyncio.run(
        force_final_answer(
            result, "single", "RULEBOOK", {"account_id": "80171BEE0"}, context, trace,
            model_factory=lambda _context: llm,
        )
    )

    assert parse_decision(fixed.output_text) == "investigate"
    assert fixed.agent_messages == 9
    # Recorded in the report trace as a distinct step, after the real tool calls.
    assert trace[-1]["name"] == FORCED_FINAL_STEP
    assert "FINAL DECISION: investigate" in trace[-1]["result"]
    # The retry prompt replays case + (truncated) evidence and demands the final line.
    rendered = "".join(str(m.content) for m in llm.seen_messages)
    assert "80171BEE0" in rendered
    assert "echo" in rendered and "x" * 5000 not in rendered  # evidence truncated
    assert "Provide your final rationale and FINAL DECISION line now." in rendered


def test_force_final_answer_model_failure_keeps_original_result():
    result = AgentResult(output_text="", tool_calls=(ToolCallRecord(name="echo"),))
    trace: list[dict] = []

    def broken_factory(_context):
        raise RuntimeError("model server down")

    context = RunContext(run_id="r", case_id="c", seed=None, temperature=0.0)
    fixed = asyncio.run(
        force_final_answer(
            result, "mas", "RULEBOOK", {"account_id": "A1"}, context, trace, model_factory=broken_factory
        )
    )

    assert fixed is result  # analysis proceeds; decision stays malformed
    assert trace[-1]["name"] == FORCED_FINAL_STEP
    assert trace[-1]["result"].startswith("error:")


def test_normalize_result_prefers_trace_and_parses_decision():
    result = AgentResult(
        output_text="Rationale…\nFINAL DECISION: escalate",
        tool_calls=(ToolCallRecord(name="echo", arguments={"query": "x"}),),
    )
    trace = [{"name": "echo", "args": {"query": "x"}, "result": "echo:x"}]
    normalized = normalize_result(result, trace, model="m", model_digest="sha256:d")
    assert normalized.decision == "escalate"
    assert normalized.tool_calls == trace
    assert normalized.model == "m" and normalized.model_digest == "sha256:d"


def test_normalize_result_falls_back_to_contract_records():
    result = AgentResult(
        output_text="FINAL DECISION: dismiss",
        tool_calls=(ToolCallRecord(name="echo", arguments={"query": "x"}),),
    )
    normalized = normalize_result(result, trace=None)
    assert normalized.decision == "dismiss"
    assert normalized.tool_calls == [{"name": "echo", "args": {"query": "x"}, "result": ""}]
    assert json.dumps(normalized.tool_calls)  # JSON-serialisable for persistence
