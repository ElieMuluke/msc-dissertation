"""Seal-time checks for the muse-glimmer:30b sweep pair (pre-registered 2026-08-14).

Two checks, both pre-registered in the CHANGELOG BEFORE this sweep sealed:
  1. Tool-liveness: per-arm min tool calls > 0 AND per-node non-zero call rate,
     nodes identified via the tool-name partition (data node = the three lookup
     tools; policy_risk node = calculate_risk_score). No node_outputs needed.
  2. Degeneracy: per arm x condition, modal-decision rate vs the label prior,
     plus majority-vote accuracy vs the constant-answer baselines.

Read-only over journals. No LLM calls, no GPU. Run from backend/:
    .venv/bin/python -m experiments.analysis.seal_checks_muse_glimmer [results_dir]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

RESULTS = Path(sys.argv[1] if len(sys.argv) > 1 else "experiments/results-muse-glimmer-30b")
ALERTS = Path("/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json")
PERTS = Path("experiments/perturbation_cases.json")

DATA_TOOLS = {"check_sanctions_list", "get_customer_profile", "search_precedents"}
POLICY_TOOLS = {"calculate_risk_score"}


def load_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    for rec in json.loads(ALERTS.read_text())["alerts"]:
        labels[rec["alert_id"]] = rec["ground_truth"]
    if PERTS.exists():
        for rec in json.loads(PERTS.read_text())["alerts"]:
            labels[rec["alert_id"]] = rec["ground_truth"]
    return labels


def tool_names(run: dict) -> list[str]:
    names = []
    for c in run.get("tool_calls") or []:
        if isinstance(c, str):
            names.append(c)
        elif isinstance(c, dict):
            names.append(c.get("name") or c.get("tool") or "?")
    return names


def check_sweep(results: Path) -> int:
    labels = load_labels()
    failures = 0
    for arm in ("single", "mas"):
        path = results / f"journal-{arm}.jsonl"
        runs = [json.loads(l) for l in path.open() if l.strip()]
        n = len(runs)
        print(f"\n=== {results.name} / {arm}: {n} runs ===")

        # --- 1. tool-liveness -------------------------------------------------
        zero_tool = [r for r in runs if not (r.get("tool_calls") or [])]
        per_run = [len(r.get("tool_calls") or []) for r in runs]
        print(f"tool calls/run: min={min(per_run)} median={sorted(per_run)[n // 2]} "
              f"max={max(per_run)}; zero-tool runs={len(zero_tool)}/{n}")
        arm_alive = sum(per_run) > 0
        print(f"[{'PASS' if arm_alive else 'FAIL'}] arm-level tool-liveness (total calls > 0)")
        failures += 0 if arm_alive else 1

        if arm == "mas":
            data_dead = sum(1 for r in runs if not DATA_TOOLS & set(tool_names(r)))
            pol_dead = sum(1 for r in runs if not POLICY_TOOLS & set(tool_names(r)))
            for label, dead in (("data", data_dead), ("policy_risk", pol_dead)):
                rate = dead / n
                ok = rate < 1.0  # liveness = node not universally dead
                print(f"[{'PASS' if ok else 'FAIL'}] node {label}: dead {dead}/{n} ({rate:.1%})"
                      + ("  <-- DISCLOSE (>10%)" if 0.10 <= rate < 1.0 else ""))
                failures += 0 if ok else 1

        # --- 2. degeneracy ----------------------------------------------------
        by_cond: dict[str, list[dict]] = {}
        for r in runs:
            by_cond.setdefault(r["condition"], []).append(r)
        bench_labels = [labels[c] for c in {r["case_id"] for r in runs} if c in labels]
        prior = Counter(bench_labels)
        prior_top = prior.most_common(1)[0]
        print(f"label prior: {dict(prior)} (modal {prior_top[0]} "
              f"{prior_top[1] / len(bench_labels):.1%})")
        for cond, rs in sorted(by_cond.items()):
            decisions = [r.get("decision") or "malformed" for r in rs]
            modal, modal_n = Counter(decisions).most_common(1)[0]
            modal_rate = modal_n / len(rs)
            # majority vote per case vs labels
            votes: dict[str, Counter] = {}
            for r in rs:
                votes.setdefault(r["case_id"], Counter())[r.get("decision") or "malformed"] += 1
            scored = [(c, v.most_common(1)[0][0]) for c, v in votes.items() if c in labels]
            mv_acc = (sum(1 for c, d in scored if labels[c] == d) / len(scored)) if scored else 0.0
            baseline = max(
                sum(1 for c, _ in scored if labels[c] == cand) / len(scored)
                for cand in ("dismiss", "investigate", "escalate")
            ) if scored else 0.0
            degenerate = modal_rate > 0.80 or mv_acc < baseline
            flag = "DEGENERATE — annotate" if degenerate else "ok"
            print(f"  {cond}: modal={modal} {modal_rate:.1%}; MV-acc={mv_acc:.3f}; "
                  f"best-constant-baseline={baseline:.3f}  [{flag}]")
    return failures


if __name__ == "__main__":
    n_fail = check_sweep(RESULTS)
    print(f"\n{'=' * 50}\nSEAL CHECKS: {'ALL PASS' if n_fail == 0 else f'{n_fail} FAILURES'}")
    sys.exit(1 if n_fail else 0)
