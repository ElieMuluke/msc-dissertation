"""Manifest generation — the full planned run list, pre-generated seeds,
model digest, config hash and git sha, written before run 1.

The runner only ever consumes this file; seeds are consumed by index so a
resume reproduces the exact planned sequence. Varied seeds are drawn from
``MASTER_SEED``; the same seed is shared by both arms for a given
(condition, case, repeat) so the arm comparison never confounds with the
seed schedule.

Usage::

    python -m experiments.harness.manifest [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import time
from pathlib import Path
from typing import Any

from experiments.config import (
    ARMS,
    CONDITIONS,
    DEFAULT_CONFIG,
    MAS_TOOL_PARTITION,
    MASTER_SEED,
    REPO_ROOT,
    ExperimentConfig,
    config_for_model,
)
from experiments.harness import journal
from experiments.harness.dfah_data import load_perturbation_cases, load_primary_cases
from experiments.harness.models import model_digest, model_show, ollama_version
from experiments.mas.prompts import MAS_PROMPTS
from experiments.single.prompts import SYSTEM_PROMPT as SINGLE_PROMPT


def _sha256(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _git_sha(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return out.stdout.strip()
    except Exception:
        return None


def planned_runs(config: ExperimentConfig = DEFAULT_CONFIG) -> list[dict[str, Any]]:
    """Deterministically expand the run matrix (2,300 entries) with seeds."""
    primary_ids = [c["alert_id"] for c in load_primary_cases()]
    pert_ids = [c["alert_id"] for c in load_perturbation_cases()]
    rng = random.Random(MASTER_SEED)
    runs: list[dict[str, Any]] = []
    for cond in CONDITIONS:
        case_ids = primary_ids if cond.block == "primary" else pert_ids
        for case_id in case_ids:
            for repeat_idx in range(cond.repeats):
                seed = cond.fixed_seed if cond.fixed_seed is not None else rng.randrange(2**31)
                for arm in ARMS:
                    runs.append(
                        {
                            "run_id": f"{arm}:{case_id}:{cond.name}:{repeat_idx}",
                            "arm": arm,
                            "case_id": case_id,
                            "block": cond.block,
                            "condition": cond.name,
                            "repeat_idx": repeat_idx,
                            "seed": seed,
                            "temperature": cond.temperature,
                        }
                    )
    return runs


def config_record(config: ExperimentConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    """Everything hash-worthy about the configuration, prompts included."""
    return {
        "model": config.model,
        "think": config.think,
        "num_ctx": config.num_ctx,
        "num_predict": config.num_predict,
        "max_iterations": config.max_iterations,
        "run_timeout_s": config.run_timeout_s,
        "master_seed": MASTER_SEED,
        "conditions": [
            {
                "name": c.name,
                "block": c.block,
                "temperature": c.temperature,
                "repeats": c.repeats,
                "fixed_seed": c.fixed_seed,
            }
            for c in CONDITIONS
        ],
        "mas_tool_partition": {k: list(v) for k, v in MAS_TOOL_PARTITION.items()},
        "prompts": {
            "single_system": SINGLE_PROMPT,
            **{f"mas_{k}": v for k, v in MAS_PROMPTS.items()},
        },
        # R2: sampling params are NOT sent by the harness; the server applies
        # its defaults. Recorded numerically (Ollama documented defaults for
        # the pinned server version) so the manifest carries the effective
        # values; any modelfile override appears in manifest["model_show"].
        "sampling": {
            "set_by_harness": False,
            "top_p": {"server_default": 0.9},
            "top_k": {"server_default": 40},
            "min_p": {"server_default": 0.0},
        },
    }


def build_manifest(config: ExperimentConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    """Assemble the full manifest, querying the arm-A server for model identity."""
    base_url = config.base_url("single")
    runs = planned_runs(config)
    cfg = config_record(config)
    totals = {arm: sum(1 for r in runs if r["arm"] == arm) for arm in ARMS}
    return {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": config.model,
        "model_digest": model_digest(base_url, config.model),
        "model_show": model_show(base_url, config.model),
        "ollama_version": ollama_version(base_url),
        "git_sha": _git_sha(REPO_ROOT),
        "config": cfg,
        "config_hash": _sha256(cfg),
        "totals": totals,
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing manifest (pre-launch only)")
    parser.add_argument(
        "--model", default=DEFAULT_CONFIG.model,
        help="replication model tag (must be in config.REPLICATION_MODELS); "
             "selects that model's own results dir",
    )
    args = parser.parse_args()
    config = config_for_model(args.model)
    results_dir = config.results_dir
    target = results_dir / "manifest.json"
    journals = [journal.journal_path(results_dir, arm) for arm in ARMS]
    if target.exists() and any(p.exists() for p in journals) and not args.force:
        raise SystemExit(
            "manifest exists and journals are non-empty; regenerating now would "
            "invalidate the pre-registration (use --force only pre-launch)."
        )
    manifest = build_manifest(config)
    results_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {target}: {len(manifest['runs'])} planned runs, "
          f"model={config.model}, config_hash={manifest['config_hash'][:12]}, "
          f"digest={manifest['model_digest'][:20]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
