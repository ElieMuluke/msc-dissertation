"""Harness v2 features: MAS inter-node journaling, cache-state control,
environment fingerprint. All mocked at the ollama wire — no network, no LLM.

Covers (harness-v2 branch; see CHANGELOG 2026-08-10):

- ``AgentResult.node_outputs`` threaded from the MAS graph into the journal
  line, node order preserved; single arm journals ``null``;
- ``cache_policy=prewarm``: the exact opening prompt is sent once and
  discarded before eligible (t0-fixed / pert-t0) runs, and prewarm failures
  never kill the measured run;
- ``cache_policy=shuffle``: deterministic, arm-independent per-repeat
  case-order permutation derived from MASTER_SEED;
- manifest records the policy (inside the hashed config record);
- ``EnvFingerprint``: nvidia-smi parsing, per-N-runs caching, and null
  fields when nvidia-smi is absent.
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import replace
from typing import Any

import ollama
import pytest

from app.agents.contract import AgentResult, RunContext
from app.agents.mas import NODES
from experiments.config import DEFAULT_CONFIG
from experiments.harness.adapter import ArmAdapter
from experiments.harness.env_fingerprint import EnvFingerprint
from experiments.harness.extraction import MALFORMED
from experiments.harness.manifest import config_record
from experiments.harness.runner import _cache_shuffle, _maybe_prewarm, execute_run
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

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
def wire(monkeypatch):
    """Capture wire payloads; replay scripted responses (FIFO, then repeat last)."""
    payloads: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []

    async def fake_chat(self, **kwargs: Any):
        payloads.append(kwargs)
        resp = responses.pop(0) if len(responses) > 1 else responses[0]

        async def gen():
            yield resp

        return gen()

    monkeypatch.setattr(ollama.AsyncClient, "chat", fake_chat)
    return payloads, responses


def _entry(arm: str, condition: str = "t0-fixed") -> dict[str, Any]:
    return {
        "run_id": f"{arm}:{CASE['alert_id']}:{condition}:0",
        "arm": arm,
        "case_id": CASE["alert_id"],
        "block": "perturbation" if condition.startswith("pert") else "primary",
        "condition": condition,
        "repeat_idx": 0,
        "seed": 42,
        "temperature": 0.0,
    }


# --------------------------------------------------------------- node_outputs


def test_mas_node_outputs_journalled_in_pipeline_order(wire) -> None:
    payloads, responses = wire
    responses += [
        _response("PLAN: check sanctions first"),
        _response("FINDINGS: receiver is offshore"),
        _response("ASSESSMENT: high risk"),
        _response("Report done.\nFINAL DECISION: escalate"),
    ]
    adapter = ArmAdapter("mas", DEFAULT_CONFIG, tool_builder=_tools)
    record = asyncio.run(
        execute_run(_entry("mas"), adapter, CASE, DEFAULT_CONFIG, IDENTITY)
    )
    assert record["decision"] == "escalate"
    assert record["node_outputs"] is not None
    # order preserved: node names in pipeline order
    assert list(record["node_outputs"]) == list(NODES)
    assert record["node_outputs"] == {
        "orchestrator": "PLAN: check sanctions first",
        "data": "FINDINGS: receiver is offshore",
        "policy_risk": "ASSESSMENT: high risk",
        "reporting": "Report done.\nFINAL DECISION: escalate",
    }
    assert len(payloads) == 4  # one model call per node, no tool turns


def test_single_arm_journals_node_outputs_null(wire) -> None:
    _, responses = wire
    responses += [_response("FINAL DECISION: dismiss")]
    adapter = ArmAdapter("single", DEFAULT_CONFIG, tool_builder=_tools)
    record = asyncio.run(
        execute_run(_entry("single"), adapter, CASE, DEFAULT_CONFIG, IDENTITY)
    )
    assert record["decision"] == "dismiss"
    assert record["node_outputs"] is None


def test_errored_run_journals_node_outputs_null() -> None:
    class _Boom:
        async def arun(self, case, context):
            raise RuntimeError("kaput")

    record = asyncio.run(
        execute_run(_entry("mas"), _Boom(), CASE, DEFAULT_CONFIG, IDENTITY)
    )
    assert record["decision"] == MALFORMED
    assert record["error"] == "RuntimeError: kaput"
    assert record["node_outputs"] is None


def test_agent_result_node_outputs_defaults_none() -> None:
    # contract compatibility: pre-v2 constructions remain valid, field None
    assert AgentResult(output_text="x").node_outputs is None


# --------------------------------------------------------------- cache policy


def test_journal_records_cache_policy_and_env(wire) -> None:
    _, responses = wire
    responses += [_response("FINAL DECISION: investigate")]
    adapter = ArmAdapter("single", DEFAULT_CONFIG, tool_builder=_tools)
    env = {"gpu_name": "Test GPU", "gpu_driver": "1.0", "gpu_vram_used_mb": 123,
           "host_load_1m": 0.5, "host_load_high": False}
    config = replace(DEFAULT_CONFIG, cache_policy="prewarm")
    record = asyncio.run(
        execute_run(_entry("single"), adapter, CASE, config, IDENTITY, env=env)
    )
    assert record["cache_policy"] == "prewarm"
    assert record["env"] == env
    # default policy is byte-identical harness-v1 behaviour and journals as such
    responses += [_response("FINAL DECISION: investigate")]
    record = asyncio.run(
        execute_run(_entry("single"), adapter, CASE, DEFAULT_CONFIG, IDENTITY)
    )
    assert record["cache_policy"] == "none"
    assert record["env"] is None


@pytest.mark.parametrize("arm", ["single", "mas"])
def test_prewarm_sends_exact_opening_prompt_once(wire, arm) -> None:
    payloads, responses = wire
    responses += [_response("FINAL DECISION: escalate")]
    config = replace(DEFAULT_CONFIG, cache_policy="prewarm")
    adapter = ArmAdapter(arm, config, tool_builder=_tools)

    async def one_run():
        entry = _entry(arm)
        await _maybe_prewarm(entry, adapter, CASE, config)
        return await execute_run(entry, adapter, CASE, config, IDENTITY)

    record = asyncio.run(one_run())
    assert record["error"] is None
    n_run_calls = 1 if arm == "single" else 4
    assert len(payloads) == n_run_calls + 1  # exactly one discarded prewarm call
    # the prewarm call IS the run's opening call: same messages, same tools
    assert payloads[0]["messages"] == payloads[1]["messages"]
    assert payloads[0].get("tools") == payloads[1].get("tools")
    assert payloads[0]["options"] == payloads[1]["options"]


def test_prewarm_skips_non_deterministic_conditions_and_policy_none(wire) -> None:
    payloads, responses = wire
    responses += [_response("FINAL DECISION: escalate")]
    prewarm_cfg = replace(DEFAULT_CONFIG, cache_policy="prewarm")
    adapter = ArmAdapter("single", prewarm_cfg, tool_builder=_tools)

    async def check(entry, config):
        before = len(payloads)
        await _maybe_prewarm(entry, adapter, CASE, config)
        return len(payloads) - before

    # varied-temperature condition: never prewarmed even under the policy
    assert asyncio.run(check(_entry("single", "t07-varied"), prewarm_cfg)) == 0
    # policy none: eligible condition still not prewarmed (v1 behaviour)
    assert asyncio.run(check(_entry("single"), DEFAULT_CONFIG)) == 0
    # policy prewarm + eligible perturbation condition: prewarmed
    assert asyncio.run(check(_entry("single", "pert-t0"), prewarm_cfg)) == 1


def test_prewarm_failure_is_non_fatal(monkeypatch) -> None:
    config = replace(DEFAULT_CONFIG, cache_policy="prewarm")
    adapter = ArmAdapter("single", config, tool_builder=_tools)

    async def boom(case, context):
        raise ConnectionError("server gone")

    monkeypatch.setattr(adapter, "aprewarm", boom)
    # must not raise
    asyncio.run(_maybe_prewarm(_entry("single"), adapter, CASE, config))


def _planned(arm: str, n_cases: int = 12) -> list[dict[str, Any]]:
    runs = []
    for condition, repeats in (("t0-fixed", 2), ("t07-varied", 2)):
        for repeat_idx in range(repeats):
            for i in range(n_cases):
                runs.append(
                    {
                        "run_id": f"{arm}:CASE-{i:03d}:{condition}:{repeat_idx}",
                        "arm": arm,
                        "case_id": f"CASE-{i:03d}",
                        "condition": condition,
                        "repeat_idx": repeat_idx,
                    }
                )
    return runs


def test_cache_shuffle_is_deterministic_permutation() -> None:
    planned = _planned("single")
    s1, s2 = _cache_shuffle(planned), _cache_shuffle(planned)
    assert s1 == s2, "shuffle must be a pure function of the manifest"
    assert s1 != planned, "shuffle must actually permute case order"
    # permutation only: same multiset of runs overall...
    assert sorted(r["run_id"] for r in s1) == sorted(r["run_id"] for r in planned)
    # ...and within every (condition, repeat) group
    for condition, repeat_idx in {(r["condition"], r["repeat_idx"]) for r in planned}:
        want = {r["run_id"] for r in planned
                if (r["condition"], r["repeat_idx"]) == (condition, repeat_idx)}
        got = {r["run_id"] for r in s1
               if (r["condition"], r["repeat_idx"]) == (condition, repeat_idx)}
        assert got == want
    # different repeats get different case orders (that is the point)
    order_r0 = [r["case_id"] for r in s1
                if (r["condition"], r["repeat_idx"]) == ("t0-fixed", 0)]
    order_r1 = [r["case_id"] for r in s1
                if (r["condition"], r["repeat_idx"]) == ("t0-fixed", 1)]
    assert order_r0 != order_r1


def test_cache_shuffle_is_arm_independent() -> None:
    """Both arms execute the same shuffled case order (comparability)."""
    orders = {}
    for arm in ("single", "mas"):
        shuffled = _cache_shuffle(_planned(arm))
        orders[arm] = [
            (r["condition"], r["repeat_idx"], r["case_id"]) for r in shuffled
        ]
    assert orders["single"] == orders["mas"]


def test_manifest_config_records_cache_policy() -> None:
    assert config_record(DEFAULT_CONFIG)["cache_policy"] == "none"
    cfg = replace(DEFAULT_CONFIG, cache_policy="shuffle")
    assert config_record(cfg)["cache_policy"] == "shuffle"


# ------------------------------------------------------------ env fingerprint

_SMI_LINE = "NVIDIA GeForce RTX 4090, 550.120, 18432\n"


def _fake_smi(monkeypatch, calls: list, stdout: str = _SMI_LINE, rc: int = 0):
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="")

    monkeypatch.setattr(
        "experiments.harness.env_fingerprint.subprocess.run", fake_run
    )


def test_env_fingerprint_parses_nvidia_smi(monkeypatch) -> None:
    calls: list = []
    _fake_smi(monkeypatch, calls)
    sample = EnvFingerprint(refresh_every=5).sample()
    assert sample["gpu_name"] == "NVIDIA GeForce RTX 4090"
    assert sample["gpu_driver"] == "550.120"
    assert sample["gpu_vram_used_mb"] == 18432
    assert isinstance(sample["host_load_1m"], float)
    assert isinstance(sample["host_load_high"], bool)


def test_env_fingerprint_caches_per_n_runs(monkeypatch) -> None:
    calls: list = []
    _fake_smi(monkeypatch, calls)
    fp = EnvFingerprint(refresh_every=10)
    for _ in range(25):
        fp.sample()
    # refreshed on samples 1, 11 and 21 only
    assert len(calls) == 3


def test_env_fingerprint_tolerates_missing_nvidia_smi(monkeypatch) -> None:
    def no_smi(cmd, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(
        "experiments.harness.env_fingerprint.subprocess.run", no_smi
    )
    sample = EnvFingerprint().sample()
    assert sample["gpu_name"] is None
    assert sample["gpu_driver"] is None
    assert sample["gpu_vram_used_mb"] is None
    assert sample["host_load_1m"] is not None  # load still reported


def test_env_fingerprint_tolerates_nvidia_smi_failure(monkeypatch) -> None:
    calls: list = []
    _fake_smi(monkeypatch, calls, stdout="", rc=9)
    sample = EnvFingerprint().sample()
    assert sample["gpu_name"] is None
    assert sample["gpu_vram_used_mb"] is None
