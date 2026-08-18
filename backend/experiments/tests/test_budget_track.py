"""Budget-sensitivity track (v2b, "@b32" registry keys) — offline, no LLM.

Covers, per the pre-registration draft (CHANGELOG-budget-track-DRAFT.md):

1. per-node LLM-turn budgets reach ``run_tool_loop`` correctly, node by node;
2. an int ``max_iterations`` still behaves exactly as before (uniform);
3. non-b32 registry keys construct agents byte-identically to the v2 code
   path (regression guard for every sealed and in-flight sweep);
4. the B32 prompts each contain the budget-disclosure sentence with the
   right number for their role — and differ from the v2 prompts by exactly
   that sentence;
5. the generalised ``analysis/seal_checks.py`` runs against an existing
   sealed results dir without error;
plus: the b32 adapter wiring (budgets + prompts + wire payload), the
manifest config record (budgets and B32 prompts hashed in), and the journal
``iteration_budgets`` stamp.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

import app.agents.mas as mas_mod
from app.agents.contract import RunContext
from app.agents.mas import NODES, MasAgent
from app.agents.single import ToolLoopResult
from experiments.config import (
    DEFAULT_CONFIG,
    EXPERIMENTS_DIR,
    MAS_ITERATION_BUDGETS,
    MAS_TOOL_PARTITION,
    REPLICATION_MODELS,
    SINGLE_ITERATION_BUDGET,
    config_for_model,
    is_budget_track_key,
)
from experiments.harness import manifest as manifest_mod
from experiments.harness.adapter import ArmAdapter
from experiments.harness.runner import execute_run
from experiments.mas.prompts import BUDGET_SENTENCES, MAS_PROMPTS, MAS_PROMPTS_B32
from experiments.single.prompts import (
    BUDGET_SENTENCE_SINGLE,
    OUTPUT_CONTRACT,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_B32,
)
from experiments.tests.test_harness_v2 import (  # noqa: F401
    CASE,
    IDENTITY,
    _entry,
    _response,
    _tools,
    wire,
)

B32_KEYS = tuple(k for k in REPLICATION_MODELS if is_budget_track_key(k))

#: The six pre-registered sweeps: registry key -> results dirname.
EXPECTED_B32 = {
    "qwen2.5:7b-instruct@b32": ("qwen2.5:7b-instruct", "results-budget-qwen2.5-7b", None),
    "granite4.1:8b@b32": ("granite4.1:8b", "results-budget-granite4.1-8b", None),
    "qwen3.5:9b@b32": ("qwen3.5:9b", "results-budget-qwen3.5-9b", False),
    "lfm2.5:8b@b32-think": ("lfm2.5:8b", "results-budget-lfm2.5-8b-thinking", True),
    "qwen3.5:9b@b32-think-budget": (
        "qwen3.5:9b", "results-budget-qwen3.5-9b-thinking", True),
    "gemma4:latest@b32": ("gemma4:latest", "results-budget-gemma4", None),
}


# --------------------------------------------------- 1+2: per-node budgets


def _mas_agent(max_iterations) -> MasAgent:
    return MasAgent(
        model_factory=lambda context: object(),
        tools=[],
        prompts=MAS_PROMPTS,
        tool_partition=MAS_TOOL_PARTITION,
        render_case=lambda case: "CASE",
        max_iterations=max_iterations,
    )


def _capture_budgets(monkeypatch) -> list[int]:
    seen: list[int] = []

    async def fake_loop(llm, tools, messages, max_iterations) -> ToolLoopResult:
        seen.append(max_iterations)
        return ToolLoopResult(
            output_text=f"out-{len(seen)}",
            tool_calls=[],
            agent_messages=1,
            prompt_tokens=0,
            completion_tokens=0,
        )

    monkeypatch.setattr(mas_mod, "run_tool_loop", fake_loop)
    return seen


def test_per_node_budgets_reach_run_tool_loop(monkeypatch) -> None:
    """A mapping delivers each node ITS budget, in pipeline order."""
    seen = _capture_budgets(monkeypatch)
    agent = _mas_agent(dict(MAS_ITERATION_BUDGETS))
    context = RunContext(run_id="r", case_id="c", seed=0, temperature=0.0)
    asyncio.run(agent.arun(CASE, context))
    assert seen == [MAS_ITERATION_BUDGETS[n] for n in NODES] == [4, 16, 8, 4]


def test_int_budget_behaves_exactly_as_before(monkeypatch) -> None:
    """An int still means the uniform v2 budget on every node."""
    seen = _capture_budgets(monkeypatch)
    agent = _mas_agent(8)
    context = RunContext(run_id="r", case_id="c", seed=0, temperature=0.0)
    asyncio.run(agent.arun(CASE, context))
    assert seen == [8, 8, 8, 8]
    assert agent._max_iterations == {n: 8 for n in NODES}  # noqa: SLF001


def test_budget_mapping_validated() -> None:
    with pytest.raises(ValueError, match="missing iteration budgets"):
        _mas_agent({"orchestrator": 4})
    with pytest.raises(ValueError, match="unknown nodes"):
        _mas_agent({**MAS_ITERATION_BUDGETS, "auditor": 2})


# ------------------------------------- 3: non-b32 keys byte-identical to v2


@pytest.mark.parametrize("key", ["granite4.1:8b", "qwen3.5:9b", "qwen3.5:9b@think"])
def test_non_b32_keys_construct_exactly_as_main(key: str) -> None:
    """Regression guard: a non-b32 config must build BOTH arms' agents with
    the pre-registered v2 prompts (same objects, not copies) and the uniform
    max_iterations scalar — byte-identical to main's behaviour."""
    config = config_for_model(key)
    assert config.budget_track is False
    single = ArmAdapter("single", config, tool_builder=_tools)._build_agent()
    assert single._system_prompt is SYSTEM_PROMPT  # noqa: SLF001
    assert single._max_iterations == config.max_iterations == 8  # noqa: SLF001
    mas = ArmAdapter("mas", config, tool_builder=_tools)._build_agent()
    assert mas._prompts == MAS_PROMPTS  # noqa: SLF001
    assert mas._max_iterations == {n: 8 for n in NODES}  # noqa: SLF001


