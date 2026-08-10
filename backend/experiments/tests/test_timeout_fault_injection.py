"""Timeout fault injection: prove ``run_timeout_s`` fires through the full
LangGraph agent path (both arms) when a model call hangs at the wire.

``ollama.AsyncClient.chat`` is monkeypatched with a never-resolving awaitable
behind the real ChatOllama + LangGraph stack, so the hang happens exactly
where a wedged Ollama server would produce it. The runner's single-run
execution path (``experiments.harness.runner.execute_run``) is driven with a
tiny timeout and asserts the locked semantics:

- the run is journalled with ``decision: "malformed"`` and the timeout error
  string (never excluded, never retried);
- the runner proceeds to the next planned run, which completes normally;
- ``asyncio.wait_for`` cancellation leaves no orphaned tasks and no
  "Task was destroyed but it is pending" asyncio errors.

No network, no LLM: the wire mock replays scripted responses after the
initial hang (same adversarial-probe pattern as ``test_single_graph``).
"""

from __future__ import annotations

import asyncio
import gc
import logging
from dataclasses import replace
from typing import Any

import ollama
import pytest

from experiments.config import DEFAULT_CONFIG
from experiments.harness.extraction import MALFORMED
from experiments.harness.journal import Journal, completed_keys, read_journal
from experiments.harness.runner import execute_run
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# Tiny per-run timeout for the fault injection (locked sweep value is 900s;
# the mechanism under test is identical).
TINY_TIMEOUT_S = 2.0

IDENTITY = {"model_digest": "sha256:test", "ollama_version": "0.0.0-test"}

CASE = {
    "alert_id": "TXN-TEST-1",
    "amount": 47500.0,
    "currency": "USD",
    "sender": "Acme Exports Ltd",
    "receiver": "Shadow Corp",
    "country": "KY",
    "flags": ["offshore", "structuring"],
    "description": "Wire split across accounts just under reporting threshold.",
}


class _NameArgs(BaseModel):
    name: str = Field(...)


def _tools() -> list[StructuredTool]:
    def check_sanctions_list(name: str) -> str:
        return f"{{'name': '{name}', 'is_sanctioned': False}}"

    return [
        StructuredTool.from_function(
            func=check_sanctions_list,
            name="check_sanctions_list",
            description="Screen an entity name against sanctions lists.",
            args_schema=_NameArgs,
        )
    ]


def _response(content: str) -> dict[str, Any]:
    """One final (done) Ollama chat chunk in the wire shape ChatOllama parses."""
    return {
        "model": DEFAULT_CONFIG.model,
        "created_at": "2026-08-10T00:00:00Z",
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": 100,
        "eval_count": 20,
    }


@pytest.fixture
def hang_then_answer(monkeypatch):
    """First wire call hangs forever (cancellable); every later call answers.

    The hang is a bare ``asyncio.Event().wait()`` — it never resolves, and is
    only released by the cancellation that ``asyncio.wait_for`` injects when
    the runner's per-run timeout expires.
    """
    calls: list[dict[str, Any]] = []

    async def fake_chat(self, **kwargs: Any):
        calls.append(kwargs)
        if len(calls) == 1:
            await asyncio.Event().wait()  # never set: hangs until cancelled
        resp = _response("Reviewed the alert.\nFINAL DECISION: escalate")

        async def gen():
            yield resp

        return gen()

    monkeypatch.setattr(ollama.AsyncClient, "chat", fake_chat)
    return calls


def _entry(arm: str, repeat_idx: int) -> dict[str, Any]:
    return {
        "run_id": f"{arm}:{CASE['alert_id']}:t0-fixed:{repeat_idx}",
        "arm": arm,
        "case_id": CASE["alert_id"],
        "block": "primary",
        "condition": "t0-fixed",
        "repeat_idx": repeat_idx,
        "seed": 42,
        "temperature": 0.0,
    }


@pytest.mark.parametrize("arm", ["single", "mas"])
def test_timeout_journals_malformed_and_runner_continues(
    arm, hang_then_answer, tmp_path, caplog
) -> None:
    from experiments.harness.adapter import ArmAdapter

    config = replace(
        DEFAULT_CONFIG, run_timeout_s=TINY_TIMEOUT_S, results_dir=tmp_path
    )
    adapter = ArmAdapter(arm, config, tool_builder=_tools)
    jpath = tmp_path / f"journal-{arm}.jsonl"

    async def two_run_session() -> list[set]:
        """The runner's loop shape: execute, journal, proceed. Never raises."""
        leftovers = []
        with Journal(jpath) as journal:
            for repeat_idx in (0, 1):
                record = await execute_run(
                    _entry(arm, repeat_idx), adapter, CASE, config, IDENTITY
                )
                journal.append(record)
                # snapshot of any tasks the finished run left behind
                leftovers.append(
                    asyncio.all_tasks() - {asyncio.current_task()}
                )
        return leftovers

    with caplog.at_level(logging.WARNING, logger="asyncio"):
        leftovers = asyncio.run(two_run_session())
        gc.collect()  # force any destroyed-pending-task complaints now

    records = read_journal(jpath)
    assert len(records) == 2, "runner must proceed to the next run after a timeout"

    timed_out, succeeded = records
    # Run 1: hung model call -> wait_for expiry journalled as malformed.
    assert timed_out["decision"] == MALFORMED
    assert timed_out["error"] is not None
    assert timed_out["error"].startswith("TimeoutError")
    assert timed_out["wall_clock_s"] >= TINY_TIMEOUT_S
    assert timed_out["raw_output"] == ""
    assert timed_out["tool_calls"] == []

    # Run 2: the very next planned run completes normally on the same adapter.
    assert succeeded["decision"] == "escalate"
    assert succeeded["error"] is None
    assert succeeded["repeat_idx"] == 1

    # Resume semantics: both runs (including the malformed one) are journalled
    # and enter the resume set — timeouts are never retried.
    assert completed_keys(jpath) == {
        (CASE["alert_id"], arm, "t0-fixed", 0),
        (CASE["alert_id"], arm, "t0-fixed", 1),
    }

    # No orphaned tasks survived either run (wait_for cancelled the hung
    # agent task to completion before raising).
    for i, tasks in enumerate(leftovers):
        assert not tasks, f"orphaned tasks after run {i}: {tasks}"
    # No 'Task was destroyed but it is pending!' style asyncio complaints.
    asyncio_noise = [r.message for r in caplog.records if r.name == "asyncio"]
    assert asyncio_noise == []

    # The hang really happened on the wire (first call), and the second run
    # went through the full ChatOllama serialization path again.
    assert len(hang_then_answer) >= 2
