#!/usr/bin/env python
"""Independent audit of the PRD-A repeatability experiment analysis.

Written from scratch by an independent auditor; deliberately shares NO code
with the project's own analysis pipeline. Recomputes every headline metric
directly from the raw journals + manifest + ground-truth labels and prints a
side-by-side comparison with the numbers in analysis-report.md.

Run with:  backend/.venv/bin/python independent_check_qwen35.py
"""

import json
import math
import random
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

RES = Path("/home/el/projects/msc-dissertation/backend/experiments/results")
ALERTS = Path("/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json")
PERT = Path("/home/el/projects/msc-dissertation/backend/experiments/perturbation_cases.json")

VALID_DECISIONS = {"escalate", "dismiss", "investigate", "malformed"}
ENTROPY_BASE = math.log2(4)  # normalization documented in CHANGELOG

# ---------------------------------------------------------------- loading

def load_journal(path):
    rows = []
    with open(path) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_labels():
    labels = {}
    for a in json.load(open(ALERTS))["alerts"]:
        labels[a["alert_id"]] = a["ground_truth"]
    for a in json.load(open(PERT))["alerts"]:
        labels[a["alert_id"]] = a["ground_truth"]
    return labels


# ---------------------------------------------------------------- integrity

def integrity(rows_single, rows_mas, manifest):
    problems = []
    rows = rows_single + rows_mas

    # line counts
    tot = manifest["totals"]
    if len(rows_single) != tot.get("single"):
        problems.append(f"single journal lines {len(rows_single)} != manifest {tot.get('single')}")
    if len(rows_mas) != tot.get("mas"):
        problems.append(f"mas journal lines {len(rows_mas)} != manifest {tot.get('mas')}")
    if len(rows) != len(manifest["runs"]):
        problems.append(f"journal total {len(rows)} != manifest planned {len(manifest['runs'])}")

    # duplicates
    keys = [(r["case_id"], r["arm"], r["condition"], r["repeat_idx"]) for r in rows]
    dups = [k for k, c in Counter(keys).items() if c > 1]
    if dups:
        problems.append(f"duplicate (case,arm,condition,repeat): {dups[:10]}")

    # seeds / planned-run match
    planned = {m["run_id"]: m for m in manifest["runs"]}
    missing = [r["run_id"] for r in rows if r["run_id"] not in planned]
    if missing:
        problems.append(f"{len(missing)} journal run_ids not in manifest, e.g. {missing[:5]}")
    unrun = set(planned) - {r["run_id"] for r in rows}
    if unrun:
        problems.append(f"{len(unrun)} planned runs missing from journals, e.g. {sorted(unrun)[:5]}")
    seed_mismatch = []
    for r in rows:
        m = planned.get(r["run_id"])
        if m is None:
            continue
        for fld in ("seed", "temperature", "condition", "arm", "case_id", "repeat_idx"):
            if r[fld] != m[fld]:
                seed_mismatch.append((r["run_id"], fld, r[fld], m[fld]))
    if seed_mismatch:
        problems.append(f"{len(seed_mismatch)} journal/manifest field mismatches, e.g. {seed_mismatch[:5]}")

    # model digest
    digests = {r["model_digest"] for r in rows}
    if digests != {manifest["model_digest"]}:
        problems.append(f"model_digest set {digests} != manifest {manifest['model_digest']}")

    # decisions domain
    bad = [(r["run_id"], r["decision"]) for r in rows if r["decision"] not in VALID_DECISIONS]
    if bad:
        problems.append(f"{len(bad)} runs with decision outside domain, e.g. {bad[:5]}")

    # t0 determinism: byte-identical raw_output within (case, arm) for
    # fixed-seed T=0 conditions (t0-fixed and pert-t0)
    nondet = []
    grp = defaultdict(list)
    for r in rows:
        if r["condition"] in ("t0-fixed", "pert-t0"):
            grp[(r["case_id"], r["arm"], r["condition"])].append(r)
    for k, g in sorted(grp.items()):
        outs = {r["raw_output"] for r in g}
        if len(outs) > 1:
            nondet.append((k, len(outs)))
    if nondet:
        problems.append(f"{len(nondet)} T=0 fixed-seed groups NOT byte-identical: {nondet}")

    return problems


# ---------------------------------------------------------------- metric helpers

