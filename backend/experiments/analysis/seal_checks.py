"""Model-agnostic seal-time checks for any sweep pair (generalised 2026-08-18
from ``seal_checks_muse_glimmer.py``, which is kept as-is for provenance of
the muse-glimmer:30b seal).

Two checks, both pre-registered in the CHANGELOG before the muse-glimmer
seal and applied unchanged to any results dir:

  1. Tool-liveness: per-arm min tool calls > 0 AND per-node non-zero call
     rate, nodes identified via the tool-name partition (data node = the
     three lookup tools; policy_risk node = calculate_risk_score). Includes
     the severed-channel detector: a node that calls its tools but emits an
     EMPTY output downstream (found on muse-glimmer thinking-off, 226/1150
     empty data-node outputs at 8.69 calls/run, audit 2026-08-17).
  2. Degeneracy: per arm x condition, modal-decision rate vs the label
     prior, plus majority-vote accuracy vs the constant-answer baselines.
     Majority ties break by canonical OUTCOMES order (must match
     ``analysis/metrics.py:majority_vote``).

Read-only over journals. No LLM calls, no GPU. Run from backend/::

    .venv/bin/python -m experiments.analysis.seal_checks <results_dir>

``<results_dir>`` may be absolute or relative to the CWD (e.g.
``experiments/results-granite4.1-8b``).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from collections import Counter
from pathlib import Path

ALERTS = Path(
    "/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json"
)
PERTS = Path(__file__).resolve().parents[1] / "perturbation_cases.json"

DATA_TOOLS = {"check_sanctions_list", "get_customer_profile", "search_precedents"}
POLICY_TOOLS = {"calculate_risk_score"}

OUTCOMES = ("escalate", "investigate", "dismiss", "malformed")


def load_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    for rec in json.loads(ALERTS.read_text())["alerts"]:
        labels[rec["alert_id"]] = rec["ground_truth"]
    if PERTS.exists():
        for rec in json.loads(PERTS.read_text())["alerts"]:
            labels[rec["alert_id"]] = rec["ground_truth"]
    return labels


def majority(decisions: list[str]) -> str:
    """Modal decision, ties broken by canonical OUTCOMES order.

    Must match ``analysis/metrics.py:majority_vote``. Using
    ``Counter.most_common`` here instead broke one perturbation cell
    (audit 2026-08-17).
    """
    counts = Counter(decisions)
    top = max(counts.values())
    return next(o for o in OUTCOMES if counts.get(o, 0) == top)


def tool_names(run: dict) -> list[str]:
    names = []
    for c in run.get("tool_calls") or []:
        if isinstance(c, str):
            names.append(c)
        elif isinstance(c, dict):
            names.append(c.get("name") or c.get("tool") or "?")
    return names


def check_sweep(results: Path) -> int:
    """Run both seal checks over ``results``; returns the failure count."""
    labels = load_labels()
    failures = 0
    for arm in ("single", "mas"):
        path = results / f"journal-{arm}.jsonl"
        if not path.exists():
            print(f"\n=== {results.name} / {arm}: NO JOURNAL ({path}) ===")
            print("[FAIL] journal missing")
            failures += 1
            continue
        runs = [json.loads(l) for l in path.open() if l.strip()]
        n = len(runs)
        print(f"\n=== {results.name} / {arm}: {n} runs ===")
        if n == 0:
            print("[FAIL] journal empty")
            failures += 1
            continue

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

            # Call-counting alone misses a severed channel: a node can call its tools
            # and still emit nothing downstream. Found on muse-glimmer thinking-off
            # (226/1150 empty data-node outputs at 8.69 calls/run), audit 2026-08-17.
            severed = set()
            for label in ("data", "policy_risk", "reporting"):
                empty = [
                    r for r in runs
                    if isinstance(r.get("node_outputs"), dict)
                    and not (r["node_outputs"].get(label) or "").strip()
                ]
                rate = len(empty) / n
                ok = rate < 0.10
                severed |= {id(r) for r in empty}
                print(f"[{'PASS' if ok else 'DISCLOSE'}] node {label}: EMPTY output "
                      f"{len(empty)}/{n} ({rate:.1%}) despite tool calls")
            if severed:
                broken = [r for r in runs if id(r) in severed]
                dist = Counter(r.get("decision") or "malformed" for r in broken)
                print(f"          severed-channel runs {len(broken)}/{n} "
                      f"({len(broken) / n:.1%}); decisions {dict(dist)}")

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
            scored = [(c, majority(list(v.elements()))) for c, v in votes.items() if c in labels]
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir", type=Path,
        help="a sweep's results directory (contains journal-single.jsonl / "
             "journal-mas.jsonl), e.g. experiments/results-granite4.1-8b",
    )
    args = parser.parse_args(argv)
    if not args.results_dir.exists():
        parser.error(f"results dir does not exist: {args.results_dir}")
    n_fail = check_sweep(args.results_dir)
    print(f"\n{'=' * 50}\nSEAL CHECKS: {'ALL PASS' if n_fail == 0 else f'{n_fail} FAILURES'}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
