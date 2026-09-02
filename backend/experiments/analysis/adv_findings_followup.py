"""Follow-up adversarial checks (see adv_findings_recompute.py).

J. granite4.1 vs qwen2.5-14b degeneracy side-by-side (exclusion consistency)
K. Run-level perturbation flips (is .tex:711 true at run level?)
L. lfm2.5-single filtered pass^1 (threat to gemma4 0.552 ranking)
M. gemma4 vs qwen3.5-budget, both excluding repeat_idx 0 (fair comparison)
N. Tier-3 token check for 7b/14b vs FINAL-RESULTS main table
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from experiments.analysis import metrics
from experiments.harness.dfah_data import (
    ground_truth, load_primary_cases, load_perturbation_cases)

BASE = Path("/home/eliem/Projects/ai/msc-dissertation/backend/experiments")
PRIMARY = ground_truth(load_primary_cases())
PERT_CASES = load_perturbation_cases()
PERT = ground_truth(PERT_CASES)
PERT_BASE = {c["alert_id"]: c["base_alert_id"] for c in PERT_CASES}
LOOKUP = {"search_precedents", "get_customer_profile", "check_sanctions_list"}
REAL = LOOKUP | {"calculate_risk_score"}


def load(dirname):
    rows = []
    for arm in ("single", "mas"):
        with open(BASE / dirname / f"journal-{arm}.jsonl") as f:
            rows += [json.loads(l) for l in f]
    return rows


def cell(rows, arm, cond):
    g = defaultdict(list)
    for r in rows:
        if r["arm"] == arm and r["condition"] == cond:
            g[r["case_id"]].append(r)
    return g


def tier1(groups, labels, exclude=None):
    per_case, units = {}, []
    for cid, runs in sorted(groups.items()):
        ds = [r["decision"] for r in runs
              if not (exclude and r["run_id"] in exclude)]
        if ds:
            per_case[cid] = sum(d == labels[cid] for d in ds) / len(ds)
            units.append(ds)
    p1 = sum(per_case.values()) / len(per_case)
    alpha = metrics.krippendorff_alpha(units)
    return p1, alpha, per_case


def main():
    P = print
    P("=" * 78)
    P("J. GRANITE4.1 vs QWEN2.5-14B — degeneracy criteria side-by-side, t07-varied")
    P("   (granite exclusion criteria: modal share, vs 0.520 baseline, pert MV)")
    P("=" * 78)
    for name, d in (("granite4.1-8b", "results-granite4.1-8b"),
                    ("qwen2.5-14b", "results-qwen2.5-14b"),
                    ("qwen3.5-9b", "results")):
        rows = load(d)
        for arm in ("single", "mas"):
            g = cell(rows, arm, "t07-varied")
            dist = Counter(r["decision"] for runs in g.values() for r in runs)
            tot = sum(dist.values())
            modal, mshare = dist.most_common(1)[0]
            p1, alpha, _ = tier1(g, PRIMARY)
            mv_hits = sum(
                metrics.majority_vote([r["decision"] for r in runs])[0]
                == PRIMARY[cid] for cid, runs in g.items())
            # pert MV readout t0
            gb, gp = cell(rows, arm, "t0-fixed"), cell(rows, arm, "pert-t0")
            moved = sum(
                metrics.majority_vote([r["decision"] for r in gb[b]])[0]
                != metrics.majority_vote([r["decision"] for r in gp[p]])[0]
                for p, b in PERT_BASE.items() if p in gp and b in gb)
            P(f"{name:14s} {arm:6s} modal={modal}:{mshare/tot:.1%} "
              f"pass^1={p1:.3f} (vs 0.520 baseline: "
              f"{'BELOW' if p1 < 0.520 else 'above'}) alpha={alpha:.3f} "
              f"MVacc={mv_hits}/50 pert-t0 MV moved {moved}/10")

    P()
    P("=" * 78)
    P("K. RUN-LEVEL PERTURBATION FLIPS (.tex:711: 'flipped cases flipped")
    P("   decisions at T>0 in both arms of every model')")
    P("   frac of pert-t05/t10 runs whose decision != base-case t07 modal")
    P("=" * 78)
    sweeps = (("qwen3.5-9b", "results"), ("qwen2.5-7b", "results-qwen2.5-7b"),
              ("qwen2.5-14b", "results-qwen2.5-14b"), ("gemma4", "results-gemma4"),
              ("granite4.1", "results-granite4.1-8b"))
    for name, d in sweeps:
        rows = load(d)
        for arm in ("single", "mas"):
            gb = cell(rows, arm, "t07-varied")
            flips = tot = 0
            cases_with_flip = 0
            for pcond in ("pert-t05", "pert-t10"):
                gp = cell(rows, arm, pcond)
                for pid, bid in PERT_BASE.items():
                    if pid not in gp or bid not in gb:
                        continue
                    bmv = metrics.majority_vote(
                        [r["decision"] for r in gb[bid]])[0]
                    f = sum(r["decision"] != bmv for r in gp[pid])
                    flips += f
                    tot += len(gp[pid])
                    cases_with_flip += f > 0
            P(f"{name:12s} {arm:6s} run-level flips {flips}/{tot} "
              f"({flips/tot:.1%}); pert-case-conditions with >=1 flip: "
              f"{cases_with_flip}/20")

    P()
    P("=" * 78)
    P("L. lfm2.5-think SINGLE filtered pass^1 (can it threaten gemma4 0.552?)")
    P("=" * 78)
    rows = load("results-lfm2.5-8b-thinking")
    g = cell(rows, "single", "t07-varied")
    p1, alpha, _ = tier1(g, PRIMARY)
    bad = {r["run_id"] for runs in g.values() for r in runs
           if not (r.get("tool_calls") or [])
           or (set(r.get("tool_calls") or []) - REAL)}
    p1f, alphaf, _ = tier1(g, PRIMARY, exclude=bad)
    P(f"lfm2.5-single t07: committed pass^1={p1:.3f}; excluding "
      f"{len(bad)} zero-tool/hallucinated-tool runs -> {p1f:.3f}")

    P()
    P("=" * 78)
    P("M. FAIR repeat-0 EXCLUSION: gemma4-single vs budget-single, both filtered")
    P("=" * 78)
    g4 = cell(load("results-gemma4"), "single", "t07-varied")
    qb = cell(load("results-qwen3.5-9b-thinking-budget"), "single", "t07-varied")
    for lab, g in (("gemma4", g4), ("budget", qb)):
        ex = {r["run_id"] for runs in g.values() for r in runs
              if r["repeat_idx"] == 0}
        p1_all, _, _ = tier1(g, PRIMARY)
        p1_ex, _, _ = tier1(g, PRIMARY, exclude=ex)
        P(f"{lab:8s} all-15 pass^1={p1_all:.4f}  repeats-1..14 pass^1={p1_ex:.4f}")

    P()
    P("=" * 78)
    P("N. TIER-3 TOKENS/RUN t07 — journal recompute vs committed reports vs")
    P("   FINAL-RESULTS main table ('3.0k->~7.5k' 7b, '~4.2k->~7.7k' 14b)")
    P("=" * 78)
    for name, d in (("qwen2.5-7b", "results-qwen2.5-7b"),
                    ("qwen2.5-14b", "results-qwen2.5-14b")):
        rows = load(d)
        for arm in ("single", "mas"):
            g = cell(rows, arm, "t07-varied")
            toks = [r["prompt_tokens"] + r["completion_tokens"]
                    for runs in g.values() for r in runs]
            P(f"{name:12s} {arm:6s} journal tokens/run = {sum(toks)/len(toks):.1f}")


if __name__ == "__main__":
    main()
