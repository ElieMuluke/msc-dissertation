"""Adversarial verification of docs/DEFECT-IMPACT-ANALYSIS.md conclusions.

Read-only over sealed journals. Recomputes, from journals alone:
  A. Tier-1 t07-varied metrics for the four headline sweeps (+0.32.6 replicas)
  B. Per-label pass rates + decision distributions (ANALYSIS-INSIGHTS items 1-3)
  C. Escalate-case table (5 cases x 4 models)
  D. Majority-vote accuracies (item 5)
  E. Zero-tool / node-dead run tracing into headline cells (C2)
  F. gemma4-single 0.552 robustness + bootstrap vs qwen3.5-budget 0.548 (C3)
  G. lfm2.5-thinking & qwen3.5-budget Tier-1 excluding node-dead MAS runs (C4)
  H. Perturbation-control readout (base MV vs pert MV) for all headline sweeps
  I. Token-ratio range check (which sweeps produce the committed 1.8-3.1x range)

Run from backend/: ./.venv/bin/python experiments/analysis/adv_findings_recompute.py
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from experiments.analysis import metrics
from experiments.harness.dfah_data import (
    ground_truth, load_primary_cases, load_perturbation_cases)

BASE = Path("/home/eliem/Projects/ai/msc-dissertation/backend/experiments")

SWEEPS = {
    "qwen3.5-9b@0.31.1": "results",
    "qwen3.5-9b@0.32.6": "results-qwen3.5-9b-ollama0326",
    "qwen2.5-7b@0.31.1": "results-qwen2.5-7b",
    "qwen2.5-7b@0.32.6": "results-qwen2.5-7b-ollama0326",
    "qwen2.5-14b@0.31.1": "results-qwen2.5-14b",
    "qwen2.5-14b@0.32.6": "results-qwen2.5-14b-ollama0326",
    "gemma4@0.32.6": "results-gemma4",
    "lfm2.5-8b-think": "results-lfm2.5-8b-thinking",
    "qwen3.5-budget": "results-qwen3.5-9b-thinking-budget",
}
HEADLINE = ["qwen3.5-9b@0.31.1", "qwen2.5-7b@0.31.1", "qwen2.5-14b@0.31.1",
            "gemma4@0.32.6"]

LOOKUP_TOOLS = {"search_precedents", "get_customer_profile", "check_sanctions_list"}
POLICY_TOOL = "calculate_risk_score"

PRIMARY = ground_truth(load_primary_cases())
PERT_CASES = load_perturbation_cases()
PERT = ground_truth(PERT_CASES)
PERT_BASE = {c["alert_id"]: c["base_alert_id"] for c in PERT_CASES}
LABELS = {**PRIMARY, **PERT}


def load(dirname):
    rows = []
    for arm in ("single", "mas"):
        p = BASE / dirname / f"journal-{arm}.jsonl"
        with open(p) as f:
            for line in f:
                rows.append(json.loads(line))
    return rows


def cell(rows, arm, cond):
    g = defaultdict(list)
    for r in rows:
        if r["arm"] == arm and r["condition"] == cond:
            g[r["case_id"]].append(r)
    for v in g.values():
        v.sort(key=lambda r: r["repeat_idx"])
    return g


def tier1(groups, labels, exclude=None):
    """pass^1 (mean over cases of c/n), DAR, alpha over case units.
    exclude: set of run_ids to drop before computing."""
    per_case, units = {}, []
    dropped = 0
    for cid, runs in sorted(groups.items()):
        ds = [r["decision"] for r in runs
              if not (exclude and r["run_id"] in exclude)]
        dropped += len(runs) - len(ds)
        if not ds:
            continue
        per_case[cid] = sum(1 for d in ds if d == labels[cid]) / len(ds)
        units.append(ds)
    p1 = sum(per_case.values()) / len(per_case)
    dar_vals = [metrics.decision_agreement_rate(u) for u in units if len(u) >= 2]
    dar = sum(dar_vals) / len(dar_vals)
    alpha = metrics.krippendorff_alpha(units)
    return {"pass1": p1, "DAR": dar, "alpha": alpha, "n_cases": len(units),
            "dropped_runs": dropped, "per_case": per_case}


def per_label(groups, labels):
    out = {}
    for lab in ("dismiss", "investigate", "escalate"):
        cids = [c for c in groups if labels[c] == lab]
        num = den = 0
        for c in cids:
            ds = [r["decision"] for r in groups[c]]
            num += sum(1 for d in ds if d == lab)
            den += len(ds)
        out[lab] = (num, den, num / den if den else None)
    return out


def mv_acc(groups, labels):
    hits = 0
    for cid, runs in groups.items():
        mv, _ = metrics.majority_vote([r["decision"] for r in runs])
        hits += mv == labels[cid]
    return hits, len(groups)


def node_dead_runs(rows):
    """MAS run_ids with dead policy node / dead data node / zero tools."""
    pol, dat, zero = set(), set(), set()
    for r in rows:
        if r["arm"] != "mas":
            continue
        tc = r.get("tool_calls") or []
        if POLICY_TOOL not in tc:
            pol.add(r["run_id"])
        if not (set(tc) & LOOKUP_TOOLS):
            dat.add(r["run_id"])
        if not tc:
            zero.add(r["run_id"])
    return pol, dat, zero


def boot_ci(vals, n=10000, seed=7):
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(vals, k=len(vals))) / len(vals)
                   for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def boot_diff_paired(a, b, n=10000, seed=7):
    """a, b: dict case->value on same keys. CI of mean(a-b) resampling cases."""
    keys = sorted(set(a) & set(b))
    diffs = [a[k] - b[k] for k in keys]
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs)
                   for _ in range(n))
    m = sum(diffs) / len(diffs)
    return m, means[int(0.025 * n)], means[int(0.975 * n)]


def boot_diff_unpaired(a, b, n=10000, seed=7):
    rng = random.Random(seed)
    av, bv = list(a.values()), list(b.values())
    means = sorted(
        sum(rng.choices(av, k=len(av))) / len(av)
        - sum(rng.choices(bv, k=len(bv))) / len(bv)
        for _ in range(n))
    m = sum(av) / len(av) - sum(bv) / len(bv)
    return m, means[int(0.025 * n)], means[int(0.975 * n)]


def main():
    data = {k: load(v) for k, v in SWEEPS.items()}
    P = print

    P("=" * 78)
    P("A. TIER-1 RECOMPUTE, t07-varied (compare to committed analysis-report.md)")
    P("=" * 78)
    t1 = {}
    for name in SWEEPS:
        for arm in ("single", "mas"):
            g = cell(data[name], arm, "t07-varied")
            t1[(name, arm)] = tier1(g, PRIMARY)
            r = t1[(name, arm)]
            P(f"{name:22s} {arm:6s} pass^1={r['pass1']:.3f} DAR={r['DAR']:.3f} "
              f"alpha={r['alpha']:.3f} cases={r['n_cases']}")

    P()
    P("=" * 78)
    P("B. PER-LABEL RATES + DECISION DISTRIBUTIONS, t07-varied")
    P("=" * 78)
    for name in HEADLINE:
        for arm in ("single", "mas"):
            g = cell(data[name], arm, "t07-varied")
            pl = per_label(g, PRIMARY)
            dist = Counter(r["decision"] for runs in g.values() for r in runs)
            P(f"{name:22s} {arm:6s} "
              + " ".join(f"{l}={v[2]:.3f}({v[0]}/{v[1]})" for l, v in pl.items())
              + f"  dist={dict(dist)}")

    P()
    P("=" * 78)
    P("C. ESCALATE-CASE TABLE (escalations /15 at t07, single|mas)")
    P("=" * 78)
    tab_cases = ["TXN-2025-002", "TXN-2025-004", "TXN-2025-015",
                 "TXN-2025-039", "TXN-2025-049"]
    for cid in tab_cases:
        row = []
        for name in HEADLINE:
            v = []
            for arm in ("single", "mas"):
                g = cell(data[name], arm, "t07-varied")
                v.append(sum(1 for r in g[cid] if r["decision"] == "escalate"))
            row.append(f"{v[0]}|{v[1]}")
        P(f"{cid}: " + "  ".join(f"{n.split('@')[0]}={x}"
                                 for n, x in zip(HEADLINE, row)))

    P()
    P("=" * 78)
    P("D. MAJORITY-VOTE ACCURACY x/50, t07-varied (item 5: 7b-mas 27, g4-single 30)")
    P("=" * 78)
    for name in HEADLINE + ["lfm2.5-8b-think", "qwen3.5-budget"]:
        for arm in ("single", "mas"):
            g = cell(data[name], arm, "t07-varied")
            h, n = mv_acc(g, PRIMARY)
            P(f"{name:22s} {arm:6s} MV acc = {h}/{n}")

    P()
    P("=" * 78)
    P("E. ZERO-TOOL / POCKET RUNS traced into headline cells (C2)")
    P("=" * 78)
    for name in HEADLINE:
        rows = data[name]
        zt = [r for r in rows if not (r.get("tool_calls") or [])]
        P(f"\n{name}: {len(zt)} zero-tool runs total")
        for r in zt:
            in_table = r["case_id"] in tab_cases and r["condition"] == "t07-varied"
            lab = LABELS.get(r["case_id"], "?")
            P(f"  {r['run_id']:44s} label={lab:11s} decision={r['decision']!s:12s}"
              f" {'<== IN ESCALATE TABLE CELL' if in_table else ''}")
        # max pass^1 shift if all zero-tool t07 primary runs flipped
        zt07 = [r for r in zt if r["condition"] == "t07-varied"]
        for arm in ("single", "mas"):
            k = sum(1 for r in zt07 if r["arm"] == arm)
            if k:
                P(f"  max pass^1 shift ({arm}, t07): +/-{k}/750 = {k/750:.4f}")
        # per-label escalate rate max shift
        esc_cases = {c for c, l in PRIMARY.items() if l == "escalate"}
        for arm in ("single", "mas"):
            k = sum(1 for r in zt07 if r["arm"] == arm and r["case_id"] in esc_cases)
            if k:
                P(f"  of which on escalate-labelled cases ({arm}): {k} "
                  f"-> max escalate-rate shift {k}/225 = {k/225:.4f}")

    P()
    P("=" * 78)
    P("F. C3: gemma4-single 0.552 robustness + gap vs qwen3.5-budget 0.548")
    P("=" * 78)
    g4 = cell(data["gemma4@0.32.6"], "single", "t07-varied")
    base = tier1(g4, PRIMARY)
    P(f"gemma4-single t07 pass^1 recomputed = {base['pass1']:.4f}")
    # exclude repeat 0
    ex_r0 = {r["run_id"] for runs in g4.values() for r in runs
             if r["repeat_idx"] == 0}
    r = tier1(g4, PRIMARY, exclude=ex_r0)
    P(f"  excluding repeat_idx 0 (n-drop {r['dropped_runs']}): pass^1={r['pass1']:.4f}")
    # exclude zero-tool
    ex_zt = {r["run_id"] for runs in g4.values() for r in runs
             if not (r.get("tool_calls") or [])}
    r = tier1(g4, PRIMARY, exclude=ex_zt)
    P(f"  excluding zero-tool runs (n-drop {r['dropped_runs']}): pass^1={r['pass1']:.4f}")
    # exclude malformed
    ex_mal = {r["run_id"] for runs in g4.values() for r in runs
              if r["decision"] not in ("dismiss", "investigate", "escalate")}
    r = tier1(g4, PRIMARY, exclude=ex_mal)
    P(f"  excluding malformed (n-drop {r['dropped_runs']}): pass^1={r['pass1']:.4f}")
    # errors?
    errs = [r for runs in g4.values() for r in runs if r.get("error")]
    P(f"  runs with error field set: {len(errs)}")

    qb = cell(data["qwen3.5-budget"], "single", "t07-varied")
    qbt = tier1(qb, PRIMARY)
    P(f"\nqwen3.5-budget-single t07 pass^1 recomputed = {qbt['pass1']:.4f}")
    # hallucinated decision-verb tool calls in budget single
    real = LOOKUP_TOOLS | {POLICY_TOOL}
    hall = {r["run_id"] for runs in qb.values() for r in runs
            if set(r.get("tool_calls") or []) - real}
    P(f"  budget-single runs calling nonexistent tools: {len(hall)}")
    r = tier1(qb, PRIMARY, exclude=hall)
    P(f"  excluding those: pass^1={r['pass1']:.4f}")

    m, lo, hi = boot_diff_paired(base["per_case"], qbt["per_case"])
    P(f"\ngap gemma4 - budget (paired by case): {m:+.4f}, 95% CI [{lo:+.4f}, {hi:+.4f}]")
    m, lo, hi = boot_diff_unpaired(base["per_case"], qbt["per_case"])
    P(f"gap (unpaired bootstrap):              {m:+.4f}, 95% CI [{lo:+.4f}, {hi:+.4f}]")
    glo, ghi = boot_ci(list(base["per_case"].values()))
    blo, bhi = boot_ci(list(qbt["per_case"].values()))
    P(f"gemma4 0.552 own CI [{glo:.3f},{ghi:.3f}]; budget 0.548 own CI [{blo:.3f},{bhi:.3f}]")

    P()
    P("=" * 78)
    P("G. C4 SEVERITY: thinking sweeps, Tier-1 excluding node-dead MAS runs")
    P("=" * 78)
    for name in ("lfm2.5-8b-think", "qwen3.5-budget"):
        rows = data[name]
        pol, dat, zero = node_dead_runs(rows)
        bad = pol | dat | zero
        g = cell(rows, "mas", "t07-varied")
        committed = tier1(g, PRIMARY)
        filtered = tier1(g, PRIMARY, exclude=bad)
        P(f"\n{name} MAS t07: node-dead runs total (all conds): pol={len(pol)} "
          f"data={len(dat)} zero={len(zero)} union={len(bad)}")
        P(f"  committed-equivalent: pass^1={committed['pass1']:.3f} "
          f"DAR={committed['DAR']:.3f} alpha={committed['alpha']:.3f}")
        P(f"  excluding node-dead:  pass^1={filtered['pass1']:.3f} "
          f"DAR={filtered['DAR']:.3f} alpha={filtered['alpha']:.3f} "
          f"(dropped {filtered['dropped_runs']} of 750 runs, "
          f"{filtered['n_cases']} cases remain)")
        # arm-diff shift: single per-case minus filtered mas per-case
        s = tier1(cell(rows, "single", "t07-varied"), PRIMARY)
        m0, lo0, hi0 = boot_diff_paired(s["per_case"], committed["per_case"])
        keys = set(s["per_case"]) & set(filtered["per_case"])
        m1, lo1, hi1 = boot_diff_paired(
            {k: s["per_case"][k] for k in keys},
            {k: filtered["per_case"][k] for k in keys})
        P(f"  arm diff pass_fraction: committed {m0:+.3f} [{lo0:+.3f},{hi0:+.3f}]"
          f" -> filtered {m1:+.3f} [{lo1:+.3f},{hi1:+.3f}]")
        # t0-fixed too (claimed DAR/alpha=1.000 for both)
        g0 = cell(rows, "mas", "t0-fixed")
        c0 = tier1(g0, PRIMARY)
        f0 = tier1(g0, PRIMARY, exclude=bad)
        P(f"  t0-fixed MAS: committed pass^1={c0['pass1']:.3f} DAR={c0['DAR']:.3f} "
          f"alpha={c0['alpha']:.3f} | excl node-dead pass^1={f0['pass1']:.3f} "
          f"DAR={f0['DAR']:.3f} alpha={f0['alpha']:.3f} "
          f"(dropped {f0['dropped_runs']}/250)")

    P()
    P("=" * 78)
    P("H. PERTURBATION CONTROL READOUT, all headline + thinking sweeps")
    P("   (granite-style: base-case MV vs perturbed-case MV, moved x/10)")
    P("=" * 78)
    for name in HEADLINE + ["lfm2.5-8b-think", "qwen3.5-budget"]:
        rows = data[name]
        for arm in ("single", "mas"):
            for bcond, pcond in (("t0-fixed", "pert-t0"),
                                 ("t07-varied", "pert-t05"),
                                 ("t07-varied", "pert-t10")):
                gb = cell(rows, arm, bcond)
                gp = cell(rows, arm, pcond)
                moved = tot = hits = 0
                for pid, bid in sorted(PERT_BASE.items()):
                    if pid not in gp or bid not in gb:
                        continue
                    bmv, _ = metrics.majority_vote([r["decision"] for r in gb[bid]])
                    pmv, _ = metrics.majority_vote([r["decision"] for r in gp[pid]])
                    tot += 1
                    moved += bmv != pmv
                    hits += pmv == PERT[pid]
                P(f"{name:22s} {arm:6s} {bcond:10s}->{pcond:8s} "
                  f"MV moved {moved}/{tot}, matched flipped label {hits}/{tot}")

    P()
    P("=" * 78)
    P("I. TOKEN RATIO (mas/single, t07-varied) per sweep — committed range check")
    P("=" * 78)
    for name in SWEEPS:
        tot = {}
        for arm in ("single", "mas"):
            g = cell(data[name], arm, "t07-varied")
            toks = [r["prompt_tokens"] + r["completion_tokens"]
                    for runs in g.values() for r in runs]
            wall = [r["wall_clock_s"] for runs in g.values() for r in runs]
            tot[arm] = (sum(toks) / len(toks), sum(wall) / len(wall))
        P(f"{name:22s} tokens {tot['single'][0]:7.0f}->{tot['mas'][0]:7.0f} "
          f"({tot['mas'][0]/tot['single'][0]:.2f}x)  "
          f"wall {tot['single'][1]:6.1f}->{tot['mas'][1]:6.1f} "
          f"({tot['mas'][1]/tot['single'][1]:.2f}x)")


if __name__ == "__main__":
    main()
