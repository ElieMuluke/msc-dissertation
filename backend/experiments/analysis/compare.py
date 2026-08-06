"""Cross-model comparison: Tier 1 side by side across replication sweeps.

Reads each model's results dir (manifest + journals) and tabulates the
pre-registered Tier 1 metrics per arm × condition, one column block per
model. qwen3.5:9b is the headline pre-registered result; the other models
are robustness replications of the identical design (same cases, seeds,
conditions, metrics — see CHANGELOG 2026-08-06).

Usage (from ``backend/``)::

    python -m experiments.analysis.compare \
        [--models qwen3.5:9b qwen2.5:7b-instruct mistral-nemo:latest] \
        [--out experiments/cross-model-comparison.md]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiments.analysis import metrics
from experiments.config import ARMS, EXPERIMENTS_DIR, REPLICATION_MODELS, config_for_model
from experiments.harness.dfah_data import (
    ground_truth,
    load_perturbation_cases,
    load_primary_cases,
)
from experiments.harness.journal import journal_path, read_journal

TIER1_KEYS = ("pass^1", "pass^5", "pass^15", "DAR", "krippendorff_alpha", "flip_rate")
PRIMARY_CONDITIONS = ("t0-fixed", "t07-varied")


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def model_summaries(model: str, labels: dict[str, str]) -> dict[tuple[str, str], dict[str, Any]]:
    """Tier-1-relevant summaries for one model's results dir (may be partial)."""
    results_dir = config_for_model(model).results_dir
    out: dict[tuple[str, str], dict[str, Any]] = {}
    journals = {arm: read_journal(journal_path(results_dir, arm)) for arm in ARMS}
    for arm in ARMS:
        for cond in PRIMARY_CONDITIONS:
            groups = metrics.group_case_runs(journals[arm], arm, cond)
            complete = {c: g for c, g in groups.items() if len(g.decisions) >= 2}
            out[(arm, cond)] = (
                metrics.condition_summary(complete, labels) if complete else {"cases": 0}
            )
    return out


def build_comparison(models: list[str], out_path: Path) -> Path:
    labels = {**ground_truth(load_primary_cases()), **ground_truth(load_perturbation_cases())}
    per_model: dict[str, dict] = {}
    status: dict[str, str] = {}
    for model in models:
        results_dir = config_for_model(model).results_dir
        manifest_path = results_dir / "manifest.json"
        if not manifest_path.exists():
            status[model] = "no manifest — sweep not prepared"
            continue
        manifest = json.loads(manifest_path.read_text())
        done = sum(len(read_journal(journal_path(results_dir, arm))) for arm in ARMS)
        status[model] = f"{done}/{sum(manifest['totals'].values())} runs journalled"
        per_model[model] = model_summaries(model, labels)

    lines = [
        "# Cross-model comparison — Tier 1 (pre-registered metrics)",
        "",
        "Headline pre-registered result: `qwen3.5:9b`. Other models are",
        "robustness replications of the identical design (same cases, seed",
        "schedule, conditions, metrics). pass^k is agreement with benchmark",
        "authors' labels; malformed outputs are included in every metric.",
        "",
        "## Sweep status",
        "",
    ]
    lines += [f"- `{m}`: {status[m]}" for m in models]
    lines.append("")

    for cond in PRIMARY_CONDITIONS:
        lines.append(f"## Condition `{cond}`")
        lines.append("")
        headers = ["arm", "metric"] + [f"`{m}`" for m in models]
        rows = []
        for arm in ARMS:
            for key in TIER1_KEYS:
                row = [arm, key]
                for m in models:
                    summary = per_model.get(m, {}).get((arm, cond), {"cases": 0})
                    row.append(
                        _fmt(summary.get(key)) if summary.get("cases", 0) else "—"
                    )
                rows.append(row)
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")
        lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
        lines.append("")

    out_path.write_text("\n".join(lines))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=list(REPLICATION_MODELS))
    parser.add_argument(
        "--out", type=Path, default=EXPERIMENTS_DIR / "cross-model-comparison.md"
    )
    args = parser.parse_args()
    print(f"wrote {build_comparison(args.models, args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
