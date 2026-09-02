#!/usr/bin/env python3
"""Full owner analysis of the budget-sensitivity track (v2b) vs its sealed v2
counterparts. Read-only over the raw journals; zero LLM calls; no network.

Every number in docs/BUDGET-TRACK-ANALYSIS.md comes from this script's stdout.

Scope (six pre-registered pairs, CHANGELOG 2026-08-18):
  v2b results-budget-<slug>  vs  sealed v2 counterpart (same tag/think/num_predict;
  budgets + disclosure the only difference, except infra-context caveats noted
  in the output header).

Sections emitted:
  S0  pair inventory + integrity (counts, errors, ollama versions, seed-schedule identity)
  S1  full Tier-1/2 recomputation per sweep x arm x condition
  S1b paired v2-vs-v2b stats at t07-varied: pass^1, DAR, alpha (bootstrap CI + permutation)
      + Holm-Bonferroni multiplicity correction over the 36-test family
  S2  mechanism: tool-call distributions, per-node calls, cap hits at own ceiling,
      severed channels, decision distributions, per-label recall
  S3  gemma4 deep dive: per-case right->wrong, tool calls, decision mix, budget mentions
  S4  disclosure-vs-size evidence table
  S5  thinking x budget: token decomposition, per-node output growth, headroom test
  S6  T=0 determinism: byte identity + flip groups, v2 vs v2b
  S7  perturbation MV movement /10 pairs
  S8  cross-track synthesis master table (incl. v2 arch effect recomputed)

Conventions match the sealed corpus (docs/MASTER-DATA-REPORT.md header):
pass^k=C(c,k)/C(n,k) vs benchmark labels; malformed never excluded; DAR over
unordered repeat pairs; Krippendorff alpha nominal, cases as units; majority
ties break by canonical config.OUTCOMES order; entropy /log2(4); MV movement =
perturbed-case MV vs same-arm base-case MV (t0-fixed base for pert-t0,
t07-varied base for pert-t05/t10). Cap-hit proxy = per-node tool-call count >=
that node's turn cap (parallel tool calls can exceed the cap; proxy matches the
sealed accounting, e.g. qwen3.5-think 35->46).

Paired stats: per-case v2b-v2 differences at t07-varied (n=50 cases), 20,000
bootstrap resamples for the 95% CI, 20,000 sign-flip permutations (two-sided)
for p; alpha (a corpus-level statistic) uses case-level bootstrap and a
case-swap permutation (each case's v2/v2b repeat vectors exchanged with p=.5),
both on per-case coincidence matrices. Seed 20260821.

Run:  backend/.venv/bin/python backend/experiments/analysis/budget_track_analysis.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

EXP = Path(__file__).resolve().parents[1]
ALERTS = Path("/home/eliem/Projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json")
PERT = EXP / "perturbation_cases.json"

OUTCOMES = ("escalate", "dismiss", "investigate", "malformed")  # canonical order (config.OUTCOMES)
DECISIONS = OUTCOMES[:3]
DATA_TOOLS = {"search_precedents", "get_customer_profile", "check_sanctions_list"}
POLICY_TOOLS = {"calculate_risk_score"}
NODES = ("orchestrator", "data", "policy_risk", "reporting")

CONDS = ("t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10")
REPEATS = {"t0-fixed": 5, "t07-varied": 15, "pert-t0": 5, "pert-t05": 5, "pert-t10": 5}
PERT_CONDS = ("pert-t0", "pert-t05", "pert-t10")
PERT_BASE = {"pert-t0": "t0-fixed", "pert-t05": "t07-varied", "pert-t10": "t07-varied"}

# v2b caps (config.MAS_ITERATION_BUDGETS / SINGLE_ITERATION_BUDGET); v2 uniform 8.
CAP_V2_SINGLE, CAP_V2_NODE = 8, 8
CAP_B32_SINGLE, CAP_B32_DATA, CAP_B32_POLICY = 32, 16, 8

PAIRS = [
    # short, pretty, v2 dir, v2b dir, think, infra caveat
    ("qwen2.5-7b", "qwen2.5:7b-instruct", "results-qwen2.5-7b", "results-budget-qwen2.5-7b",
     "off", "v2 on Ollama 0.31.1 / harness v1 (no node_outputs); v2b on 0.32.9"),
    ("granite4.1-8b", "granite4.1:8b", "results-granite4.1-8b", "results-budget-granite4.1-8b",
     "off", "both 0.32.9 / harness v2 — clean"),
    ("qwen3.5-9b", "qwen3.5:9b (think off)", "results-qwen3.5-9b-ollama0326", "results-budget-qwen3.5-9b",
     "off", "v2 on Ollama 0.32.6 / harness v1 (no node_outputs); v2b on 0.32.9"),
    ("lfm2.5-8b-think", "lfm2.5:8b (think ON)", "results-lfm2.5-8b-thinking", "results-budget-lfm2.5-8b-thinking",
     "on", "both 0.32.9 / harness v2 — clean"),
    ("qwen3.5-9b-think", "qwen3.5:9b (think ON, np8192)", "results-qwen3.5-9b-thinking-budget",
     "results-budget-qwen3.5-9b-thinking", "on", "both 0.32.9 / harness v2, both num_predict 8192 — clean"),
    ("gemma4", "gemma4:latest", "results-gemma4", "results-budget-gemma4",
     "off", "v2 on Ollama 0.32.6 / harness v1 (no node_outputs); v2b on 0.32.9"),
]

RNG_SEED = 20260821
N_BOOT = 20000
N_PERM = 20000


# ---------------------------------------------------------------- loading

def load_journal(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_labels():
    primary = {r["alert_id"]: r["ground_truth"] for r in json.loads(ALERTS.read_text())["alerts"]}
    pert_recs = json.loads(PERT.read_text())["alerts"]
    pert = {r["alert_id"]: r["ground_truth"] for r in pert_recs}
    return primary, pert, pert_recs


# ---------------------------------------------------------------- metrics

def pass_hat_k(decisions, label, k):
    n = len(decisions)
    c = sum(1 for d in decisions if d == label)
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def dar(decisions):
    pairs = list(combinations(decisions, 2))
    return sum(a == b for a, b in pairs) / len(pairs)


def coincidence_matrix(decisions) -> np.ndarray:
    """Per-case 4x4 coincidence counts (weight 1/(m-1)), canonical order."""
    idx = {o: i for i, o in enumerate(OUTCOMES)}
    m = len(decisions)
    M = np.zeros((4, 4))
    if m < 2:
        return M
    for i, a in enumerate(decisions):
        for j, b in enumerate(decisions):
            if i != j:
                M[idx[a], idx[b]] += 1.0 / (m - 1)
    return M


def alpha_from_stack(stack: np.ndarray) -> float | np.ndarray:
    """Krippendorff alpha from summed coincidence matrices.
    stack: (..., 4, 4) already summed over cases."""
    n_c = stack.sum(axis=-1)                       # (...,4)
    n = n_c.sum(axis=-1)                           # (...)
    d_o = n - np.trace(stack, axis1=-2, axis2=-1)  # off-diagonal mass
    d_e = (n * n - (n_c ** 2).sum(axis=-1)) / (n - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        a = 1.0 - d_o / d_e
    return np.where(d_e == 0, 1.0, a) if isinstance(a, np.ndarray) else (1.0 if d_e == 0 else a)


def norm_entropy(decisions):
    counts = Counter(decisions)
    total = sum(counts.values())
    h = -sum((c / total) * math.log2(c / total) for c in counts.values() if c)
    return h / 2.0  # log2(4)


def majority_vote(decisions):
    counts = Counter(decisions)
    top = max(counts.values())
    winners = [o for o in OUTCOMES if counts.get(o, 0) == top]
    return winners[0], len(winners) > 1


def group(rows, arm, cond):
    by_case = defaultdict(list)
    for r in rows:
        if r["arm"] == arm and r["condition"] == cond:
            by_case[r["case_id"]].append(r)
    for c in by_case:
        by_case[c].sort(key=lambda r: r["repeat_idx"])
    return dict(sorted(by_case.items()))


def tier_stats(by_case, labels):
    s = {}
    cases = sorted(by_case)
    dec = {c: [r.get("decision") for r in by_case[c]] for c in cases}
    n_rep = min(len(d) for d in dec.values())
    s["runs"] = sum(len(v) for v in by_case.values())
    s["cases"] = len(cases)
    for k in (1, 5, 15):
        if k <= n_rep:
            s[f"pass^{k}"] = float(np.mean([pass_hat_k(dec[c], labels[c], k) for c in cases]))
    s["DAR"] = float(np.mean([dar(dec[c]) for c in cases]))
    stack = np.stack([coincidence_matrix(dec[c]) for c in cases])
    s["alpha"] = float(alpha_from_stack(stack.sum(axis=0)))
    s["flip"] = float(np.mean([len(set(dec[c])) > 1 for c in cases]))
    mv = {c: majority_vote(dec[c]) for c in cases}
    s["mv_acc"] = float(np.mean([mv[c][0] == labels[c] for c in cases]))
    s["mv_ties"] = sum(1 for c in cases if mv[c][1])
    s["mv"] = {c: mv[c][0] for c in cases}
    lbls = [labels[c] for c in cases]
    s["baseline"] = max(Counter(lbls).values()) / len(lbls)
    s["entropy"] = float(np.mean([norm_entropy(dec[c]) for c in cases]))
    allruns = [r for c in cases for r in by_case[c]]
    dist = Counter(r.get("decision") for r in allruns)
    s["dist"] = {d: dist.get(d, 0) for d in OUTCOMES}
    s["prompt_tokens"] = float(np.mean([r.get("prompt_tokens") or 0 for r in allruns]))
    s["completion_tokens"] = float(np.mean([r.get("completion_tokens") or 0 for r in allruns]))
    s["total_tokens"] = s["prompt_tokens"] + s["completion_tokens"]
    s["tools_mean"] = float(np.mean([len(r.get("tool_calls") or []) for r in allruns]))
    s["errors"] = sum(1 for r in allruns if r.get("error"))
    s["per_case_dec"] = dec
    return s


# ---------------------------------------------------------------- paired stats

def paired_scalar(pc_a, pc_b, rng):
    """Per-case paired diff d = b - a. Bootstrap CI + sign-flip permutation p."""
    cases = sorted(set(pc_a) & set(pc_b))
    d = np.array([pc_b[c] - pc_a[c] for c in cases])
    n = len(d)
    boot = d[rng.integers(0, n, size=(N_BOOT, n))].mean(axis=1)
    ci = (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975)))
    obs = abs(d.mean())
    flips = rng.choice((-1.0, 1.0), size=(N_PERM, n))
    p = (1 + int((np.abs((flips * d).mean(axis=1)) >= obs - 1e-12).sum())) / (N_PERM + 1)
    return float(d.mean()), ci, float(p), n


def paired_alpha(dec_a, dec_b, rng):
    """Alpha diff (v2b - v2): case bootstrap CI + case-swap permutation p."""
    cases = sorted(set(dec_a) & set(dec_b))
    A = np.stack([coincidence_matrix(dec_a[c]) for c in cases])  # (n,4,4)
    B = np.stack([coincidence_matrix(dec_b[c]) for c in cases])
    n = len(cases)
    obs = float(alpha_from_stack(B.sum(0)) - alpha_from_stack(A.sum(0)))
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boot = alpha_from_stack(B[idx].sum(1)) - alpha_from_stack(A[idx].sum(1))
    ci = (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975)))
    swap = rng.random(size=(N_PERM, n)) < 0.5     # (P,n)
    w = swap[..., None, None]
    permB = np.where(w, A[None], B[None]).sum(1)  # (P,4,4)
    permA = np.where(w, B[None], A[None]).sum(1)
    diffs = alpha_from_stack(permB) - alpha_from_stack(permA)
    p = (1 + int((np.abs(diffs) >= abs(obs) - 1e-12).sum())) / (N_PERM + 1)
    return obs, ci, float(p), n


def holm(pvals: dict[str, float]) -> dict[str, tuple[float, bool]]:
    """Holm-Bonferroni at alpha=.05. Returns name -> (adjusted p, survives)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (name, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        running = max(running, adj)
        out[name] = (running, running < 0.05)
    return out


# ---------------------------------------------------------------- helpers

def data_calls(r):
    return sum(1 for t in (r.get("tool_calls") or []) if t in DATA_TOOLS)


def policy_calls(r):
    return sum(1 for t in (r.get("tool_calls") or []) if t in POLICY_TOOLS)


def f3(x):
    return "—" if x is None else f"{x:.3f}"


def pctf(x):
    return f"{100*x:.1f}%"


BUDGET_RE = re.compile(r"\bbudget\b|\btool-use steps?\b|\bsteps? (?:remaining|left)\b", re.I)


def main():
    np.random.seed(0)
    rng = np.random.default_rng(RNG_SEED)
    primary, pert, pert_recs = load_labels()
    labels = {**primary, **pert}
    print("=" * 100)
    print("BUDGET-SENSITIVITY TRACK (v2b) — FULL ANALYSIS  | script: budget_track_analysis.py | seed", RNG_SEED)
    print("=" * 100)

    data = {}  # short -> {"v2": {"single": rows, "mas": rows}, "v2b": {...}}
    print("\n### S0. PAIR INVENTORY & INTEGRITY\n")
    print("| pair | v2 dir | v2b dir | v2 runs s/m | v2b runs s/m | v2 ollama | v2b ollama | errors v2 | errors v2b | seeds identical |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for short, pretty, v2d, v2bd, think, caveat in PAIRS:
        entry = {}
        for tag, d in (("v2", v2d), ("v2b", v2bd)):
            entry[tag] = {
                "single": load_journal(EXP / d / "journal-single.jsonl"),
                "mas": load_journal(EXP / d / "journal-mas.jsonl"),
            }
        data[short] = entry
        seeds_ok = True
        for arm in ("single", "mas"):
            sv2 = {r["run_id"]: r["seed"] for r in entry["v2"][arm]}
            svb = {r["run_id"]: r["seed"] for r in entry["v2b"][arm]}
            common = set(sv2) & set(svb)
            if len(common) != 1150 or any(sv2[k] != svb[k] for k in common):
                seeds_ok = False
        vers2 = sorted({r["ollama_version"] for a in ("single", "mas") for r in entry["v2"][a]})
        versb = sorted({r["ollama_version"] for a in ("single", "mas") for r in entry["v2b"][a]})
        e2 = sum(1 for a in ("single", "mas") for r in entry["v2"][a] if r.get("error"))
        eb = sum(1 for a in ("single", "mas") for r in entry["v2b"][a] if r.get("error"))
        print(f"| {short} | {v2d} | {v2bd} | {len(entry['v2']['single'])}/{len(entry['v2']['mas'])} "
              f"| {len(entry['v2b']['single'])}/{len(entry['v2b']['mas'])} | {','.join(vers2)} | {','.join(versb)} "
              f"| {e2} | {eb} | {'YES' if seeds_ok else 'NO'} |")
    for short, pretty, v2d, v2bd, think, caveat in PAIRS:
        print(f"- {short}: {caveat}")

    # ---------------- S1: tier tables ------------------------------------
    print("\n### S1. FULL TIER-1/2 RECOMPUTATION (per sweep x arm x condition)\n")
    T = {}  # (short, track, arm, cond) -> stats
    for short, pretty, v2d, v2bd, think, caveat in PAIRS:
        for track in ("v2", "v2b"):
            for arm in ("single", "mas"):
                rows = data[short][track][arm]
                for cond in CONDS:
                    by_case = group(rows, arm, cond)
                    if by_case:
                        T[(short, track, arm, cond)] = tier_stats(by_case, labels)
        print(f"\n#### {short} ({pretty})\n")
        hdr = ("| arm | cond | track | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | base | ties "
               "| entropy | esc/dis/inv/mal | tokens (p+c) | tools/run | err |")
        print(hdr)
        print("|" + "---|" * 17)
        for arm in ("single", "mas"):
            for cond in CONDS:
                for track in ("v2", "v2b"):
                    s = T.get((short, track, arm, cond))
                    if not s:
                        continue
                    d = s["dist"]
                    print(f"| {arm} | {cond} | {track} | {f3(s.get('pass^1'))} | {f3(s.get('pass^5'))} "
                          f"| {f3(s.get('pass^15'))} | {f3(s['DAR'])} | {f3(s['alpha'])} | {f3(s['flip'])} "
                          f"| {f3(s['mv_acc'])} | {f3(s['baseline'])} | {s['mv_ties']} | {f3(s['entropy'])} "
                          f"| {d['escalate']}/{d['dismiss']}/{d['investigate']}/{d['malformed']} "
                          f"| {s['total_tokens']:.0f} ({s['prompt_tokens']:.0f}+{s['completion_tokens']:.0f}) "
                          f"| {s['tools_mean']:.1f} | {s['errors']} |")

    # ---------------- S1b: paired stats + multiplicity --------------------
    print("\n### S1b. PAIRED v2->v2b STATS at t07-varied (n=50 cases; b32 minus v2)\n")
    print("| model | arm | metric | v2 | v2b | Δ (v2b−v2) | 95% CI | p (perm) |")
    print("|---|---|---|---|---|---|---|---|")
    pvals = {}
    stats_store = {}
    for short, pretty, *_ in PAIRS:
        for arm in ("single", "mas"):
            g2 = group(data[short]["v2"][arm], arm, "t07-varied")
            gb = group(data[short]["v2b"][arm], arm, "t07-varied")
            dec2 = {c: [r.get("decision") for r in rs] for c, rs in g2.items()}
            decb = {c: [r.get("decision") for r in rs] for c, rs in gb.items()}
            # pass^1
            p2 = {c: pass_hat_k(dec2[c], labels[c], 1) for c in dec2}
            pb = {c: pass_hat_k(decb[c], labels[c], 1) for c in decb}
            m, ci, p, n = paired_scalar(p2, pb, rng)
            key = f"{short}|{arm}|pass^1"
            pvals[key] = p
            stats_store[key] = (np.mean(list(p2.values())), np.mean(list(pb.values())), m, ci, p)
            # DAR
            d2 = {c: dar(dec2[c]) for c in dec2}
            db = {c: dar(decb[c]) for c in decb}
            m2, ci2, pd, _ = paired_scalar(d2, db, rng)
            key2 = f"{short}|{arm}|DAR"
            pvals[key2] = pd
            stats_store[key2] = (np.mean(list(d2.values())), np.mean(list(db.values())), m2, ci2, pd)
            # alpha
            ma, cia, pa, _ = paired_alpha(dec2, decb, rng)
            a2 = float(alpha_from_stack(np.stack([coincidence_matrix(dec2[c]) for c in sorted(dec2)]).sum(0)))
            ab = float(alpha_from_stack(np.stack([coincidence_matrix(decb[c]) for c in sorted(decb)]).sum(0)))
            key3 = f"{short}|{arm}|alpha"
            pvals[key3] = pa
            stats_store[key3] = (a2, ab, ma, cia, pa)
            for key_, metric in ((key, "pass^1"), (key2, "DAR"), (key3, "alpha")):
                v2v, vbv, mm, cc, pp = stats_store[key_]
                star = "***" if pp < 0.001 else "**" if pp < 0.01 else "*" if pp < 0.05 else "ns"
                print(f"| {short} | {arm} | {metric} | {v2v:.3f} | {vbv:.3f} | {mm:+.3f} {star} "
                      f"| [{cc[0]:+.3f}, {cc[1]:+.3f}] | {pp:.4f} |")

    print("\n#### Holm-Bonferroni over the full 36-test family (alpha=.05)\n")
    adj = holm(pvals)
    print("| test | raw p | Holm-adjusted p | survives |")
    print("|---|---|---|---|")
    for name, praw in sorted(pvals.items(), key=lambda kv: kv[1]):
        a, ok = adj[name]
        print(f"| {name} | {praw:.4f} | {a:.4f} | {'YES' if ok else 'no'} |")
    surv = [k for k, (a, ok) in adj.items() if ok]
    print(f"\nSurviving tests ({len(surv)}/36): " + "; ".join(sorted(surv)))
    # secondary family: the 12 pre-registered primary contrasts (pass^1 only)
    p12 = {k: v for k, v in pvals.items() if k.endswith("pass^1")}
    adj12 = holm(p12)
    surv12 = [k for k, (a, ok) in adj12.items() if ok]
    print(f"Pre-registered primary family (12 pass^1 tests) Holm survivors ({len(surv12)}/12): "
          + "; ".join(sorted(surv12)))
    for k in sorted(p12):
        a, ok = adj12[k]
        print(f"  {k}: raw {p12[k]:.4f} -> Holm {a:.4f} {'SURVIVES' if ok else 'ns'}")

    # ---------------- S2: mechanism ---------------------------------------
    print("\n### S2. MECHANISM: what the budgets changed in behaviour\n")
    print("#### S2a. Tool calls per run (all 1,150 runs per arm) and cap hits at each track's own ceiling\n")
    print("| model | arm/node | v2 mean | v2b mean | v2 med | v2b med | v2 max | v2b max | v2 cap | v2 hits | v2b cap | v2b hits |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        s2 = data[short]["v2"]["single"]; sb = data[short]["v2b"]["single"]
        m2 = data[short]["v2"]["mas"]; mb = data[short]["v2b"]["mas"]
        c2 = [len(r.get("tool_calls") or []) for r in s2]
        cb = [len(r.get("tool_calls") or []) for r in sb]
        h2 = sum(c >= CAP_V2_SINGLE for c in c2); hb = sum(c >= CAP_B32_SINGLE for c in cb)
        print(f"| {short} | single | {np.mean(c2):.2f} | {np.mean(cb):.2f} | {np.median(c2):.0f} | {np.median(cb):.0f} "
              f"| {max(c2)} | {max(cb)} | 8 | {h2} | 32 | {hb} |")
        for node, fn, capb in (("MAS data", data_calls, CAP_B32_DATA), ("MAS policy_risk", policy_calls, CAP_B32_POLICY)):
            c2 = [fn(r) for r in m2]; cb = [fn(r) for r in mb]
            h2 = sum(c >= CAP_V2_NODE for c in c2); hb = sum(c >= capb for c in cb)
            print(f"| {short} | {node} | {np.mean(c2):.2f} | {np.mean(cb):.2f} | {np.median(c2):.0f} | {np.median(cb):.0f} "
                  f"| {max(c2)} | {max(cb)} | 8 | {h2} | {capb} | {hb} |")
        c2 = [len(r.get("tool_calls") or []) for r in m2]; cb = [len(r.get("tool_calls") or []) for r in mb]
        print(f"| {short} | MAS total | {np.mean(c2):.2f} | {np.mean(cb):.2f} | {np.median(c2):.0f} | {np.median(cb):.0f} "
              f"| {max(c2)} | {max(cb)} | — | — | — | — |")

    print("\n#### S2b. Severed channel (empty node_outputs) rates, MAS arm (harness-v2 journals only)\n")
    print("| model | track | rows w/ node_outputs | empty orch | empty data | empty policy | empty reporting | empty data % |")
    print("|---|---|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        for track in ("v2", "v2b"):
            rows = data[short][track]["mas"]
            wno = [r for r in rows if isinstance(r.get("node_outputs"), dict)]
            if not wno:
                print(f"| {short} | {track} | 0 (harness v1) | — | — | — | — | — |")
                continue
            em = {n: sum(1 for r in wno if not (r["node_outputs"].get(n) or "").strip()) for n in NODES}
            print(f"| {short} | {track} | {len(wno)} | {em['orchestrator']} | {em['data']} | {em['policy_risk']} "
                  f"| {em['reporting']} | {100*em['data']/len(wno):.1f}% |")

    print("\n#### S2c. Decision distributions at t07-varied (counts /750) and dismissal collapse\n")
    print("| model | arm | track | escalate | dismiss | investigate | malformed | dismiss share | modal share |")
    print("|---|---|---|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        for arm in ("single", "mas"):
            for track in ("v2", "v2b"):
                s = T[(short, track, arm, "t07-varied")]
                d = s["dist"]; n = sum(d.values())
                modal = max(d.values()) / n
                print(f"| {short} | {arm} | {track} | {d['escalate']} | {d['dismiss']} | {d['investigate']} "
                      f"| {d['malformed']} | {pctf(d['dismiss']/n)} | {pctf(modal)} |")

    print("\n#### S2d. Per-label run-level recall at t07-varied (fraction of runs on label-L cases decided L)\n")
    print("| model | arm | track | escalate recall | dismiss recall | investigate recall |")
    print("|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        for arm in ("single", "mas"):
            for track in ("v2", "v2b"):
                rows = [r for r in data[short][track][arm] if r["condition"] == "t07-varied"]
                rec = {}
                for L in DECISIONS:
                    lr = [r for r in rows if labels[r["case_id"]] == L]
                    rec[L] = sum(1 for r in lr if r.get("decision") == L) / len(lr)
                print(f"| {short} | {arm} | {track} | {rec['escalate']:.3f} | {rec['dismiss']:.3f} | {rec['investigate']:.3f} |")

    # ---------------- S3: gemma4 deep dive ---------------------------------
    print("\n### S3. GEMMA4 DEEP DIVE (single arm, t07-varied unless stated)\n")
    g2 = group(data["gemma4"]["v2"]["single"], "single", "t07-varied")
    gb = group(data["gemma4"]["v2b"]["single"], "single", "t07-varied")
    dec2 = {c: [r.get("decision") for r in rs] for c, rs in g2.items()}
    decb = {c: [r.get("decision") for r in rs] for c, rs in gb.items()}
    print("#### S3a. Per-case correct counts /15 (cases with the largest declines first; Δ != 0 only)\n")
    print("| case | label | v2 correct/15 | v2b correct/15 | Δ | v2 decision mix | v2b decision mix |")
    print("|---|---|---|---|---|---|---|")
    deltas = []
    for c in sorted(dec2):
        c2 = sum(1 for d in dec2[c] if d == labels[c])
        cb = sum(1 for d in decb[c] if d == labels[c])
        deltas.append((cb - c2, c, c2, cb))
    for dlt, c, c2, cb in sorted(deltas):
        if dlt == 0:
            continue
        mix2 = dict(Counter(dec2[c]).most_common())
        mixb = dict(Counter(decb[c]).most_common())
        print(f"| {c} | {labels[c]} | {c2} | {cb} | {dlt:+d} | {mix2} | {mixb} |")
    worse = sum(1 for d, *_ in deltas if d < 0)
    better = sum(1 for d, *_ in deltas if d > 0)
    same = sum(1 for d, *_ in deltas if d == 0)
    print(f"\nCases worse: {worse}, better: {better}, unchanged: {same} (of 50). "
          f"Net run-level correct: {sum(cb for _, _, _, cb in deltas)} v2b vs {sum(c2 for _, _, c2, _ in deltas)} v2 (/750).")
    mv_flips_rw = [c for c in dec2 if majority_vote(dec2[c])[0] == labels[c] and majority_vote(decb[c])[0] != labels[c]]
    mv_flips_wr = [c for c in dec2 if majority_vote(dec2[c])[0] != labels[c] and majority_vote(decb[c])[0] == labels[c]]
    print(f"MV right->wrong cases: {len(mv_flips_rw)} {mv_flips_rw}")
    print(f"MV wrong->right cases: {len(mv_flips_wr)} {mv_flips_wr}")
    print("\nLabel breakdown of run-level losses (t07 single):")
    for L in DECISIONS:
        l2 = sum(1 for c in dec2 if labels[c] == L for d in dec2[c] if d == L)
        lb = sum(1 for c in decb if labels[c] == L for d in decb[c] if d == L)
        nL = 15 * sum(1 for c in dec2 if labels[c] == L)
        print(f"  {L}: v2 {l2}/{nL} -> v2b {lb}/{nL} ({lb-l2:+d})")

    print("\n#### S3b. Behaviour shift (gemma4 single, all conditions pooled and t07)\n")
    for cond_lbl, pred in (("t07-varied", lambda r: r["condition"] == "t07-varied"),
                           ("all 1150", lambda r: True)):
        r2 = [r for r in data["gemma4"]["v2"]["single"] if pred(r)]
        rb = [r for r in data["gemma4"]["v2b"]["single"] if pred(r)]
        t2 = [len(r.get("tool_calls") or []) for r in r2]
        tb = [len(r.get("tool_calls") or []) for r in rb]
        ct2 = [r.get("completion_tokens") or 0 for r in r2]
        ctb = [r.get("completion_tokens") or 0 for r in rb]
        tt2 = [(r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in r2]
        ttb = [(r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in rb]
        print(f"  [{cond_lbl}] tools/run {np.mean(t2):.2f}->{np.mean(tb):.2f} ({(np.mean(tb)/np.mean(t2)-1)*100:+.0f}%); "
              f"completion tok {np.mean(ct2):.0f}->{np.mean(ctb):.0f} ({(np.mean(ctb)/np.mean(ct2)-1)*100:+.0f}%); "
              f"total tok {np.mean(tt2):.0f}->{np.mean(ttb):.0f} ({(np.mean(ttb)/np.mean(tt2)-1)*100:+.0f}%)")
    print("\n  Tool-call histogram, gemma4 single t07 (calls: v2 count -> v2b count):")
    h2 = Counter(len(r.get("tool_calls") or []) for r in data["gemma4"]["v2"]["single"] if r["condition"] == "t07-varied")
    hb = Counter(len(r.get("tool_calls") or []) for r in data["gemma4"]["v2b"]["single"] if r["condition"] == "t07-varied")
    for k in sorted(set(h2) | set(hb)):
        print(f"    {k}: {h2.get(k,0):4d} -> {hb.get(k,0):4d}")

    print("\n#### S3c. Budget mentions in raw_output (v2b runs; regex: budget|tool-use steps|steps remaining/left)\n")
    print("| model | arm | v2b runs mentioning budget | % | v2 runs mentioning (control) |")
    print("|---|---|---|---|---|")
    for short, *_ in PAIRS:
        for arm in ("single", "mas"):
            def cnt(rows):
                n = 0
                for r in rows:
                    txt = str(r.get("raw_output") or "")
                    if isinstance(r.get("node_outputs"), dict):
                        txt += " " + " ".join(str(v or "") for v in r["node_outputs"].values())
                    if BUDGET_RE.search(txt):
                        n += 1
                return n
            nb = cnt(data[short]["v2b"][arm]); n2 = cnt(data[short]["v2"][arm])
            print(f"| {short} | {arm} | {nb}/1150 | {100*nb/1150:.1f}% | {n2}/1150 |")

    # escalate-vs-investigate shift detail for gemma4 (rulebook herding test)
    print("\n#### S3d. gemma4 single decision shares at t07: v2 vs v2b (per label)\n")
    for L in DECISIONS:
        rows2 = [r for r in data["gemma4"]["v2"]["single"] if r["condition"] == "t07-varied" and labels[r["case_id"]] == L]
        rowsb = [r for r in data["gemma4"]["v2b"]["single"] if r["condition"] == "t07-varied" and labels[r["case_id"]] == L]
        m2 = Counter(r.get("decision") for r in rows2); mb = Counter(r.get("decision") for r in rowsb)
        print(f"  label={L} (n={len(rows2)}): v2 {dict(m2)} -> v2b {dict(mb)}")

    # ---------------- S5: thinking x budget --------------------------------
    print("\n### S5. THINKING x BUDGET: where the headroom went\n")
    print("#### S5a. Token decomposition per arm (all 1,150 runs; mean per run)\n")
    print("| model | arm | v2 prompt | v2b prompt | Δ% | v2 completion | v2b completion | Δ% | v2 total | v2b total | Δ% | Δtools/run |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        for arm in ("single", "mas"):
            r2 = data[short]["v2"][arm]; rb = data[short]["v2b"][arm]
            p2 = np.mean([r.get("prompt_tokens") or 0 for r in r2]); pb = np.mean([r.get("prompt_tokens") or 0 for r in rb])
            c2 = np.mean([r.get("completion_tokens") or 0 for r in r2]); cb = np.mean([r.get("completion_tokens") or 0 for r in rb])
            t2, tb = p2 + c2, pb + cb
            tl2 = np.mean([len(r.get("tool_calls") or []) for r in r2]); tlb = np.mean([len(r.get("tool_calls") or []) for r in rb])
            print(f"| {short} | {arm} | {p2:.0f} | {pb:.0f} | {(pb/p2-1)*100:+.0f}% | {c2:.0f} | {cb:.0f} | {(cb/c2-1)*100:+.0f}% "
                  f"| {t2:.0f} | {tb:.0f} | {(tb/t2-1)*100:+.0f}% | {tlb-tl2:+.2f} |")

    print("\n#### S5b. Per-node output length (chars, mean over MAS runs with node_outputs)\n")
    print("| model | track | orchestrator | data | policy_risk | reporting |")
    print("|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        for track in ("v2", "v2b"):
            wno = [r for r in data[short][track]["mas"] if isinstance(r.get("node_outputs"), dict)]
            if not wno:
                print(f"| {short} | {track} | (harness v1) | | | |")
                continue
            means = {n: np.mean([len(r["node_outputs"].get(n) or "") for r in wno]) for n in NODES}
            print(f"| {short} | {track} | {means['orchestrator']:.0f} | {means['data']:.0f} "
                  f"| {means['policy_risk']:.0f} | {means['reporting']:.0f} |")

    print("\n#### S5c. Headroom-absorption test: Δcompletion tokens vs Δtool calls vs Δpass^1 (t07, single+mas)\n")
    print("| model | think | arm | Δcompl tok/run | Δtool calls/run | Δpass^1 | Δ significant? |")
    print("|---|---|---|---|---|---|---|")
    for short, pretty, v2d, v2bd, think, cav in PAIRS:
        for arm in ("single", "mas"):
            r2 = [r for r in data[short]["v2"][arm] if r["condition"] == "t07-varied"]
            rb = [r for r in data[short]["v2b"][arm] if r["condition"] == "t07-varied"]
            dc = np.mean([r.get("completion_tokens") or 0 for r in rb]) - np.mean([r.get("completion_tokens") or 0 for r in r2])
            dt = np.mean([len(r.get("tool_calls") or []) for r in rb]) - np.mean([len(r.get("tool_calls") or []) for r in r2])
            key = f"{short}|{arm}|pass^1"
            _, _, dm, _, pp = stats_store[key]
            print(f"| {short} | {think} | {arm} | {dc:+.0f} | {dt:+.2f} | {dm:+.3f} | {'yes' if pp<0.05 else 'no'} (p={pp:.3f}) |")

    # qwen3.5-think cap-hit token detail
    print("\n#### S5d. qwen3.5-think MAS: completion tokens on data-cap-hit runs vs others (v2b)\n")
    rb = data["qwen3.5-9b-think"]["v2b"]["mas"]
    hit = [r for r in rb if data_calls(r) >= CAP_B32_DATA]
    miss = [r for r in rb if data_calls(r) < CAP_B32_DATA]
    print(f"  cap-hit runs n={len(hit)}: mean completion {np.mean([r['completion_tokens'] for r in hit]):.0f}, "
          f"mean decision dist {dict(Counter(r['decision'] for r in hit))}")
    print(f"  non-hit runs n={len(miss)}: mean completion {np.mean([r['completion_tokens'] for r in miss]):.0f}")
    r2 = data["qwen3.5-9b-think"]["v2"]["mas"]
    hit2 = [r for r in r2 if data_calls(r) >= CAP_V2_NODE]
    print(f"  v2 cap-hit runs n={len(hit2)}: decisions {dict(Counter(r['decision'] for r in hit2))}")

    # ---------------- S6: T=0 determinism ----------------------------------
    print("\n### S6. T=0 DETERMINISM (fixed seed 42): byte-identity and flip groups\n")
    print("| model | arm | cond | track | groups | byte-identical | decision-flipping | byte-id excl. repeat 0 |")
    print("|---|---|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        for arm in ("single", "mas"):
            for cond in ("t0-fixed", "pert-t0"):
                for track in ("v2", "v2b"):
                    by_case = group(data[short][track][arm], arm, cond)
                    n = len(by_case)
                    bi = sum(1 for rs in by_case.values() if len({str(r.get("raw_output") or "") for r in rs}) == 1)
                    fl = sum(1 for rs in by_case.values() if len({r.get("decision") for r in rs}) > 1)
                    bi_x0 = sum(1 for rs in by_case.values()
                                if len({str(r.get("raw_output") or "") for r in rs if r["repeat_idx"] != 0}) == 1)
                    print(f"| {short} | {arm} | {cond} | {track} | {n} | {bi} | {fl} | {bi_x0} |")

    # ---------------- S7: perturbation -------------------------------------
    print("\n### S7. PERTURBATION BLOCK: MV movement /10 pairs (perturbed MV vs same-arm base-case MV)\n")
    print("| model | arm | track | pert-t0 | pert-t05 | pert-t10 | pert MV acc t0/t05/t10 (base 0.600) |")
    print("|---|---|---|---|---|---|---|")
    base_of = {r["alert_id"]: r["base_alert_id"] for r in pert_recs}
    for short, *_ in PAIRS:
        for arm in ("single", "mas"):
            for track in ("v2", "v2b"):
                cells = []
                accs = []
                for pc in PERT_CONDS:
                    pg = group(data[short][track][arm], arm, pc)
                    bg = group(data[short][track][arm], arm, PERT_BASE[pc])
                    moved = 0
                    tot = 0
                    for pid, bid in base_of.items():
                        if pid in pg and bid in bg:
                            tot += 1
                            mv_p = majority_vote([r["decision"] for r in pg[pid]])[0]
                            mv_b = majority_vote([r["decision"] for r in bg[bid]])[0]
                            moved += mv_p != mv_b
                    cells.append(f"{moved}/{tot}")
                    acc = np.mean([majority_vote([r['decision'] for r in pg[pid]])[0] == pert[pid] for pid in pg])
                    accs.append(f"{acc:.2f}")
                print(f"| {short} | {arm} | {track} | {cells[0]} | {cells[1]} | {cells[2]} | {'/'.join(accs)} |")

    # ---------------- S8: synthesis ----------------------------------------
    print("\n### S8. CROSS-TRACK SYNTHESIS: v2 arch effect (MAS - single, t07 pass^1) recomputed + budget response\n")
    print("| model | v2 arch Δ (MAS−single) | v2 arch p | v2b arch Δ | v2b arch p | budget Δ single (p) | budget Δ mas (p) |")
    print("|---|---|---|---|---|---|---|")
    for short, *_ in PAIRS:
        row = [short]
        for track in ("v2", "v2b"):
            gs = group(data[short][track]["single"], "single", "t07-varied")
            gm = group(data[short][track]["mas"], "mas", "t07-varied")
            ps = {c: pass_hat_k([r["decision"] for r in rs], labels[c], 1) for c, rs in gs.items()}
            pm = {c: pass_hat_k([r["decision"] for r in rs], labels[c], 1) for c, rs in gm.items()}
            m, ci, p, n = paired_scalar(ps, pm, rng)  # mas - single
            row.append(f"{m:+.3f}")
            row.append(f"{p:.4f}")
        for arm in ("single", "mas"):
            v2v, vbv, mm, cc, pp = stats_store[f"{short}|{arm}|pass^1"]
            row.append(f"{mm:+.3f} (p={pp:.3f})")
        print("| " + " | ".join(row) + " |")

    # ---------------- S9: serving-stack confound bound --------------------
    print("\n### S9. SERVING-STACK CONFOUND BOUND: pure infra-replication pairs (same model, harness, budgets)\n")
    print("Three v2b pairs cross Ollama versions (qwen2.5-7b 0.31.1->0.32.9; qwen3.5-9b and gemma4 0.32.6->0.32.9).")
    print("The corpus's infra replications isolate the serving-stack effect alone (uniform v2 budgets, no disclosure):\n")
    print("| infra pair | arm | pass^1 A | pass^1 B | Δ | 95% CI | p (perm) |")
    print("|---|---|---|---|---|---|---|")
    INFRA = [
        ("qwen2.5:7b 0.31.1 vs 0.32.6", "results-qwen2.5-7b", "results-qwen2.5-7b-ollama0326"),
        ("qwen3.5:9b 0.31.1 vs 0.32.6", "results", "results-qwen3.5-9b-ollama0326"),
    ]
    for name, da, db in INFRA:
        for arm in ("single", "mas"):
            ra = load_journal(EXP / da / f"journal-{arm}.jsonl")
            rb = load_journal(EXP / db / f"journal-{arm}.jsonl")
            ga = group(ra, arm, "t07-varied"); gb = group(rb, arm, "t07-varied")
            pa = {c: pass_hat_k([r["decision"] for r in rs], labels[c], 1) for c, rs in ga.items()}
            pb = {c: pass_hat_k([r["decision"] for r in rs], labels[c], 1) for c, rs in gb.items()}
            m, ci, p, n = paired_scalar(pa, pb, rng)
            print(f"| {name} | {arm} | {np.mean(list(pa.values())):.3f} | {np.mean(list(pb.values())):.3f} "
                  f"| {m:+.3f} | [{ci[0]:+.3f}, {ci[1]:+.3f}] | {p:.4f} |")

    print("\nDone. Every table above is journal-derived; no LLM calls were made.")


if __name__ == "__main__":
    main()
