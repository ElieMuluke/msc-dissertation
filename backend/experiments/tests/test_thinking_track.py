"""Thinking-on track: the ``think=True`` wire path and the INVERTED
mini-gate criterion (pre-registered, CHANGELOG 2026-08-11 evening).

Two things are asserted here and nowhere else:

1. ``ExperimentConfig.think=True`` reaches the wire as ``think: true`` on
   EVERY model call, and the reasoning the server returns on the separate
   ``message.thinking`` channel stays OUT of ``AgentResult.output_text`` —
   so extraction and every downstream metric still see the answer only.
2. The think probe's pass rule inverts for this track: reasoning must be
   PRESENT on the separate channel and ABSENT (as markup) from content. A
   model that inlines its reasoning fails, which is the whole point.

No network: ``ollama.AsyncClient.chat`` and ``mini_gates._chat`` are
monkeypatched.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import ollama
import pytest

from app.agents.contract import RunContext
from app.agents.single import SingleAgent
from experiments.config import DEFAULT_CONFIG, config_for_model
from experiments.harness import mini_gates
from experiments.harness.extraction import extract_decision
from experiments.harness.models import make_model_factory
from experiments.tests.test_single_graph import _fake_tool, wire  # noqa: F401

THINK_ON = dataclasses.replace(DEFAULT_CONFIG, think=True)
THINK_OFF = dataclasses.replace(DEFAULT_CONFIG, think=False)
THINK_OMIT = dataclasses.replace(DEFAULT_CONFIG, think=None)


def _response(
    content: str, thinking: str | None = None, tool_calls: list[dict] | None = None
) -> dict[str, Any]:
    """One done Ollama chat chunk, optionally carrying a thinking channel."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if thinking is not None:
        message["thinking"] = thinking
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "model": DEFAULT_CONFIG.model,
        "created_at": "2026-08-11T00:00:00Z",
        "done": True,
        "done_reason": "stop",
        "message": message,
        "prompt_eval_count": 100,
        "eval_count": 900,
    }


def _context() -> RunContext:
    return RunContext(run_id="think-test", case_id="C1", seed=42, temperature=0.0)


# --- 1. the think=True wire path --------------------------------------------


def test_think_true_reaches_the_wire_on_every_call(wire) -> None:  # noqa: F811
    """think: true on every model call of a multi-turn tool run, and the
    reasoning channel never contaminates output_text."""
    payloads, responses = wire
    responses += [
        _response(
            "",
            thinking="Let me screen the counterparty first.",
            tool_calls=[{"function": {"name": "check_sanctions_list",
                                      "arguments": {"name": "Shadow Corp"}}}],
        ),
        _response(
            "Evidence gathered.\nFINAL DECISION: escalate",
            thinking="Sanctioned entity, so this must go up.",
        ),
    ]
    agent = SingleAgent(
        model_factory=make_model_factory(THINK_ON, "single"),
        tools=[_fake_tool([])],
        system_prompt="You are a compliance analyst.",
        render_case=lambda case: f"ALERT {case['alert_id']}",
        max_iterations=THINK_ON.max_iterations,
    )
    result = asyncio.run(agent.arun({"alert_id": "TXN-1"}, _context()))

    assert len(payloads) == 2
    for payload in payloads:
        assert payload["think"] is True  # the manipulation, on every call
        assert payload["options"]["seed"] == 42
        assert payload["options"]["num_predict"] == THINK_ON.num_predict

    # The answer channel only: reasoning is not concatenated into the output,
    # so extraction and every metric are computed on the answer as before.
    assert result.output_text == "Evidence gathered.\nFINAL DECISION: escalate"
    assert "must go up" not in result.output_text
    assert not mini_gates.has_inline_reasoning(result.output_text)
    assert extract_decision(result.output_text) == "escalate"

    # Turn 2 replays turn 1's reasoning back to the model on its own field —
    # that continuity IS the deliberation the track manipulates.
    assistant = [m for m in payloads[1]["messages"] if m["role"] == "assistant"]
    assert assistant[0]["thinking"] == "Let me screen the counterparty first."


