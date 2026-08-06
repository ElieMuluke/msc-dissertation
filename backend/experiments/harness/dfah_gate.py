"""G2 gate: DFAH integration check via DFAH's own runner.

Verifies, in order:

1. dfah-bench is installed;
2. the 50 alerts load (and the 10 perturbation variants parse);
3. every DFAH mocked tool responds;
4. one case completes through DFAH's own ``Replay`` orchestrator (its
   minimum design: 1 case × 2 replays), with our arm-A adapter wrapped to
   DFAH's agent protocol.

The wrapper runs the real arm (LangChain tools, our ArmAdapter) and then
replays the recorded tool calls through the DFAH ``ToolSession`` so DFAH
observes a genuine trajectory — the mocks are deterministic, so results are
identical. This shim exists only for this conformance gate; the sweep uses
the PRD-A journalled runner.

Usage::

    python -m experiments.harness.dfah_gate [--case TXN-2025-001] [--arm single]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import dfah

from app.agents.contract import RunContext as HarnessRunContext
from experiments.config import DEFAULT_CONFIG, DECISIONS, RESULTS_DIR
from experiments.harness.adapter import ArmAdapter
from experiments.harness.dfah_tools import build_dfah_tools, load_task_module
from experiments.harness.dfah_data import load_perturbation_cases, load_primary_cases

_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_precedents": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
    "get_customer_profile": {
        "type": "object",
        "properties": {"customer_id": {"type": "string"}},
        "required": ["customer_id"],
        "additionalProperties": False,
    },
    "check_sanctions_list": {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    },
    "calculate_risk_score": {
        "type": "object",
        "properties": {"factors": {"type": "object"}},
        "required": ["factors"],
        "additionalProperties": False,
    },
}


def _build_registry() -> dfah.ToolRegistry:
    task = load_task_module()
    impl = task.ComplianceTriageTools(task.create_test_context())
    registry = dfah.ToolRegistry()

    @registry.tool(dfah.ToolSpec(name="search_precedents",
                                 input_schema=_TOOL_SCHEMAS["search_precedents"]))
    def search_precedents(*, query: str) -> str:
        return str(impl.search_precedents(query))

    @registry.tool(dfah.ToolSpec(name="get_customer_profile",
                                 input_schema=_TOOL_SCHEMAS["get_customer_profile"]))
    def get_customer_profile(*, customer_id: str) -> str:
        return str(impl.get_customer_profile(customer_id))

    @registry.tool(dfah.ToolSpec(name="check_sanctions_list",
                                 input_schema=_TOOL_SCHEMAS["check_sanctions_list"]))
    def check_sanctions_list(*, name: str) -> str:
        return str(impl.check_sanctions_list(name))

    @registry.tool(dfah.ToolSpec(name="calculate_risk_score",
                                 input_schema=_TOOL_SCHEMAS["calculate_risk_score"]))
    def calculate_risk_score(*, factors: dict[str, Any]) -> str:
        return str(impl.calculate_risk_score(factors))

    return registry


def _build_suite(case: dict[str, Any]) -> dfah.Suite:
    return dfah.Suite(
        suite_id="dfah-compliance-triage-g2",
        suite_version="1.0.0",
        decisions=DECISIONS,
        cases=(dfah.Case(case_id=case["alert_id"], input=case),),
        tools=tuple(
            dfah.ToolSpec(name=name, input_schema=schema)
            for name, schema in sorted(_TOOL_SCHEMAS.items())
        ),
        description="G2 conformance gate: one DFAH alert through DFAH's Replay.",
    )


def _make_agent(arm: str, suite: dfah.Suite, registry: dfah.ToolRegistry,
                temperature: float, seed: int):
    adapter = ArmAdapter(arm, DEFAULT_CONFIG)
    parameters = {"temperature": temperature, "seed": seed}
    manifest = dfah.build_manifest(
        suite,
        provider="ollama",
        model=DEFAULT_CONFIG.model,
        adapter=f"experiments.harness.adapter.ArmAdapter[{arm}]",
        adapter_version="0.1.0",
        request_parameters=parameters,
        implementation_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )

    @dfah.agent(manifest=manifest, tools=registry, suite=suite)
    async def arm_agent(case: dfah.Case, context: dfah.RunContext) -> dfah.AgentResult:
        assert context.tools is not None
        raw_case = dict(case.input)  # type: ignore[arg-type]
        result = await adapter.arun(
            raw_case,
            HarnessRunContext(
                run_id=f"g2:{case.case_id}:{context.replay_index}",
                case_id=case.case_id,
                seed=seed,
                temperature=temperature,
            ),
        )
        # Re-drive the recorded calls through the DFAH session so DFAH
        # observes the trajectory (mocks are deterministic).
        for call in result.tool_calls:
            try:
                await context.tools.call(call.name, **dict(call.arguments))
            except Exception:
                pass  # unknown-tool hallucinations are data, not crashes
        payload: dict[str, Any] = {
            "model": DEFAULT_CONFIG.model,
            **parameters,
            "case_id": case.case_id,
        }
        return dfah.AgentResult(
            output_text=result.output_text,
            trajectory=context.tools.trajectory(),
            wire_request=dfah.WireRequest.from_payload(
                provider="ollama",
                model=DEFAULT_CONFIG.model,
                payload=payload,
                parameters=parameters,
                adapter=f"experiments.harness.adapter.ArmAdapter[{arm}]",
                adapter_version="0.1.0",
            ),
            usage=dfah.Usage(
                input_tokens=result.prompt_tokens,
                output_tokens=result.completion_tokens,
            ),
        )

    return arm_agent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=None, help="alert_id (default: first alert)")
    parser.add_argument("--arm", default="single", choices=["single", "mas"])
    args = parser.parse_args()

    print(f"dfah-bench {dfah.__version__} installed")
    primary = load_primary_cases()
    perts = load_perturbation_cases()
    print(f"cases load: {len(primary)} primary, {len(perts)} perturbation")

    task = load_task_module()
    impl = task.ComplianceTriageTools(task.create_test_context())
    probes = [
        impl.check_sanctions_list("Shadow Corp"),
        impl.get_customer_profile("ABC Corp"),
        impl.search_precedents("offshore wire unusual"),
        impl.calculate_risk_score({"amount": 125000, "sanctions_hit": True}),
    ]
    assert all(p is not None for p in probes)
    print(f"mocked tools respond: {len(probes)}/4 (sanctions hit on Shadow Corp: "
          f"{probes[0]['is_sanctioned']})")
    lc_tools = build_dfah_tools()
    print(f"langchain wrappers build: {[t.name for t in lc_tools]}")

    case = next(
        (c for c in primary if c["alert_id"] == args.case), primary[0]
    ) if args.case else primary[0]
    suite = _build_suite(case)
    registry = _build_registry()
    agent = _make_agent(args.arm, suite, registry, temperature=0.0, seed=42)
    out = RESULTS_DIR / "gates" / "g2-dfah-replay"
    replay = dfah.Replay(suite=suite, replays=2, seed=42, tools=registry, out=out)
    report = replay.run(agent)
    print(f"DFAH Replay completed: report at {out}")
    summary = getattr(report, "model_dump", lambda: str(report))()
    (RESULTS_DIR / "gates" / "g2-report.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    print("G2 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