def pass_at_k(c, n, k):
    """C(c,k)/C(n,k): probability k sampled runs all agree with the label."""
    if k > n:
        return None
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def pairwise_agreement(decisions):
    """DAR within one case. malformed counts as disagreement with everything,
    including another malformed output (never excluded)."""
    pairs = list(combinations(decisions, 2))
    ok = sum(1 for a, b in pairs if a == b and a != "malformed")
    return ok / len(pairs)


def krippendorff_alpha_nominal(units):
    """units: list of lists of category labels (all non-missing)."""
    cats = sorted({c for u in units for c in u})
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    o = np.zeros((k, k))
    for u in units:
        m = len(u)
        if m < 2:
            continue
        cnt = Counter(u)
        for a in cnt:
            for b in cnt:
                if a == b:
                    o[idx[a], idx[a]] += cnt[a] * (cnt[a] - 1) / (m - 1)
                else:
                    o[idx[a], idx[b]] += cnt[a] * cnt[b] / (m - 1)
    n = o.sum()
    nc = o.sum(axis=1)
    do = n - np.trace(o)  # observed disagreement mass (off-diagonal)
    de = (n * n - (nc * nc).sum()) / (n - 1)
    if de == 0:
        return 1.0
    return 1.0 - do / de


def shannon_entropy_norm(decisions):
    cnt = Counter(decisions)
    n = len(decisions)
    h = -sum((c / n) * math.log2(c / n) for c in cnt.values())
    return h / ENTROPY_BASE


