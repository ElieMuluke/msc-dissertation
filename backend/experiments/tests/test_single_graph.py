"""Ported arm A (LangGraph): wire contract and loop semantics, no network.

The adversarial probe pattern: ``ollama.AsyncClient.chat`` is monkeypatched
to capture every wire payload ChatOllama actually sends and to script the
model's replies (including tool calls), so a full multi-turn run is driven
end-to-end through the real ChatOllama serialization path and the real
LangGraph loop — asserting the pinned parameters (think, seed, temperature,
num_ctx, num_predict) reach the wire on EVERY model call.
"""

from __future__ import annotations

import asyncio
from typing import Any

import ollama
import pytest

from app.agents.contract import RunContext
from app.agents.single import SingleAgent, build_tool_loop_graph, run_tool_loop
from experiments.config import DEFAULT_CONFIG
from experiments.harness.extraction import extract_decision
from experiments.harness.models import make_model_factory
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class _NameArgs(BaseModel):
    name: str = Field(...)


def _fake_tool(calls: list[dict]) -> StructuredTool:
    def check_sanctions_list(name: str) -> str:
        calls.append({"name": name})
        return f"{{'name': '{name}', 'is_sanctioned': True}}"

    return StructuredTool.from_function(
        func=check_sanctions_list,
        name="check_sanctions_list",
        description="Screen an entity name against sanctions lists.",
        args_schema=_NameArgs,
    )


def _response(content: str, tool_calls: list[dict] | None = None) -> dict[str, Any]:
    """One final (done) Ollama chat chunk in the wire shape ChatOllama parses."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "model": DEFAULT_CONFIG.model,
        "created_at": "2026-08-06T00:00:00Z",
        "done": True,
        "done_reason": "stop",
        "message": message,
        "prompt_eval_count": 100,
        "eval_count": 20,
    }


@pytest.fixture
def wire(monkeypatch):
    """Patch ollama.AsyncClient.chat: capture payloads, replay scripted responses."""
    payloads: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []

    async def fake_chat(self, **kwargs: Any):
        payloads.append(kwargs)
        resp = responses.pop(0)

        async def gen():
            yield resp

        return gen()

    monkeypatch.setattr(ollama.AsyncClient, "chat", fake_chat)
    return payloads, responses


def _context(run_id: str = "wire-test") -> RunContext:
    return RunContext(run_id=run_id, case_id="C1", seed=42, temperature=0.0)


def test_wire_contract_multi_turn_tool_run(wire) -> None:
    """Every model call of a multi-turn tool run carries the pinned params."""
    payloads, responses = wire
    responses += [
        _response(
            "",
            tool_calls=[{"function": {"name": "check_sanctions_list",
                                      "arguments": {"name": "Shadow Corp"}}}],
        ),
        _response("Evidence gathered.\nFINAL DECISION: escalate"),
    ]
    tool_executions: list[dict] = []
    agent = SingleAgent(
        model_factory=make_model_factory(DEFAULT_CONFIG, "single"),
        tools=[_fake_tool(tool_executions)],
        system_prompt="You are a compliance analyst.",
        render_case=lambda case: f"ALERT {case['alert_id']}",
        max_iterations=DEFAULT_CONFIG.max_iterations,
    )
    result = asyncio.run(agent.arun({"alert_id": "TXN-1"}, _context()))

    assert len(payloads) == 2  # one per model call, multi-turn
    for payload in payloads:
        assert payload["model"] == DEFAULT_CONFIG.model
        assert payload["think"] is False  # G0 contract on every call
        options = payload["options"]
        assert options["seed"] == 42
        assert options["temperature"] == 0.0
        assert options["num_ctx"] == DEFAULT_CONFIG.num_ctx
        assert options["num_predict"] == DEFAULT_CONFIG.num_predict
        # sampling params left to server defaults — never sent
        assert "top_p" not in options and "top_k" not in options
        assert payload["tools"], "tools must be bound on every call"

    # second call feeds the tool result back as a role=tool message
    second_roles = [m["role"] for m in payloads[1]["messages"]]
    assert second_roles == ["system", "user", "assistant", "tool"]
    assert "is_sanctioned" in payloads[1]["messages"][-1]["content"]

    assert tool_executions == [{"name": "Shadow Corp"}]
    assert [c.name for c in result.tool_calls] == ["check_sanctions_list"]
    assert result.agent_messages == 2
    assert result.prompt_tokens == 200 and result.completion_tokens == 40
    assert extract_decision(result.output_text) == "escalate"


def test_max_iterations_cap_is_graceful(wire) -> None:
    """Cap semantics preserved: N model calls max, last tools still executed,
    last text returned — no GraphRecursionError."""
    payloads, responses = wire
    max_iterations = 3
    responses += [
        _response(
            f"turn {i}",
            tool_calls=[{"function": {"name": "check_sanctions_list",
                                      "arguments": {"name": f"Entity {i}"}}}],
        )
        for i in range(max_iterations)
    ]
    tool_executions: list[dict] = []
    llm = make_model_factory(DEFAULT_CONFIG, "single")(_context())
    loop = asyncio.run(
        run_tool_loop(
            llm,
            [_fake_tool(tool_executions)],
            [SystemMessage(content="s"), HumanMessage(content="u")],
            max_iterations,
        )
    )
    assert len(payloads) == max_iterations  # not one more
    assert len(tool_executions) == max_iterations  # final call's tools ran too
    assert loop.agent_messages == max_iterations
    assert loop.output_text == f"turn {max_iterations - 1}"
    assert len(loop.tool_calls) == max_iterations


def test_unknown_tool_gets_error_result_and_is_recorded(wire) -> None:
    payloads, responses = wire
    responses += [
        _response("", tool_calls=[{"function": {"name": "nope", "arguments": {}}}]),
        _response("FINAL DECISION: investigate"),
    ]
    llm = make_model_factory(DEFAULT_CONFIG, "single")(_context())
    loop = asyncio.run(
        run_tool_loop(llm, [_fake_tool([])], [HumanMessage(content="u")], 4)
    )
    assert [c.name for c in loop.tool_calls] == ["nope"]
    assert payloads[1]["messages"][-1]["role"] == "tool"
    assert payloads[1]["messages"][-1]["content"] == "error: unknown tool 'nope'"
    assert extract_decision(loop.output_text) == "investigate"


def test_fresh_graph_per_invocation() -> None:
    """Statelessness: each loop invocation compiles its own graph object."""
    llm = make_model_factory(DEFAULT_CONFIG, "single")(_context())
    tool = _fake_tool([])
    g1 = build_tool_loop_graph(llm, [tool], 4)
    g2 = build_tool_loop_graph(llm, [tool], 4)
    assert g1 is not g2