def test_non_b32_config_records_unchanged() -> None:
    """No non-b32 config record gains budget fields or B32 prompt text.
    (The byte-level guarantee is the pinned hashes in test_replication.)"""
    for key in REPLICATION_MODELS:
        if key in B32_KEYS:
            continue
        record = manifest_mod.config_record(config_for_model(key))
        assert "iteration_budgets" not in record, key
        assert record["prompts"]["single_system"] == SYSTEM_PROMPT
        assert record["prompts"]["mas_data"] == MAS_PROMPTS["data"]


# --------------------------------------------------- 4: disclosure prompts


def test_b32_prompts_disclose_the_right_budget_per_role() -> None:
    assert (
        f"at most {SINGLE_ITERATION_BUDGET} tool-use steps" in SYSTEM_PROMPT_B32
    )
    assert "at most 32 tool-use steps" in SYSTEM_PROMPT_B32
    assert "at most 16 tool-use steps" in MAS_PROMPTS_B32["data"]
    assert "at most 8 tool-use steps" in MAS_PROMPTS_B32["policy_risk"]
    assert "at most 4 steps" in MAS_PROMPTS_B32["orchestrator"]
    assert "at most 4 steps" in MAS_PROMPTS_B32["reporting"]
    for node in NODES:
        assert BUDGET_SENTENCES[node] in MAS_PROMPTS_B32[node]
        assert str(MAS_ITERATION_BUDGETS[node]) in BUDGET_SENTENCES[node]
    # pooled equality across arms: MAS budgets sum to the single budget
    assert sum(MAS_ITERATION_BUDGETS.values()) == SINGLE_ITERATION_BUDGET == 32


def test_b32_prompts_differ_by_exactly_the_budget_sentence() -> None:
    """Each B32 prompt is its v2 original plus ONE sentence — nothing else
    changes, and the v2 originals themselves are untouched."""
    assert SYSTEM_PROMPT_B32.replace(f"{BUDGET_SENTENCE_SINGLE}\n\n", "") == SYSTEM_PROMPT
    assert BUDGET_SENTENCE_SINGLE not in SYSTEM_PROMPT
    for node in ("orchestrator", "data", "policy_risk"):
        assert (
            MAS_PROMPTS_B32[node].replace(f" {BUDGET_SENTENCES[node]}", "")
            == MAS_PROMPTS[node]
        )
    assert (
        MAS_PROMPTS_B32["reporting"].replace(
            f"{BUDGET_SENTENCES['reporting']}\n\n", ""
        )
        == MAS_PROMPTS["reporting"]
    )
    for node in NODES:
        assert BUDGET_SENTENCES[node] not in MAS_PROMPTS[node]
    # both prompts still end with the shared output contract
    assert SYSTEM_PROMPT_B32.endswith(OUTPUT_CONTRACT)
    assert MAS_PROMPTS_B32["reporting"].endswith(OUTPUT_CONTRACT)


# --------------------------------------------------------- registry + config


def test_b32_registry_entries() -> None:
    assert set(B32_KEYS) == set(EXPECTED_B32)
    sealed_dirs = {
        config_for_model(k).results_dir
        for k in REPLICATION_MODELS
        if k not in B32_KEYS
    }
    for key, (tag, dirname, think) in EXPECTED_B32.items():
        c = config_for_model(key)
        assert c.model == tag and c.model != key
        assert c.think == think  # mirrors the tag's sealed counterpart
        assert c.results_dir == EXPERIMENTS_DIR / dirname
        assert c.results_dir not in sealed_dirs
        assert c.budget_track is True
        # everything else stays the locked v2 design
        assert c.num_ctx == 16384
        assert c.cache_policy == "none"
        assert c.run_timeout_s == 900.0
        expected_predict = 8192 if key == "qwen3.5:9b@b32-think-budget" else 2048
        assert c.num_predict == expected_predict