@pytest.mark.parametrize(
    "config,expected", [(THINK_ON, True), (THINK_OFF, False), (THINK_OMIT, None)]
)
def test_factory_maps_all_three_think_states(wire, config, expected) -> None:  # noqa: F811
    """The tri-state reaches ChatOllama's ``reasoning`` unchanged; the real
    ollama client drops it when None (exclude_none)."""
    payloads, responses = wire
    responses.append(_response("FINAL DECISION: dismiss"))
    llm = make_model_factory(config, "single")(_context())
    assert llm.reasoning is expected
    asyncio.run(llm.ainvoke("hello"))
    assert payloads[0]["think"] is expected


# --- 2. the inverted gate criterion -----------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("<think>reasoning</think> answer", True),
        ("</think>answer", True),
        ("<THINK>shouty</THINK>", True),
        ("<thinking>x</thinking>", True),
        ("<reasoning>x</reasoning>", True),
        ("<|channel|>analysis<|message|>x", True),  # gpt-oss harmony
        ("◁think▷x◁/think▷", True),
        ("[THINK] x [/THINK]", True),
        ("FINAL DECISION: escalate", False),
        ("I think this is suspicious.", False),  # prose, not markup
        ("", False),
        (None, False),
    ],
)
def test_has_inline_reasoning(text, expected) -> None:
    assert mini_gates.has_inline_reasoning(text) is expected


def test_expects_thinking_infers_track_from_config() -> None:
    assert mini_gates.expects_thinking(THINK_ON) is True
    assert mini_gates.expects_thinking(THINK_OFF) is False
    assert mini_gates.expects_thinking(THINK_OMIT) is False
    assert mini_gates.expects_thinking(config_for_model("qwen3.5:9b@think")) is True
    assert mini_gates.expects_thinking(config_for_model("qwen3.5:9b")) is False


def _record(**kwargs: Any) -> dict[str, Any]:
    base = {
        "http_ok": True,
        "thinking_field_present": False,
        "thinking_nonempty": False,
        "inline_think_tags": False,
        "content_nonempty": True,
    }
    return {**base, **kwargs}


@pytest.mark.parametrize(
    "record,expect_thinking,verdict,why",
    [
        # thinking ON: separate channel required, inline markup forbidden
        (_record(thinking_field_present=True, thinking_nonempty=True), True, True,
         "reasoning on the separate channel, clean content"),
        (_record(inline_think_tags=True), True, False,
         "inlined reasoning into content — contaminates the measured output"),
        (_record(thinking_field_present=True, thinking_nonempty=True,
                 inline_think_tags=True), True, False,
         "both channels — content is still contaminated"),
        (_record(), True, False, "no reasoning at all: think:true had no effect"),
        (_record(thinking_field_present=True, thinking_nonempty=False), True, False,
         "thinking field present but empty is not reasoning"),
        (_record(http_ok=False), True, False, "server rejected the parameter"),
        # thinking OFF: the original rule, unchanged
        (_record(), False, True, "clean on both surfaces"),
        (_record(thinking_field_present=True, thinking_nonempty=True), False, False,
         "thought anyway"),
        (_record(inline_think_tags=True), False, False, "inline think tags"),
    ],
)
def test_probe_verdict_truth_table(record, expect_thinking, verdict, why) -> None:
    assert mini_gates._probe_verdict(record, expect_thinking) is verdict, why


def _fake_chat(script: dict[bool | None, dict[str, Any]]):
    """Monkeypatch target for mini_gates._chat, keyed by the think param."""
    def fake(base_url, prompt, *, think, **kwargs):
        message = dict(script[think])
        return {"message": message, "prompt_eval_count": 50, "eval_count": 800}
    return fake


SEPARATE_CHANNEL = {"content": "71", "thinking": "17 < 71, so 71."}
INLINED = {"content": "<think>17 < 71</think>71"}
SILENT = {"content": "71"}


