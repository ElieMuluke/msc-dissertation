"""Replication mini-gates: per-model pre-launch checks in one command.

For each replication model (see ``config.REPLICATION_MODELS``) this runs:

1. **Think-behavior capture** — calls with ``think: false``, with the
   parameter omitted, and with ``think: true``, recording exactly how the
   model/server behave (non-thinking models may reject the parameter —
   that decides the model's ``think`` config value, which for the
   replication models is ``None`` = omit).
2. **G1-style determinism** — one discarded warm-up, then 5 calls at T=0
   with the fixed seed; byte-identical outputs required.
3. **2-case × 2-repeat pilot per arm** through the real runner into a
   scratch dir (never the model's results dir), with an extraction check
   (bar: ≥ 7/8 valid decisions overall, mirroring G3's ≥13/15).

Evidence is written to ``<model results dir>/gates/mini-gates.json``.
Requires the model's manifest to exist (``harness.manifest --model …``)
and the pinned arm servers to be up. Run only when no sweep is writing.

Usage (from ``backend/``)::

    python -m experiments.harness.mini_gates --model qwen2.5:7b-instruct
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from experiments.config import ARMS, FIXED_SEED, ExperimentConfig, config_for_model
from experiments.harness.gates import _chat
from experiments.harness.journal import read_journal, journal_path
from experiments.harness import runner as runner_mod

_THINK_PROBE_PROMPT = "Which is larger, 17 or 71? Answer with one word."
_DET_PROMPT = (
    "COMPLIANCE ALERT: a $47,500 USD wire from ABC Corp to XYZ Holdings in "
    "the Cayman Islands, flags: unusual_amount, offshore_destination. "
    "In under 150 words, assess the alert and end with one line "
    "'FINAL DECISION: <escalate|dismiss|investigate>'."
)


def _probe(base_url: str, model: str, think: bool | None) -> dict[str, Any]:
    """One probe call; HTTP errors are captured as data, never raised."""
    try:
        body = _chat(
            base_url, _THINK_PROBE_PROMPT,
            temperature=0.0, seed=FIXED_SEED, think=think, model=model,
        )
        message = body.get("message", {})
        return {
            "think_param": think,
            "http_ok": True,
            "thinking_field_present": "thinking" in message,
            "inline_think_tags": "<think" in (message.get("content") or "").lower(),
            "content_head": (message.get("content") or "")[:120],
        }
    except httpx.HTTPStatusError as exc:
        return {
            "think_param": think,
            "http_ok": False,
            "status": exc.response.status_code,
            "error_body": exc.response.text[:300],
        }


def think_behavior(config: ExperimentConfig) -> dict[str, Any]:
    """Capture think-parameter behavior; pass = the configured mode is clean."""
    base_url = config.base_url("single")
    records = [_probe(base_url, config.model, t) for t in (False, False, False, None, True)]
    configured = [r for r in records if r["think_param"] == config.think]
    ok = all(
        r["http_ok"] and not r.get("thinking_field_present") and not r.get("inline_think_tags")
        for r in configured
    )
    return {"pass": ok, "configured_think": config.think, "records": records}


def determinism(config: ExperimentConfig, n: int = 5) -> dict[str, Any]:
    """Warm-up + n byte-identical calls at T=0/fixed seed on the arm-A server."""
    base_url = config.base_url("single")
    kwargs = dict(temperature=0.0, seed=FIXED_SEED, think=config.think, model=config.model)
    _chat(base_url, _DET_PROMPT, **kwargs)  # warm-up, discarded
    outputs = [_chat(base_url, _DET_PROMPT, **kwargs)["message"]["content"] for _ in range(n)]
    return {
        "pass": all(o == outputs[0] for o in outputs),
        "n": n,
        "sha256": sorted({hashlib.sha256(o.encode()).hexdigest() for o in outputs}),
        "output_len": len(outputs[0]),
    }


async def _pilot(config: ExperimentConfig, scratch: Path, key: str) -> dict[str, Any]:
    """2 cases × 2 repeats per arm through the real runner, extraction check."""
    manifest_src = config.results_dir / "manifest.json"
    if not manifest_src.exists():
        raise SystemExit(
            f"{manifest_src} missing — generate it first: "
            f"python -m experiments.harness.manifest --model '{key}'"
        )
    shutil.copy(manifest_src, scratch / "manifest.json")
    per_arm: dict[str, Any] = {}
    for arm in ARMS:
        args = argparse.Namespace(
            arm=arm, condition="t0-fixed", max_cases=2, max_repeats=2,
            no_git=True, allow_digest_mismatch=False, results_dir=scratch,
        )
        pilot_config = dataclasses.replace(config, results_dir=scratch)
        await runner_mod.run_sweep(args, pilot_config)
        records = [
            r for r in read_journal(journal_path(scratch, arm))
            if r["condition"] == "t0-fixed"
        ]
        per_arm[arm] = {
            "runs": len(records),
            "valid": sum(r["decision"] != "malformed" for r in records),
            "decisions": [r["decision"] for r in records],
            "errors": [r["error"] for r in records if r["error"]],
            "mean_wall_clock_s": round(
                sum(r["wall_clock_s"] for r in records) / max(len(records), 1), 2
            ),
        }
    total_valid = sum(a["valid"] for a in per_arm.values())
    total_runs = sum(a["runs"] for a in per_arm.values())
    return {"pass": total_runs == 8 and total_valid >= 7,
            "valid_total": f"{total_valid}/{total_runs}", "arms": per_arm}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", required=True,
        help="replication registry key (config.REPLICATION_MODELS; may differ "
             "from the served model tag, e.g. 'qwen2.5:7b-instruct@0.32.6')",
    )
    parser.add_argument("--skip-pilot", action="store_true",
                        help="probes only (e.g. while servers are busy)")
    args = parser.parse_args()
    config = config_for_model(args.model)

    evidence: dict[str, Any] = {
        "registry_key": args.model,
        "model": config.model,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "servers": dict(config.arm_base_urls),
    }
    print(f"[mini-gates] {config.model}: think-behavior probe...")
    evidence["think_behavior"] = think_behavior(config)
    print(f"  pass={evidence['think_behavior']['pass']} "
          f"(configured think={config.think!r})")
    print(f"[mini-gates] {config.model}: determinism (warm-up + 5)...")
    evidence["determinism"] = determinism(config)
    print(f"  pass={evidence['determinism']['pass']} "
          f"sha256[:16]={evidence['determinism']['sha256'][0][:16]}")
    if not args.skip_pilot:
        print(f"[mini-gates] {config.model}: 2x2 pilot per arm...")
        scratch = Path(tempfile.mkdtemp(
            prefix=f"mini-gate-{args.model.replace(':', '-').replace('@', '-')}-"))
        evidence["pilot"] = asyncio.run(_pilot(config, scratch, args.model))
        evidence["pilot"]["scratch_dir"] = str(scratch)
        print(f"  pass={evidence['pilot']['pass']} valid={evidence['pilot']['valid_total']}")

    gates_dir = config.results_dir / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    out = gates_dir / "mini-gates.json"
    out.write_text(json.dumps(evidence, indent=2))
    overall = all(evidence[k]["pass"] for k in ("think_behavior", "determinism", "pilot")
                  if k in evidence)
    print(f"[mini-gates] {config.model}: {'ALL PASS' if overall else 'FAIL'} — {out}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
