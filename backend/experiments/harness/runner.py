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
import random
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from app.agents.contract import RunContext
from experiments.config import (
    DEFAULT_CONFIG,
    MASTER_SEED,
    ExperimentConfig,
    config_for_model,
)
from experiments.harness import git_sync
from experiments.harness.adapter import ArmAdapter
from experiments.harness.env_fingerprint import EnvFingerprint
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


#: Conditions eligible for the ``prewarm`` cache policy: the deterministic
#: repeatability conditions, where cold-vs-warm server state is a confound.
PREWARM_CONDITIONS = ("t0-fixed", "pert-t0")


async def execute_run(
    entry: dict[str, Any],
    adapter: ArmAdapter,
    case: dict[str, Any],
    config: ExperimentConfig,
    identity: dict[str, str],
    env: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one planned entry and shape the journal record (never raises).

    Journal schema, harness v2 additions (all other fields as PRD-A):

    - ``node_outputs`` — MAS arm only: each node's output text keyed by node
      name in pipeline order (``orchestrator``, ``data``, ``policy_risk``,
      ``reporting``); ``null`` for the single arm and for errored runs.
    - ``think`` — the wire ``think`` parameter this sweep ran under:
      ``false`` / ``null`` (thinking-off, the sealed corpus) or ``true``
      (the thinking-on track). It is the per-run stamp that keeps the two
      tracks separable in any pooled read of the journals, exactly as
      ``ollama_version`` separates infra contexts. Under ``true`` the
      reasoning text is NOT in ``raw_output``: langchain-ollama keeps it on
      the separate ``reasoning_content`` channel, so ``raw_output``,
      ``decision`` and every metric still see the answer only.
    - ``cache_policy`` — the active cache-state policy for this sweep
      (``none`` | ``prewarm`` | ``shuffle``; see ``ExperimentConfig``).
    - ``env`` — environment fingerprint (``gpu_name``, ``gpu_driver``,
      ``gpu_vram_used_mb``, ``host_load_1m``, ``host_load_high``; GPU
      fields ``null`` where nvidia-smi is unavailable — see
      ``experiments.harness.env_fingerprint``), or ``null`` when no
      sampler was supplied.
    """
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
    node_outputs: dict[str, str] | None = None
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
        if result.node_outputs is not None:
            node_outputs = dict(result.node_outputs)  # order preserved
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
        "node_outputs": node_outputs,
        "cache_policy": config.cache_policy,
        "env": env,
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


def _cache_shuffle(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-repeat case-order shuffle (``cache_policy="shuffle"``).

    Within each (condition, repeat_idx) group the case order is permuted by
    an RNG seeded deterministically from ``MASTER_SEED`` and the group
    identity only — independent of model and arm, so both arms and all
    replication models execute the same shuffled order and stay comparable.
    Being a pure function of the manifest, a resumed runner replays the
    identical sequence (the resume set is key-based, so order never affects
    which runs execute — only when).
    """
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for run in runs:
        groups.setdefault((run["condition"], run["repeat_idx"]), []).append(run)
    shuffled: list[dict[str, Any]] = []
    for (condition, repeat_idx), group in groups.items():
        rng = random.Random(f"{MASTER_SEED}:{condition}:{repeat_idx}")
        group = list(group)
        rng.shuffle(group)
        shuffled.extend(group)
    return shuffled


async def _maybe_prewarm(
    entry: dict[str, Any],
    adapter: ArmAdapter,
    case: dict[str, Any],
    config: ExperimentConfig,
) -> None:
    """Send the run's exact opening prompt once and discard (best-effort).

    Only under ``cache_policy="prewarm"`` and only for the deterministic
    conditions (:data:`PREWARM_CONDITIONS`). A prewarm failure is logged and
    swallowed — the measured run must still execute and be journalled.
    """
    if config.cache_policy != "prewarm" or entry["condition"] not in PREWARM_CONDITIONS:
        return
    context = RunContext(
        run_id=f"{entry['run_id']}:prewarm",
        case_id=entry["case_id"],
        seed=entry["seed"],
        temperature=entry["temperature"],
        metadata={"arm": entry["arm"], "block": entry["block"], "prewarm": True},
    )
    try:
        await asyncio.wait_for(
            adapter.aprewarm(case, context), timeout=config.run_timeout_s
        )
    except Exception as exc:
        logger.warning("prewarm failed (non-fatal) for %s: %s", entry["run_id"], exc)


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

    manifest_policy = manifest.get("config", {}).get("cache_policy", "none")
    if manifest_policy != config.cache_policy:
        # v2: the policy is pre-registered in the manifest; a differing CLI
        # value is allowed for pilots but flagged loudly (comparability).
        logger.warning(
            "cache_policy %r differs from the manifest's pre-registered %r — "
            "runs journalled now are not comparable to runs under the other "
            "policy (note it in backend/experiments/CHANGELOG.md)",
            config.cache_policy, manifest_policy,
        )

    planned = _select(
        manifest["runs"], args.arm, args.condition, args.max_cases, args.max_repeats
    )
    if config.cache_policy == "shuffle":
        planned = _cache_shuffle(planned)
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

    env_fingerprint = EnvFingerprint(refresh_every=config.env_fingerprint_every)
    executed = 0
    with Journal(jpath) as journal:
        for entry in todo:
            await _maybe_prewarm(entry, adapter, cases[entry["case_id"]], config)
            record = await execute_run(
                entry, adapter, cases[entry["case_id"]], config, identity,
                env=env_fingerprint.sample(),
            )
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
        help="replication registry key (config.REPLICATION_MODELS; may differ "
             "from the served model tag, e.g. 'qwen2.5:7b-instruct@0.32.6' or "
             "the thinking-on track's 'qwen3.5:9b@think'); selects that key's "
             "own results dir, served tag and think handling",
    )
    parser.add_argument(
        "--cache-policy", default=None, choices=["none", "prewarm", "shuffle"],
        help="cache-state control (harness v2; default: the config/manifest "
             "value, 'none' = harness-v1 behaviour). 'prewarm' sends each "
             "t0-fixed/pert-t0 run's exact opening prompt once beforehand and "
             "discards it; 'shuffle' randomises per-repeat case order "
             "deterministically from MASTER_SEED. Pre-register the policy in "
             "the manifest; changing it mid-sweep invalidates comparability "
             "(see ExperimentConfig.cache_policy).",
    )
    args = parser.parse_args()
    config = config_for_model(args.model) if args.model else DEFAULT_CONFIG
    if args.results_dir is not None:
        config = dataclasses.replace(config, results_dir=args.results_dir)
    if args.cache_policy is not None:
        config = dataclasses.replace(config, cache_policy=args.cache_policy)
    return asyncio.run(run_sweep(args, config))


if __name__ == "__main__":
    raise SystemExit(main())