def test_think_behavior_thinking_on_passes_on_separate_channel(monkeypatch) -> None:
    monkeypatch.setattr(mini_gates, "_chat", _fake_chat(
        {False: SILENT, None: SEPARATE_CHANNEL, True: SEPARATE_CHANNEL}))
    out = mini_gates.think_behavior(THINK_ON)
    assert out["pass"] is True
    assert out["expect_thinking"] is True
    assert out["criterion"].startswith("inverted")
    # all three wire modes captured, and the configured mode sampled 3x
    assert [r["think_param"] for r in out["records"]] == [
        False, False, False, None, True, True, True]
    assert sum(r.get("verdict") is True for r in out["records"]) == 3


def test_think_behavior_thinking_on_fails_when_reasoning_is_inlined(monkeypatch) -> None:
    """The pre-registered exclusion: a model that inlines <think> into the
    answer channel fails the thinking-on gate even though it IS thinking."""
    monkeypatch.setattr(mini_gates, "_chat", _fake_chat(
        {False: SILENT, None: INLINED, True: INLINED}))
    out = mini_gates.think_behavior(THINK_ON)
    assert out["pass"] is False
    assert all(r["inline_think_tags"] for r in out["records"] if r["think_param"] is True)


def test_think_behavior_thinking_on_fails_when_nothing_thinks(monkeypatch) -> None:
    monkeypatch.setattr(mini_gates, "_chat", _fake_chat(
        {False: SILENT, None: SILENT, True: SILENT}))
    assert mini_gates.think_behavior(THINK_ON)["pass"] is False


def test_think_behavior_thinking_off_rule_unchanged(monkeypatch) -> None:
    """Same responses, thinking-OFF config: the non-inverted rule applies
    and only the think:false calls are adjudicated."""
    monkeypatch.setattr(mini_gates, "_chat", _fake_chat(
        {False: SILENT, None: SEPARATE_CHANNEL, True: SEPARATE_CHANNEL}))
    out = mini_gates.think_behavior(THINK_OFF)
    assert out["pass"] is True and out["expect_thinking"] is False
    assert [r["think_param"] for r in out["records"]] == [False, False, False, None, True]

    monkeypatch.setattr(mini_gates, "_chat", _fake_chat(
        {False: SEPARATE_CHANNEL, None: SILENT, True: SEPARATE_CHANNEL}))
    assert mini_gates.think_behavior(THINK_OFF)["pass"] is False  # thought anyway


def test_expect_thinking_override_beats_inference(monkeypatch) -> None:
    monkeypatch.setattr(mini_gates, "_chat", _fake_chat(
        {False: SEPARATE_CHANNEL, None: SEPARATE_CHANNEL, True: SEPARATE_CHANNEL}))
    # think=False config, but adjudicated under the inverted rule on request
    out = mini_gates.think_behavior(THINK_OFF, expect_thinking=True)
    assert out["expect_thinking"] is True and out["pass"] is True


def test_determinism_thinking_on_requires_both_channels(monkeypatch) -> None:
    """Byte-identity is required of content AND thinking on this track, and
    the probe uses the sweep's num_predict so a long preamble cannot
    truncate every answer to the same empty string."""
    seen: list[dict[str, Any]] = []

    def drifting_thinking(base_url, prompt, **kwargs):
        seen.append(kwargs)
        return {"message": {"content": "FINAL DECISION: escalate",
                            "thinking": f"path {len(seen)}"},
                "prompt_eval_count": 50, "eval_count": 900}

    monkeypatch.setattr(mini_gates, "_chat", drifting_thinking)
    out = mini_gates.determinism(THINK_ON, n=5)
    assert out["content_pass"] is True
    assert out["thinking_pass"] is False
    assert out["pass"] is False  # inverted track fails on a drifting channel
    assert out["num_predict"] == THINK_ON.num_predict
    assert all(k["num_predict"] == THINK_ON.num_predict for k in seen)
    assert out["mean_completion_tokens"] == 900

    # the same drift is NOT a failure on the thinking-off track
    seen.clear()
    off = mini_gates.determinism(THINK_OFF, n=5)
    assert off["pass"] is True and off["thinking_pass"] is False
    assert "num_predict" not in seen[0]  # thinking-off keeps the 512 default
