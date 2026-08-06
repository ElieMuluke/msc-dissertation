"""Checkpointed sweep runner for one arm.

Consumes ``results/manifest.json`` (never generates seeds itself), skips
runs already journalled, executes the remainder sequentially against the
arm's dedicated Ollama server, and after every run appends one fsynced
journal line and rewrites ``results/progress.json``. Every N runs the
results directory is committed and pushed (best-effort, never fatal).

Errors and timeouts are journalled with ``decision: "malformed"`` and the
error string — never excluded, never retried (locked constant).

Usage (one process per arm, under tmux, run from ``backend/``)::

    python -m experiments.harness.runner --arm single
    python -m experiments.harness.runner --arm mas

Pilot filters (G3/G4 only, not for the scored sweep)::

    python -m experiments.harness.runner --arm single --condition t0-fixed \
        --max-cases 5 --max-repeats 3 --no-git
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from app.agents.contract import RunContext
from experiments.config import DEFAULT_CONFIG, ExperimentConfig, config_for_model
from experiments.harness import git_sync
from experiments.harness.adapter import ArmAdapter
from experiments.harness.dfah_data import load_perturbation_cases, load_primary_cases
from experiments.harness.extraction import MALFORMED, extract_decision
from experiments.harness.journal import (
    Journal,
    completed_keys,
    journal_path,
    write_progress,
)
from experiments.harness.models import model_digest, ollama_version

logger = logging.getLogger("runner")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_progress_safely(config: ExperimentConfig, manifest: dict[str, Any]) -> None:
    """Progress reporting must never kill a runner (F2)."""
    try:
        write_progress(config.results_dir, manifest)
    except Exception as exc:
        logger.warning("progress.json update failed (non-fatal): %s", exc)


async def _warm_up(adapter: ArmAdapter, config: ExperimentConfig) -> None:
    """One discarded call after model load (PRD-A sweep rule)."""
    context = RunContext(run_id="warm-up", case_id="warm-up", seed=0, temperature=0.0)
    llm = adapter._model_factory(context)  # noqa: SLF001 — harness-internal
    await llm.ainvoke([HumanMessage(content="Reply with the single word: ready")])
    logger.info("warm-up call discarded")


async def execute_run(
    entry: dict[str, Any],
    adapter: ArmAdapter,
    case: dict[str, Any],
    config: ExperimentConfig,
    identity: dict[str, str],
) -> dict[str, Any]:
    """Run one planned entry and shape the journal record (never raises)."""
    context = RunContext(
        run_id=entry["run_id"],
        case_id=entry["case_id"],
        seed=entry["seed"],
        temperature=entry["temperature"],
        metadata={"arm": entry["arm"], "block": entry["block"]},
    )
    started_at = _utc_now()
    t0 = time.monotonic()
    error: str | None = None
    try:
        result = await asyncio.wait_for(
            adapter.arun(case, context), timeout=config.run_timeout_s
        )
        raw_output = result.output_text
        decision = extract_decision(raw_output)
        tool_calls = [c.name for c in result.tool_calls]
        agent_messages = result.agent_messages
        prompt_tokens = result.prompt_tokens
        completion_tokens = result.completion_tokens
    except Exception as exc:
        raw_output = ""
        decision = MALFORMED
        tool_calls = []
        agent_messages = prompt_tokens = completion_tokens = 0
        error = f"{type(exc).__name__}: {exc}"
    return {
        "run_id": entry["run_id"],
        "case_id": entry["case_id"],
        "arm": entry["arm"],
        "block": entry["block"],
        "condition": entry["condition"],
        "repeat_idx": entry["repeat_idx"],
        "seed": entry["seed"],
        "temperature": entry["temperature"],
        "model": config.model,
        "model_digest": identity["model_digest"],
        "ollama_version": identity["ollama_version"],
        "think": config.think,
        "started_at": started_at,
        "wall_clock_s": round(time.monotonic() - t0, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tool_calls": tool_calls,
        "agent_messages": agent_messages,
        "raw_output": raw_output,
        "decision": decision,
        "error": error,
    }


def _select(
    runs: list[dict[str, Any]],
    arm: str,
    condition: str | None,
    max_cases: int | None,
    max_repeats: int | None,
) -> list[dict[str, Any]]:
    """Filter the planned list for this arm (pilot filters optional)."""
    selected = [r for r in runs if r["arm"] == arm]
    if condition:
        selected = [r for r in selected if r["condition"] == condition]
    if max_repeats is not None:
        selected = [r for r in selected if r["repeat_idx"] < max_repeats]
    if max_cases is not None:
        keep = sorted({r["case_id"] for r in selected})[:max_cases]
        selected = [r for r in selected if r["case_id"] in keep]
    return selected


async def run_sweep(args: argparse.Namespace, config: ExperimentConfig) -> int:
    manifest = json.loads((config.results_dir / "manifest.json").read_text())
    cases = {c["alert_id"]: c for c in load_primary_cases() + load_perturbation_cases()}

    base_url = config.base_url(args.arm)
    identity = {
        "model_digest": model_digest(base_url, config.model),
        "ollama_version": ollama_version(base_url),
    }
    if identity["model_digest"] != manifest["model_digest"]:
        # F3: a digest drift means the weights are not the pre-registered
        # ones — refuse to journal runs against them unless explicitly told.
        message = (
            f"model digest on {base_url} ({identity['model_digest']}) differs "
            f"from manifest ({manifest['model_digest']})"
        )
        if not args.allow_digest_mismatch:
            raise SystemExit(
                f"ERROR: {message}. Re-pin the model or pass "
                "--allow-digest-mismatch to override (invalidates the "
                "pre-registration; note it in backend/experiments/CHANGELOG.md)."
            )
        logger.warning("%s — continuing due to --allow-digest-mismatch", message)

    planned = _select(
        manifest["runs"], args.arm, args.condition, args.max_cases, args.max_repeats
    )
    jpath = journal_path(config.results_dir, args.arm)
    done = completed_keys(jpath)
    todo = [
        r for r in planned
        if (r["case_id"], r["arm"], r["condition"], r["repeat_idx"]) not in done
    ]
    logger.info(
        "arm=%s planned=%d completed=%d todo=%d", args.arm, len(planned), len(done), len(todo)
    )
    if not todo:
        _write_progress_safely(config, manifest)
        return 0

    adapter = ArmAdapter(args.arm, config)
    await _warm_up(adapter, config)

    executed = 0
    with Journal(jpath) as journal:
        for entry in todo:
            record = await execute_run(entry, adapter, cases[entry["case_id"]], config, identity)
            journal.append(record)
            executed += 1
            _write_progress_safely(config, manifest)
            logger.info(
                "[%d/%d] %s -> %s (%.1fs)%s",
                executed, len(todo), entry["run_id"], record["decision"],
                record["wall_clock_s"],
                f" ERROR {record['error']}" if record["error"] else "",
            )
            if not args.no_git and executed % config.git_sync_every == 0:
                git_sync.sync_results(
                    f"results: {args.arm} checkpoint after {executed} runs this session",
                    results_dir=config.results_dir,
                )
    if not args.no_git:
        git_sync.sync_results(
            f"results: {args.arm} runner session end ({executed} runs)",
            results_dir=config.results_dir,
        )
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=["single", "mas"])
    parser.add_argument("--condition", default=None, help="pilot filter")
    parser.add_argument("--max-cases", type=int, default=None, help="pilot filter")
    parser.add_argument("--max-repeats", type=int, default=None, help="pilot filter")
    parser.add_argument("--no-git", action="store_true", help="disable git checkpoints")
    parser.add_argument(
        "--allow-digest-mismatch", action="store_true",
        help="run despite a model-digest drift from the manifest "
             "(invalidates the pre-registration; CHANGELOG note required)",
    )
    parser.add_argument(
        "--results-dir", type=Path, default=None,
        help="alternate results dir (pilots/G4 only; sweeps use the model's default)",
    )
    parser.add_argument(
        "--model", default=None,
        help="replication model tag (config.REPLICATION_MODELS); selects that "
             "model's own results dir and think handling",
    )
    args = parser.parse_args()
    config = config_for_model(args.model) if args.model else DEFAULT_CONFIG
    if args.results_dir is not None:
        config = dataclasses.replace(config, results_dir=args.results_dir)
    return asyncio.run(run_sweep(args, config))


if __name__ == "__main__":
    raise SystemExit(main())