def lcs_len(a, b):
    """Plain DP LCS length (used for short tool sequences + self-test)."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def lcs_len_bits(a, b):
    """Bit-parallel LCS length (Crochemore et al.) for long token sequences."""
    if not a or not b:
        return 0
    m = len(a)
    pm = defaultdict(int)
    for i, x in enumerate(a):
        pm[x] |= 1 << i
    full = (1 << m) - 1
    v = full
    for y in b:
        p = pm.get(y, 0)
        u = v & p
        v = ((v + u) | (v - u)) & full
    # zeros in v = LCS length
    return m - bin(v).count("1")


def _selftest_lcs():
    rng = random.Random(7)
    for _ in range(300):
        a = [rng.randint(0, 5) for _ in range(rng.randint(0, 25))]
        b = [rng.randint(0, 5) for _ in range(rng.randint(0, 25))]
        assert lcs_len(a, b) == lcs_len_bits(a, b), (a, b)


def mean_pairwise(vals_per_case):
    return float(np.mean(vals_per_case))


# ---------------------------------------------------------------- per-condition metrics

def condition_metrics(rows, labels):
    """rows: all runs for one (arm, condition). Returns dict of metrics."""
    by_case = defaultdict(list)
    for r in rows:
        by_case[r["case_id"]].append(r)
    for g in by_case.values():
        g.sort(key=lambda r: r["repeat_idx"])

    cases = sorted(by_case)
    n_rep = len(by_case[cases[0]])

    p1 = []
    p5 = []
    p15 = []
    dar = []
    flip = []
    maj_strict = []
    maj_lenient = []  # tie including label counts as correct
    maj_firstseen = []  # tie broken by first-seen decision in run order
    ent = []
    tar = []
    jac = []
    nlcs = []
    rouge = []
    units = []

    for cid in cases:
        g = by_case[cid]
        decs = [r["decision"] for r in g]
        units.append(decs)
        label = labels[cid]
        n = len(decs)
        c = sum(1 for d in decs if d == label)
        p1.append(c / n)
        p5.append(pass_at_k(c, n, 5))
        p15.append(pass_at_k(c, n, 15))
        dar.append(pairwise_agreement(decs))
        flip.append(1.0 if len(set(decs)) > 1 else 0.0)
        cnt = Counter(decs)
        top = max(cnt.values())
        winners = [d for d, v in cnt.items() if v == top]
        maj_strict.append(1.0 if winners == [label] else 0.0)
        maj_lenient.append(1.0 if label in winners else 0.0)
        # first-seen (run-order) tie-break, i.e. Counter.most_common(1) —
        # this is the convention the report's 0.360 for single/t07 implies
        maj_firstseen.append(1.0 if cnt.most_common(1)[0][0] == label else 0.0)
        ent.append(shannon_entropy_norm(decs))

        tools = [tuple(r.get("tool_calls") or []) for r in g]
        t_ok, j_sum, l_sum = [], [], []
        for a, b in combinations(tools, 2):
            t_ok.append(1.0 if a == b else 0.0)
            sa, sb = set(a), set(b)
            if not sa and not sb:
                j_sum.append(1.0)
            elif not sa or not sb:
                j_sum.append(0.0)
            else:
                j_sum.append(len(sa & sb) / len(sa | sb))
            if not a and not b:
                l_sum.append(1.0)
            elif not a or not b:
                l_sum.append(0.0)
            else:
                l_sum.append(lcs_len(list(a), list(b)) / max(len(a), len(b)))
        tar.append(float(np.mean(t_ok)))
        jac.append(float(np.mean(j_sum)))
        nlcs.append(float(np.mean(l_sum)))

        # ROUGE-L F1 on full raw output, lowercased whitespace tokens
        toks = [r["raw_output"].lower().split() for r in g]
        vocab = {}
        enc = [[vocab.setdefault(t, len(vocab)) for t in tk] for tk in toks]
        cache = {}
        f1s = []
        for i, j in combinations(range(len(enc)), 2):
            a, b = enc[i], enc[j]
            key = (tuple(a), tuple(b))
            if key not in cache:
                if a == b:
                    l = len(a)
                elif not a or not b:
                    l = 0
                else:
                    l = lcs_len_bits(a, b)
                cache[key] = l
            l = cache[key]
            if len(a) + len(b) == 0:
                f1s.append(1.0)
            else:
                f1s.append(2.0 * l / (len(a) + len(b)))
        rouge.append(float(np.mean(f1s)))

    toks_per_run = float(np.mean([r["prompt_tokens"] + r["completion_tokens"] for r in rows]))
    wall = float(np.mean([r["wall_clock_s"] for r in rows]))
    malformed_rate = sum(1 for r in rows if r["decision"] == "malformed") / len(rows)

    out = {
        "cases": len(cases),
        "repeats": n_rep,
        "pass1": float(np.mean(p1)),
        "pass5": float(np.mean(p5)) if p5[0] is not None else None,
        "pass15": float(np.mean(p15)) if p15[0] is not None else None,
        "DAR": float(np.mean(dar)),
        "alpha": float(krippendorff_alpha_nominal(units)),
        "flip_rate": float(np.mean(flip)),
        "maj_acc_strict": float(np.mean(maj_strict)),
        "maj_acc_lenient": float(np.mean(maj_lenient)),
        "maj_acc_firstseen": float(np.mean(maj_firstseen)),
        "mean_entropy": float(np.mean(ent)),
        "TAR": float(np.mean(tar)),
        "jaccard": float(np.mean(jac)),
        "nLCS": float(np.mean(nlcs)),
        "malformed_rate": malformed_rate,
        "tokens_per_run": toks_per_run,
        "wall_clock": wall,
        "rouge_l_f1": float(np.mean(rouge)),
        # per-case series for the stats section
        "_per_case": {cid: {"pass_frac": p1[i], "DAR": dar[i], "entropy": ent[i]}
                      for i, cid in enumerate(cases)},
    }
    for k in ("pass1", "pass5", "pass15"):
        pk = out[k]
        out[f"tokens_per_{k}"] = (toks_per_run / pk) if pk else None
    return out


# ---------------------------------------------------------------- stats

def paired_stats(single_pc, mas_pc, metric, n_boot=20000, n_perm=20000, seed=1234):
    cases = sorted(set(single_pc) & set(mas_pc))
    d = np.array([single_pc[c][metric] - mas_pc[c][metric] for c in cases])
    rng = np.random.default_rng(seed)
    n = len(d)
    boots = np.array([d[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
    obs = abs(d.mean())
    signs = rng.choice([-1.0, 1.0], size=(n_perm, n))
    perm = np.abs((signs * d).mean(axis=1))
    p = (1 + int((perm >= obs - 1e-12).sum())) / (n_perm + 1)
    return float(d.mean()), ci, float(p)


# ---------------------------------------------------------------- report values

REPORT = {
    ("single", "t0-fixed"): dict(pass1=0.400, pass5=0.400, pass15=None, DAR=1.000, alpha=1.000,
                                 flip_rate=0.000, maj=0.400, ent=0.000, TAR=1.000, jac=1.000,
                                 nlcs=1.000, mal=0.000, tpr=4219.180, tp1=10547.950, tp5=10547.950,
                                 tp15=None, wall=6.249, rouge=1.000),
    ("single", "t07-varied"): dict(pass1=0.364, pass5=0.078, pass15=0.040, DAR=0.618, alpha=0.205,
                                   flip_rate=0.920, maj=0.360, ent=0.409, TAR=0.155, jac=0.709,
                                   nlcs=0.618, mal=0.004, tpr=4241.443, tp1=11652.315, tp5=54241.770,
                                   tp15=106036.067, wall=6.538, rouge=0.210),
    ("mas", "t0-fixed"): dict(pass1=0.260, pass5=0.260, pass15=None, DAR=1.000, alpha=1.000,
                              flip_rate=0.000, maj=0.260, ent=0.000, TAR=1.000, jac=1.000,
                              nlcs=1.000, mal=0.000, tpr=7501.360, tp1=28851.385, tp5=28851.385,
                              tp15=None, wall=19.736, rouge=1.000),
    ("mas", "t07-varied"): dict(pass1=0.253, pass5=0.110, pass15=0.060, DAR=0.802, alpha=0.203,
                                flip_rate=0.760, maj=0.220, ent=0.223, TAR=0.414, jac=0.953,
                                nlcs=0.847, mal=0.000, tpr=7759.716, tp1=30630.458, tp5=70459.685,
                                tp15=129328.600, wall=16.345, rouge=0.244),
    ("single", "pert-t0"): dict(pass1=0.300, pass5=0.300, DAR=1.000, alpha=1.000, flip_rate=0.000,
                                ent=0.000, rouge=1.000),
    ("single", "pert-t05"): dict(pass1=0.320, pass5=0.100, DAR=0.760, alpha=0.593, flip_rate=0.500,
                                 ent=0.205, rouge=0.247),
    ("single", "pert-t10"): dict(pass1=0.240, pass5=0.000, DAR=0.650, alpha=0.335, flip_rate=0.700,
                                 ent=0.310, rouge=0.195),
    ("mas", "pert-t0"): dict(pass1=0.000, pass5=0.000, DAR=1.000, alpha=1.000, flip_rate=0.000,
                             ent=0.000, rouge=1.000),
    ("mas", "pert-t05"): dict(pass1=0.080, pass5=0.000, DAR=0.760, alpha=0.055, flip_rate=0.500,
                              ent=0.205, rouge=0.251),
    ("mas", "pert-t10"): dict(pass1=0.180, pass5=0.100, DAR=0.740, alpha=0.302, flip_rate=0.600,
                              ent=0.229, rouge=0.213),
}

REPORT_STATS = {
    "pass_frac": dict(mean=0.111, ci=(0.045, 0.180), p=0.003),
    "DAR": dict(mean=-0.184, ci=(-0.241, -0.127), p=0.000),
    "entropy": dict(mean=0.185, ci=(0.125, 0.245), p=0.000),
}

KEYMAP = [  # (report key, my key, label)
    ("pass1", "pass1", "pass^1"), ("pass5", "pass5", "pass^5"), ("pass15", "pass15", "pass^15"),
    ("DAR", "DAR", "DAR"), ("alpha", "alpha", "kripp_alpha"), ("flip_rate", "flip_rate", "flip_rate"),
    ("maj", "maj_acc_strict", "majority_acc"), ("ent", "mean_entropy", "mean_entropy"),
    ("TAR", "TAR", "TAR"), ("jac", "jaccard", "jaccard"), ("nlcs", "nLCS", "nLCS"),
    ("mal", "malformed_rate", "malformed_rate"), ("tpr", "tokens_per_run", "tokens_per_run"),
    ("tp1", "tokens_per_pass1", "tokens/pass^1"), ("tp5", "tokens_per_pass5", "tokens/pass^5"),
    ("tp15", "tokens_per_pass15", "tokens/pass^15"), ("wall", "wall_clock", "wall_clock_s"),
    ("rouge", "rouge_l_f1", "rouge_l_f1"),
]

TOL = 0.005          # fraction-scale metrics
TOL_REL = 0.001      # relative tolerance for token/second scale numbers


def main():
    _selftest_lcs()
    labels = load_labels()
    rows_single = load_journal(RES / "journal-single.jsonl")
    rows_mas = load_journal(RES / "journal-mas.jsonl")
    manifest = json.load(open(RES / "manifest.json"))

    print("=" * 78)
    print("INTEGRITY")
    print("=" * 78)
    problems = integrity(rows_single, rows_mas, manifest)
    if problems:
        for p in problems:
            print("VIOLATION:", p)
    else:
        print("all integrity checks passed")

    allrows = rows_single + rows_mas
    groups = defaultdict(list)
    for r in allrows:
        groups[(r["arm"], r["condition"])].append(r)

    print()
    print("=" * 78)
    print("METRICS  (report vs recomputed; * = mismatch beyond tolerance)")
    print("=" * 78)
    discrepancies = []
    results = {}
    for key in sorted(groups, key=lambda k: (k[0], k[1])):
        res = condition_metrics(groups[key], labels)
        results[key] = res
        rep = REPORT.get(key, {})
        print(f"\n--- {key[0]} / {key[1]}  (cases={res['cases']}, repeats={res['repeats']}) ---")
        print(f"{'metric':<16}{'report':>14}{'mine':>14}   ok?")
        for rk, mk, lab in KEYMAP:
            if rk not in rep:
                continue
            rv, mv = rep[rk], res[mk]
            if rv is None and mv is None:
                continue
            if rv is None or mv is None:
                line_ok = False
            elif rv > 10:  # token / big-number scale
                line_ok = abs(mv - rv) / rv <= TOL_REL
            else:
                line_ok = abs(mv - rv) <= TOL
            flag = "" if line_ok else "  *MISMATCH*"
            if not line_ok and mk == "maj_acc_strict" and rv is not None \
                    and abs(res["maj_acc_firstseen"] - rv) <= TOL:
                flag = ("  note: tie-break convention — report matches run-order "
                        f"(most_common) tie-break {res['maj_acc_firstseen']:.3f}; "
                        f"strict-majority (ties wrong) gives {mv:.3f}, "
                        f"ties-favor-label gives {res['maj_acc_lenient']:.3f}")
                line_ok = None  # convention difference, not a numeric error
            if line_ok is False:
                discrepancies.append((key, lab, rv, mv))
            fmt = lambda v: "—" if v is None else (f"{v:,.3f}" if abs(v) < 10 else f"{v:,.3f}")
            print(f"{lab:<16}{fmt(rv):>14}{fmt(mv):>14}   {'ok' if line_ok else flag}")

    print()
    print("=" * 78)
    print("STATS (single - mas, t07-varied, paired per case)")
    print("=" * 78)
    spc = results[("single", "t07-varied")]["_per_case"]
    mpc = results[("mas", "t07-varied")]["_per_case"]
    for metric in ("pass_frac", "DAR", "entropy"):
        mean, ci, p = paired_stats(spc, mpc, metric)
        rep = REPORT_STATS[metric]
        ok = abs(mean - rep["mean"]) <= TOL
        print(f"{metric:<10} mean {mean:+.3f} (report {rep['mean']:+.3f}) "
              f"CI [{ci[0]:.3f},{ci[1]:.3f}] (report [{rep['ci'][0]:.3f},{rep['ci'][1]:.3f}]) "
              f"p={p:.4f} (report {rep['p']:.3f}) {'ok' if ok else '*MEAN MISMATCH*'}")
        if not ok:
            discrepancies.append((("stats", "t07"), metric + " mean diff", rep["mean"], mean))

    # worst entropy cases
    print()
    for arm in ("single", "mas"):
        pc = results[(arm, "t07-varied")]["_per_case"]
        worst = sorted(pc, key=lambda c: -pc[c]["entropy"])[:3]
        print(f"worst-entropy cases ({arm}, t07-varied): {', '.join(worst)}")

    print()
    print("=" * 78)
    if discrepancies:
        print(f"VERDICT: DISCREPANCIES FOUND ({len(discrepancies)})")
        for key, lab, rv, mv in discrepancies:
            print(f"  {key} {lab}: report={rv} mine={mv}")
    else:
        print("VERDICT (metrics): all report values reproduced within tolerance")
    if problems:
        print(f"INTEGRITY: {len(problems)} violation(s) — see above")
    else:
        print("INTEGRITY: clean")


if __name__ == "__main__":
    main()