def test_b32_seed_schedule_identical_to_v2() -> None:
    """planned_runs derives from MASTER_SEED only — b32 sweeps share the
    exact seed schedule of every sealed sweep."""
    for key in B32_KEYS:
        assert (
            manifest_mod.planned_runs(config_for_model(key))
            == manifest_mod.planned_runs(DEFAULT_CONFIG)
        )


# ------------------------------------------------- adapter wiring (b32 only)


def test_b32_adapter_wires_budgets_and_prompts() -> None:
    config = config_for_model("granite4.1:8b@b32")
    single = ArmAdapter("single", config, tool_builder=_tools)._build_agent()
    assert single._system_prompt == SYSTEM_PROMPT_B32  # noqa: SLF001
    assert single._max_iterations == SINGLE_ITERATION_BUDGET == 32  # noqa: SLF001
    mas = ArmAdapter("mas", config, tool_builder=_tools)._build_agent()
    assert mas._prompts == MAS_PROMPTS_B32  # noqa: SLF001
    assert mas._max_iterations == MAS_ITERATION_BUDGETS  # noqa: SLF001


def test_b32_single_run_sends_b32_prompt_and_journals_budget(wire) -> None:  # noqa: F811
    payloads, responses = wire
    responses += [_response("FINAL DECISION: escalate")]
    config = config_for_model("granite4.1:8b@b32")
    adapter = ArmAdapter("single", config, tool_builder=_tools)
    record = asyncio.run(execute_run(_entry("single"), adapter, CASE, config, IDENTITY))
    assert record["decision"] == "escalate"
    # F: the journal line records the budget enforced on this run
    assert record["iteration_budgets"] == {"single": 32}
    # the disclosure sentence went out on the wire, in the system message
    system = payloads[0]["messages"][0]
    assert system["role"] == "system"
    assert BUDGET_SENTENCE_SINGLE in system["content"]
    assert system["content"] == SYSTEM_PROMPT_B32


def test_b32_mas_run_journals_per_node_budgets(wire) -> None:  # noqa: F811
    payloads, responses = wire
    responses += [
        _response("PLAN: sanctions first"),
        _response("FINDINGS: offshore receiver"),
        _response("ASSESSMENT: high risk"),
        _response("Report.\nFINAL DECISION: escalate"),
    ]
    config = config_for_model("granite4.1:8b@b32")
    adapter = ArmAdapter("mas", config, tool_builder=_tools)
    record = asyncio.run(execute_run(_entry("mas"), adapter, CASE, config, IDENTITY))
    assert record["decision"] == "escalate"
    assert record["iteration_budgets"] == MAS_ITERATION_BUDGETS
    # each node's wire call carried ITS B32 prompt
    for payload, node in zip(payloads, NODES):
        assert payload["messages"][0]["content"] == MAS_PROMPTS_B32[node]


def test_non_b32_run_journals_null_budgets(wire) -> None:  # noqa: F811
    payloads, responses = wire
    responses += [_response("FINAL DECISION: dismiss")]
    config = config_for_model("granite4.1:8b")
    adapter = ArmAdapter("single", config, tool_builder=_tools)
    record = asyncio.run(execute_run(_entry("single"), adapter, CASE, config, IDENTITY))
    assert record["iteration_budgets"] is None
    assert payloads[0]["messages"][0]["content"] == SYSTEM_PROMPT


# ------------------------------------------------------- E: manifest record


def test_b32_manifest_records_budgets_and_b32_prompts() -> None:
    record = manifest_mod.config_record(config_for_model("granite4.1:8b@b32"))
    assert record["iteration_budgets"] == {
        "single": 32,
        "mas": {"orchestrator": 4, "data": 16, "policy_risk": 8, "reporting": 4},
    }
    assert record["prompts"]["single_system"] == SYSTEM_PROMPT_B32
    for node in NODES:
        assert record["prompts"][f"mas_{node}"] == MAS_PROMPTS_B32[node]
    # config_hash changes vs the v2 key for the same tag
    h_b32 = manifest_mod._sha256(record)
    h_v2 = manifest_mod._sha256(
        manifest_mod.config_record(config_for_model("granite4.1:8b"))
    )
    assert h_b32 != h_v2


# ----------------------------------------------------- 5: seal_checks runs


def test_seal_checks_runs_on_sealed_dir(capsys) -> None:
    """The generalised seal_checks must complete over a sealed results dir
    (read-only) and report per-arm results plus the severed-channel scan."""
    from experiments.analysis import seal_checks

    results = EXPERIMENTS_DIR / "results-granite4.1-8b"
    assert results.exists()
    failures = seal_checks.check_sweep(results)
    out = capsys.readouterr().out
    assert isinstance(failures, int) and failures >= 0
    assert f"{results.name} / single:" in out
    assert f"{results.name} / mas:" in out
    assert "EMPTY output" in out  # severed-channel detector ran
    assert "label prior:" in out  # degeneracy check ran
