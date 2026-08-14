"""Adversarial probe 2 — response-parsing attack (C4). ZERO network/GPU/LLM.

Feeds synthetic /api/chat responses through the REAL pipeline
(ChatOllama parsing -> run_tool_loop recording -> journal-shaped fields)
via a class-level monkeypatch of ollama.AsyncClient.chat.

Question under attack: does harness v2's "strict" path silently DROP tool
calls that Ollama would have surfaced, making journalled "zero tool calls"
a parsing artifact?

Scenarios (each = one scripted first response, then a plain final answer):
  A  native message.tool_calls, dict arguments            (the normal path)
  B  native tool_calls, arguments as JSON string          (ollama #6155 shape)
  C  native tool_calls, arguments malformed (not JSON)    -> visible error?
  D  native tool_calls, UNKNOWN tool name                 (hallucinated tool)
  E  tool call as raw JSON in message.content only        (template-less emit)
  F  tool call as <tool_call> XML in content only
  G  deepseek-style: thinking channel + prose content, no tool_calls
  H  truncation: done_reason=length, empty content, no tool_calls
  I  native tool_calls present in a NON-final stream chunk (done=False)

Run from backend/ with PYTHONPATH=.:
  ./.venv/bin/python experiments/analysis/adv_probe_parsing.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import ollama
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.single import run_tool_loop
from experiments.config import config_for_model
from experiments.harness.dfah_tools import build_dfah_tools
from experiments.harness.models import make_model_factory
from app.agents.contract import RunContext

_REAL_CHAT = ollama.AsyncClient.chat
SCRIPT: list[list[dict[str, Any]]] = []  # per-call chunk lists, consumed FIFO


def _chunk(content: str = "", tool_calls: list | None = None,
           thinking: str | None = None, done_reason: str = "stop",
           done: bool = True) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    if thinking is not None:
        msg["thinking"] = thinking
    return {
        "model": "probe", "created_at": "2026-08-14T00:00:00Z",
        "done": done, "done_reason": done_reason if done else None,
        "prompt_eval_count": 100, "eval_count": 50, "message": msg,
    }


async def _fake_chat(self, **kwargs: Any):  # noqa: ANN001
    chunks = SCRIPT.pop(0) if SCRIPT else [_chunk("FINAL DECISION: investigate")]
    if kwargs.get("stream", False):
        async def gen():
            for c in chunks:
                yield c
        return gen()
    return chunks[-1]


FINAL = [_chunk("FINAL DECISION: investigate")]

SCENARIOS: dict[str, list[list[dict[str, Any]]]] = {
    "A_native_dict_args": [
        [_chunk(tool_calls=[{"function": {"name": "check_sanctions_list",
                                          "arguments": {"name": "ABC Corp"}}}])],
        FINAL,
    ],
    "B_native_json_string_args": [
        [_chunk(tool_calls=[{"function": {"name": "check_sanctions_list",
                                          "arguments": '{"name": "ABC Corp"}'}}])],
        FINAL,
    ],
    "C_native_malformed_args": [
        [_chunk(tool_calls=[{"function": {"name": "check_sanctions_list",
                                          "arguments": "name := ABC Corp ;;"}}])],
        FINAL,
    ],
    "D_native_unknown_tool": [
        [_chunk(tool_calls=[{"function": {"name": "decision_rulebook",
                                          "arguments": {"q": "x"}}}])],
        FINAL,
    ],
    "E_json_in_content": [
        [_chunk('{"name": "check_sanctions_list", "arguments": {"name": "ABC Corp"}}')],
        FINAL,
    ],
    "F_xml_in_content": [
        [_chunk('<tool_call>{"name": "check_sanctions_list", '
                '"arguments": {"name": "ABC Corp"}}</tool_call>')],
        FINAL,
    ],
    "G_deepseek_prose": [
        [_chunk("The alert involves ABC Corp. FINAL DECISION: dismiss",
                thinking="Okay, so I need to assess...")],
    ],
    "H_truncation_length": [
        [_chunk("", done_reason="length")],
    ],
    "I_tool_calls_nonfinal_chunk": [
        [
            _chunk(tool_calls=[{"function": {"name": "check_sanctions_list",
                                             "arguments": {"name": "ABC Corp"}}}],
                   done=False),
            _chunk("", done_reason="stop"),
        ],
        FINAL,
    ],
}


async def main() -> int:
    config = config_for_model("deepseek-r1:14b@think")  # think=True path
    factory = make_model_factory(config, "single")
    context = RunContext(run_id="adv-parse", case_id="probe", seed=42,
                         temperature=0.0)
    tools = build_dfah_tools()
    messages = [SystemMessage(content="probe system"),
                HumanMessage(content="probe case")]

    ollama.AsyncClient.chat = _fake_chat  # type: ignore[method-assign]
    results: dict[str, Any] = {}
    try:
        for name, script in SCENARIOS.items():
            SCRIPT.clear()
            SCRIPT.extend([list(c) for c in script])
            llm = factory(context)
            try:
                loop = await run_tool_loop(llm, tools, messages, max_iterations=8)
                results[name] = {
                    "journalled_tool_calls": [c.name for c in loop.tool_calls],
                    "tool_args": [c.arguments for c in loop.tool_calls],
                    "output_text_head": loop.output_text[:90],
                    "agent_messages": loop.agent_messages,
                    "error": None,
                }
            except Exception as exc:  # what execute_run would journal as error
                results[name] = {
                    "journalled_tool_calls": [],
                    "error": f"{type(exc).__name__}: {str(exc)[:140]}",
                }
    finally:
        ollama.AsyncClient.chat = _REAL_CHAT  # type: ignore[method-assign]

    for name, r in results.items():
        print(f"{name:<30} tool_calls={r['journalled_tool_calls']} "
              f"error={r.get('error')!s:.80}")
        if r.get("output_text_head") is not None:
            print(f"{'':<30} text_head={r['output_text_head']!r}")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'tool_args'}
                      for k, v in results.items()}, indent=1)[:0] or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
