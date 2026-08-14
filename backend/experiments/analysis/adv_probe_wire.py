"""Adversarial probe 1 — wire-payload capture. ZERO network / GPU / LLM.

Monkeypatches ``ollama.AsyncClient.chat`` at class level so every request
langchain-ollama would put on the wire is captured verbatim (model, think,
tools, options, messages) and answered with a canned no-tool-call response.
Everything upstream of the patch is the REAL sweep code path:
ArmAdapter -> SingleAgent/MasAgent -> run_tool_loop -> ChatOllama._agenerate
-> AsyncClient.chat(**chat_params).

Configs probed:
  (a) deepseek-r1:14b@think  think=True   single arm
  (b) qwen2.5:7b-instruct    think=None   single arm
  (c) muse-glimmer:30b       think=False  single arm
  (d) lfm2.5:8b@think        think=True   MAS arm (4 nodes)
  (e) deepseek-r1:14b@think  think=True   MAS arm (4 nodes)

Output: JSON to argv[1] (default ./adv_probe_wire.json), plus stdout verdicts.
Run from backend/:  ./.venv/bin/python experiments/analysis/adv_probe_wire.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import ollama

from app.agents.contract import RunContext
from experiments.config import MAS_TOOL_PARTITION, config_for_model
from experiments.harness.adapter import ArmAdapter
from experiments.harness.dfah_data import load_primary_cases
from experiments.mas.prompts import MAS_PROMPTS

CAPTURED: list[dict[str, Any]] = []
_REAL_CHAT = ollama.AsyncClient.chat


def _canned_chunk() -> dict[str, Any]:
    """One final non-tool-call chunk shaped like a real /api/chat stream end."""
    return {
        "model": "probe",
        "created_at": "2026-08-14T00:00:00Z",
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 100,
        "eval_count": 50,
        "message": {
            "role": "assistant",
            "content": "Assessment complete.\nFINAL DECISION: investigate",
            "thinking": "probe thinking",
        },
    }


async def _fake_chat(self, **kwargs: Any):  # noqa: ANN001
    CAPTURED.append(dict(kwargs))
    if kwargs.get("stream", False):
        async def gen():
            yield _canned_chunk()
        return gen()
    return _canned_chunk()


def _tool_names(payload: dict[str, Any]) -> list[str]:
    return [
        t.get("function", {}).get("name", "?") for t in (payload.get("tools") or [])
    ]


def _tools_sha(payload: dict[str, Any]) -> str | None:
    tools = payload.get("tools")
    if tools is None:
        return None
    # ollama _copy_tools yields Tool pydantic models; normalise to plain JSON
    def norm(t: Any) -> Any:
        if hasattr(t, "model_dump"):
            return t.model_dump(exclude_none=False)
        return t
    blob = json.dumps([norm(t) for t in tools], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _node_of(payload: dict[str, Any]) -> str:
    sys_msg = next(
        (m for m in payload.get("messages", []) if m.get("role") == "system"), {}
    )
    content = sys_msg.get("content", "")
    for node, prompt in MAS_PROMPTS.items():
        if content == prompt:
            return node
    return "single/unknown"


async def probe(key: str, arm: str, case: dict[str, Any]) -> list[dict[str, Any]]:
    CAPTURED.clear()
    config = config_for_model(key)
    adapter = ArmAdapter(arm, config)
    context = RunContext(
        run_id=f"adv-probe:{key}:{arm}", case_id=case["alert_id"],
        seed=42, temperature=0.0,
    )
    result = await adapter.arun(case, context)
    out = []
    for p in CAPTURED:
        out.append({
            "registry_key": key,
            "arm": arm,
            "node": _node_of(p) if arm == "mas" else "single",
            "wire_model": p.get("model"),
            "wire_think": p.get("think"),
            "tools_key_present": "tools" in p and p["tools"] is not None,
            "n_tools": len(p.get("tools") or []),
            "tool_names": _tool_names(p),
            "tools_sha256": _tools_sha(p),
            "options": p.get("options"),
            "n_messages": len(p.get("messages") or []),
        })
    # sanity: agent actually completed through the real loop
    assert "FINAL DECISION" in result.output_text, "loop did not complete"
    return out


async def main() -> int:
    case = load_primary_cases()[0]
    rows: list[dict[str, Any]] = []
    ollama.AsyncClient.chat = _fake_chat  # type: ignore[method-assign]
    try:
        rows += await probe("deepseek-r1:14b@think", "single", case)
        rows += await probe("qwen2.5:7b-instruct", "single", case)
        rows += await probe("muse-glimmer:30b", "single", case)
        rows += await probe("lfm2.5:8b@think", "mas", case)
        rows += await probe("deepseek-r1:14b@think", "mas", case)
    finally:
        ollama.AsyncClient.chat = _REAL_CHAT  # type: ignore[method-assign]

    for r in rows:
        print(
            f"{r['registry_key']:<28} {r['arm']:<6} {r['node']:<12} "
            f"model={r['wire_model']:<20} think={r['wire_think']!s:<5} "
            f"tools={r['tool_names']} sha={str(r['tools_sha256'])[:12]}"
        )

    # ---- verdict checks -----------------------------------------------------
    singles = [r for r in rows if r["arm"] == "single"]
    shas = {r["registry_key"]: r["tools_sha256"] for r in singles}
    print("\n[V1] single-arm full tool list byte-identical across models:",
          len(set(shas.values())) == 1, shas)
    ds = next(r for r in singles if r["registry_key"].startswith("deepseek"))
    print("[V2] deepseek think=True request carries tools:",
          ds["tools_key_present"], ds["tool_names"], "think:", ds["wire_think"])
    mas_rows = [r for r in rows if r["arm"] == "mas"]
    for key in ("lfm2.5:8b@think", "deepseek-r1:14b@think"):
        nodes = {r["node"]: r["tool_names"] for r in mas_rows if r["registry_key"] == key}
        expected = {n: sorted(v) for n, v in MAS_TOOL_PARTITION.items()}
        got = {n: sorted(v) for n, v in nodes.items()}
        print(f"[V3] {key} MAS node tool partitions match config:",
              got == expected, got)
    pol = [r for r in mas_rows if r["node"] == "policy_risk"]
    print("[V4] policy_risk node requests contain calculate_risk_score:",
          all(r["tool_names"] == ["calculate_risk_score"] for r in pol))
    # cross-arm: MAS data-node tools are a subset of the single arm's full set,
    # rendered through the identical serializer (compare name-filtered shas)
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("adv_probe_wire.json")
    dest.write_text(json.dumps(rows, indent=1, default=str))
    print(f"\nwritten {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
