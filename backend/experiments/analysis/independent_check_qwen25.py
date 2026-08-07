#!/usr/bin/env python
"""Independent audit of the qwen2.5:7b-instruct PRD-A repeatability sweep.

Written from scratch by a second independent auditor. Shares no code with the
project's analysis pipeline (metrics.py / report.py / stats.py) and was written
without executing them. Recomputes every number in
results-qwen2.5-7b/analysis-report.md directly from the raw journals,
manifest, and ground-truth label files, and performs a forensic
investigation of the T=0 fixed-seed nondeterminism the report implies.

Run:  backend/.venv/bin/python backend/experiments/analysis/independent_check_qwen25.py
"""

import json
import math
import random
import datetime as dt
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

RES = Path("/home/el/projects/msc-dissertation/backend/experiments/results-qwen2.5-7b")
ALERTS = Path("/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json")
PERT = Path("/home/el/projects/msc-dissertation/backend/experiments/perturbation_cases.json")

VALID = {"escalate", "dismiss", "investigate", "malformed"}
HNORM = math.log2(4.0)  # entropy normalized over the 4-way decision domain
EXPECTED_MALFORMED = 16

# ----------------------------------------------------------------- loading

def jread(path):
    out = []
    for ln in open(path, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            out.append(json.loads(ln))
    return out


def load_labels():
    lab = {}
    for a in json.load(open(ALERTS))["alerts"]:
        lab[a["alert_id"]] = a["ground_truth"]
    for a in json.load(open(PERT))["alerts"]:
        lab[a["alert_id"]] = a["ground_truth"]
    return lab


# ----------------------------------------------------------------- LCS (own impl)

def lcs_naive(a, b):
    """Reference O(nm) DP, used for the self-test only."""
    if not a or not b:
        return 0
    row = [0] * (len(b) + 1)
    for x in a:
        diag = 0
        for j, y in enumerate(b, 1):
            tmp = row[j]
            row[j] = diag + 1 if x == y else max(row[j], row[j - 1])
            diag = tmp
    return row[-1]


def lcs_fast(a, b):
    """Bit-parallel LCS length (Allison–Dix style), own implementation."""
    if not a or not b:
        return 0
    if len(a) > len(b):
        a, b = b, a
    n = len(a)
    masks = defaultdict(int)
    for i, s in enumerate(a):
        masks[s] |= 1 << i
    full = (1 << n) - 1
    v = full
    for s in b:
        p = masks.get(s, 0)
        u = v & p
        v = ((v + u) | (v - u)) & full
    return n - bin(v).count("1")


def selftest_lcs():
    rng = random.Random(20260807)
    for _ in range(500):
        a = [rng.randint(0, 6) for _ in range(rng.randint(0, 30))]
        b = [rng.randint(0, 6) for _ in range(rng.randint(0, 30))]
        assert lcs_naive(a, b) == lcs_fast(a, b), (a, b)


# ----------------------------------------------------------------- metric helpers

def pass_hat_k(correct, n, k):
    """P(k runs drawn without replacement all match the label) = C(c,k)/C(n,k)."""
    if k > n:
        return None
    if correct < k:
        return 0.0
    return math.comb(correct, k) / math.comb(n, k)


def dar(decisions):
    """Pairwise decision-agreement; malformed never agrees with anything."""
    pairs = list(combinations(decisions, 2))
    return sum(1 for a, b in pairs if a == b and a != "malformed") / len(pairs)


def dar_naive(decisions):
    """Pairwise agreement counting malformed==malformed as agreement
    (the convention the report's single/t0-fixed DAR=0.952 implies)."""
    pairs = list(combinations(decisions, 2))
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def entropy_norm(decisions):
    n = len(decisions)
    h = -sum((c / n) * math.log2(c / n) for c in Counter(decisions).values())
    return h / HNORM


def kripp_alpha(units):
    """Nominal Krippendorff's alpha via the coincidence matrix (own impl)."""
    cats = sorted({d for u in units for d in u})
    ix = {c: i for i, c in enumerate(cats)}
    K = len(cats)
    co = np.zeros((K, K))
    for u in units:
        m = len(u)
        if m < 2:
            continue
        for i in range(m):
            for j in range(m):
                if i != j:
                    co[ix[u[i]], ix[u[j]]] += 1.0 / (m - 1)
    n = co.sum()
    if n <= 1:
        return 1.0
    d_obs = n - np.trace(co)
    marg = co.sum(axis=0)
    d_exp = (n * n - (marg ** 2).sum()) / (n - 1)
    return 1.0 if d_exp == 0 else float(1.0 - d_obs / d_exp)


def seq_sim(a, b, kind):
    if kind == "exact":
        return 1.0 if a == b else 0.0
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if kind == "jaccard":
        sa, sb = set(a), set(b)
        return len(sa & sb) / len(sa | sb)
    if kind == "nlcs":
        return lcs_naive(list(a), list(b)) / max(len(a), len(b))
    raise ValueError(kind)


def rouge_l_f1_group(texts):
    toks = [t.lower().split() for t in texts]
    vocab = {}
    enc = [tuple(vocab.setdefault(w, len(vocab)) for w in tk) for tk in toks]
    memo = {}
    vals = []
    for a, b in combinations(enc, 2):
        if len(a) + len(b) == 0:
            vals.append(1.0)
            continue
        key = (a, b) if a <= b else (b, a)
        if key not in memo:
            memo[key] = len(a) if a == b else lcs_fast(list(a), list(b))
        vals.append(2.0 * memo[key] / (len(a) + len(b)))
    return float(np.mean(vals))


# ----------------------------------------------------------------- per-condition

def analyse_condition(rows, labels):
    by_case = defaultdict(list)
    for r in rows:
        by_case[r["case_id"]].append(r)
    for g in by_case.values():
        g.sort(key=lambda r: r["repeat_idx"])
    cases = sorted(by_case)

    acc = defaultdict(list)
    units = []
    per_case = {}
    for cid in cases:
        g = by_case[cid]
        decs = [r["decision"] for r in g]
        units.append(decs)
        n = len(decs)
        lab = labels[cid]
        c = sum(1 for d in decs if d == lab)
        acc["p1"].append(c / n)
        acc["p5"].append(pass_hat_k(c, n, 5))
        acc["p15"].append(pass_hat_k(c, n, 15))
        acc["dar"].append(dar(decs))
        acc["dar_naive"].append(dar_naive(decs))
        acc["flip"].append(1.0 if len(set(decs)) > 1 else 0.0)
        acc["ent"].append(entropy_norm(decs))
        cnt = Counter(decs)
        top = max(cnt.values())
        winners = {d for d, v in cnt.items() if v == top}
        acc["maj_strict"].append(1.0 if winners == {lab} else 0.0)
        acc["maj_lenient"].append(1.0 if lab in winners else 0.0)
        acc["maj_firstseen"].append(1.0 if cnt.most_common(1)[0][0] == lab else 0.0)

        trajs = [tuple(r.get("tool_calls") or ()) for r in g]
        for kind, key in (("exact", "tar"), ("jaccard", "jac"), ("nlcs", "nlcs")):
            acc[key].append(float(np.mean([seq_sim(a, b, kind) for a, b in combinations(trajs, 2)])))
        acc["rouge"].append(rouge_l_f1_group([r["raw_output"] or "" for r in g]))
        per_case[cid] = {"pass_frac": c / n, "DAR": acc["dar"][-1], "entropy": acc["ent"][-1]}

    tpr = float(np.mean([r["prompt_tokens"] + r["completion_tokens"] for r in rows]))
    res = {
        "cases": len(cases),
        "repeats": len(units[0]),
        "pass1": float(np.mean(acc["p1"])),
        "pass5": None if acc["p5"][0] is None else float(np.mean(acc["p5"])),
        "pass15": None if acc["p15"][0] is None else float(np.mean(acc["p15"])),
        "DAR": float(np.mean(acc["dar"])),
        "DAR_naive": float(np.mean(acc["dar_naive"])),
        "alpha": kripp_alpha(units),
        "flip_rate": float(np.mean(acc["flip"])),
        "maj_strict": float(np.mean(acc["maj_strict"])),
        "maj_lenient": float(np.mean(acc["maj_lenient"])),
        "maj_firstseen": float(np.mean(acc["maj_firstseen"])),
        "mean_entropy": float(np.mean(acc["ent"])),
        "TAR": float(np.mean(acc["tar"])),
        "jaccard": float(np.mean(acc["jac"])),
        "nLCS": float(np.mean(acc["nlcs"])),
        "malformed_rate": sum(1 for r in rows if r["decision"] == "malformed") / len(rows),
        "tokens_per_run": tpr,
        "wall_clock": float(np.mean([r["wall_clock_s"] for r in rows])),
        "rouge": float(np.mean(acc["rouge"])),
        "_per_case": per_case,
    }
    for k in ("pass1", "pass5", "pass15"):
        v = res[k]
        res["tokens_per_" + k] = (tpr / v) if v else None
    return res


# ----------------------------------------------------------------- integrity

def integrity(single, mas, manifest):
    probs = []
    rows = single + mas
    tot = manifest["totals"]
    if len(single) != tot["single"]:
        probs.append(f"single lines {len(single)} != manifest {tot['single']}")
    if len(mas) != tot["mas"]:
        probs.append(f"mas lines {len(mas)} != manifest {tot['mas']}")
    if len(rows) != len(manifest["runs"]):
        probs.append(f"total lines {len(rows)} != planned {len(manifest['runs'])}")

    ids = Counter(r["run_id"] for r in rows)
    dup = [k for k, c in ids.items() if c > 1]
    if dup:
        probs.append(f"{len(dup)} duplicate run_ids e.g. {dup[:5]}")
    keys = Counter((r["case_id"], r["arm"], r["condition"], r["repeat_idx"]) for r in rows)
    dup2 = [k for k, c in keys.items() if c > 1]
    if dup2:
        probs.append(f"{len(dup2)} duplicate (case,arm,cond,repeat) e.g. {dup2[:5]}")

    plan = {m["run_id"]: m for m in manifest["runs"]}
    missing = sorted(set(plan) - set(ids))
    extra = sorted(set(ids) - set(plan))
    if missing:
        probs.append(f"{len(missing)} planned runs absent e.g. {missing[:5]}")
    if extra:
        probs.append(f"{len(extra)} journal runs not planned e.g. {extra[:5]}")
    bad_fields = []
    for r in rows:
        m = plan.get(r["run_id"])
        if not m:
            continue
        for f in ("seed", "temperature", "condition", "arm", "case_id", "repeat_idx", "block"):
            if r[f] != m[f]:
                bad_fields.append((r["run_id"], f, r[f], m[f]))
    if bad_fields:
        probs.append(f"{len(bad_fields)} field mismatches vs manifest e.g. {bad_fields[:5]}")

    dig = {r["model_digest"] for r in rows}
    if dig != {manifest["model_digest"]}:
        probs.append(f"digest set {dig} != manifest digest")
    ver = {r["ollama_version"] for r in rows}
    if ver != {manifest["ollama_version"]}:
        probs.append(f"ollama_version set {ver} != manifest {manifest['ollama_version']}")
    mod = {r["model"] for r in rows}
    if mod != {manifest["model"]}:
        probs.append(f"model set {mod}")

    bad_dec = [(r["run_id"], r["decision"]) for r in rows if r["decision"] not in VALID]
    if bad_dec:
        probs.append(f"{len(bad_dec)} decisions outside domain e.g. {bad_dec[:5]}")

    mal = [r for r in rows if r["decision"] == "malformed"]
    errs = [r for r in rows if r.get("error")]
    print(f"  malformed runs: {len(mal)} (expected {EXPECTED_MALFORMED}); journal error field set on {len(errs)} runs")
    bycond = Counter((r["arm"], r["condition"]) for r in mal)
    for k in sorted(bycond):
        print(f"    malformed {k[0]}/{k[1]}: {bycond[k]}")
    if len(mal) != EXPECTED_MALFORMED:
        probs.append(f"malformed count {len(mal)} != expected {EXPECTED_MALFORMED}")
    return probs


# ----------------------------------------------------------------- T=0 forensics

def ts(r):
    return dt.datetime.strptime(r["started_at"], "%Y-%m-%dT%H:%M:%SZ")


def first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n if len(a) != len(b) else -1


def forensics(rows_all, condition):
    grp = defaultdict(list)
    order_index = {}
    for arm in ("single", "mas"):
        seq = [r for r in rows_all if r["arm"] == arm]
        seq.sort(key=lambda r: r["started_at"])
        for i, r in enumerate(seq):
            order_index[r["run_id"]] = i
    for r in rows_all:
        if r["condition"] == condition:
            grp[(r["arm"], r["case_id"])].append(r)
    for g in grp.values():
        g.sort(key=lambda r: r["repeat_idx"])

    # wall-clock predecessor of every run within its arm (for cache-state analysis)
    prev_case = {}
    for arm in ("single", "mas"):
        seq = sorted((r for r in rows_all if r["arm"] == arm),
                     key=lambda r: (r["started_at"], r["repeat_idx"]))
        for i, r in enumerate(seq):
            prev_case[r["run_id"]] = seq[i - 1]["case_id"] if i else None

    n_groups = len(grp)
    byte_div, dec_div, traj_div = [], [], []
    patterns = defaultdict(Counter)
    harness_flags = []
    deviant_repeats = defaultdict(Counter)
    deviant_prev = defaultdict(Counter)
    gap_records = []

    for key, g in sorted(grp.items()):
        outs = [r["raw_output"] or "" for r in g]
        decs = [r["decision"] for r in g]
        trajs = [tuple(r.get("tool_calls") or ()) for r in g]

        # harness constancy inside the group
        for f in ("seed", "temperature", "model_digest", "ollama_version"):
            if len({r[f] for r in g}) != 1:
                harness_flags.append((key, f, [r[f] for r in g]))
        if len({r["prompt_tokens"] for r in g}) != 1:
            harness_flags.append((key, "prompt_tokens", [r["prompt_tokens"] for r in g]))

        if len(set(outs)) > 1:
            byte_div.append(key)
            if len(set(decs)) > 1:
                dec_div.append(key)
            if len(set(trajs)) > 1:
                traj_div.append(key)
            # equivalence classes over repeats by exact output
            cls = {}
            sig = []
            for o in outs:
                cls.setdefault(o, len(cls))
                sig.append(cls[o])
            patterns[key[0]][tuple(sig)] += 1
            # which repeats deviate from the modal output
            modal = Counter(outs).most_common(1)[0][0]
            for r, o in zip(g, outs):
                if o != modal:
                    deviant_repeats[key[0]][r["repeat_idx"]] += 1
                    same = prev_case.get(r["run_id"]) == r["case_id"]
                    deviant_prev[key[0]]["same_case_pred" if same else "diff_case_pred"] += 1
            # timing gaps preceding each repeat
            times = [ts(r) for r in g]
            gaps = [(times[i] - times[i - 1]).total_seconds() for i in range(1, len(times))]
            gap_records.append((key, gaps, sig))

    return {
        "n_groups": n_groups,
        "byte_div": byte_div,
        "dec_div": dec_div,
        "traj_div": traj_div,
        "patterns": patterns,
        "harness_flags": harness_flags,
        "deviant_repeats": deviant_repeats,
        "deviant_prev": deviant_prev,
        "gap_records": gap_records,
        "groups": grp,
        "order_index": order_index,
    }


def show_example(g):
    """Print a minimal diff example for the first divergent pair in a group."""
    g = sorted(g, key=lambda r: r["repeat_idx"])
    outs = [r["raw_output"] or "" for r in g]
    base_i = 0
    for j in range(1, len(g)):
        if outs[j] != outs[base_i]:
            i = base_i
            pos = first_diff(outs[i], outs[j])
            a, b = outs[i], outs[j]
            lo = max(0, pos - 60)
            print(f"    runs {g[i]['run_id']}  vs  {g[j]['run_id']}")
            print(f"    completion_tokens {g[i]['completion_tokens']} vs {g[j]['completion_tokens']}; "
                  f"tool_calls equal: {g[i]['tool_calls'] == g[j]['tool_calls']}; "
                  f"decisions {g[i]['decision']!r} vs {g[j]['decision']!r}")
            print(f"    first divergent char index {pos} of lens ({len(a)},{len(b)})")
            print(f"      A: ...{a[lo:pos]!r} >>{a[pos:pos+40]!r}")
            print(f"      B: ...{b[lo:pos]!r} >>{b[pos:pos+40]!r}")
            return


# ----------------------------------------------------------------- report values

R = {
    ("single", "t0-fixed"): dict(pass1=0.244, pass5=0.220, pass15=None, DAR=0.952, alpha=0.783,
                                 flip_rate=0.120, maj=0.240, ent=0.043, TAR=0.968, jac=0.991,
                                 nlcs=0.989, mal=0.016, tpr=2099.024, tp1=8602.557, tp5=9541.018,
                                 tp15=None, wall=2.638, rouge=0.863),
    ("single", "t07-varied"): dict(pass1=0.293, pass5=0.089, pass15=0.000, DAR=0.719, alpha=0.102,
                                   flip_rate=0.880, maj=0.200, ent=0.312, TAR=0.505, jac=0.841,
                                   nlcs=0.794, mal=0.011, tpr=2073.595, tp1=7069.073, tp5=23360.612,
                                   tp15=None, wall=2.589, rouge=0.301),
    ("mas", "t0-fixed"): dict(pass1=0.380, pass5=0.200, pass15=None, DAR=0.824, alpha=0.576,
                              flip_rate=0.380, maj=0.380, ent=0.152, TAR=0.672, jac=1.000,
                              nlcs=0.888, mal=0.000, tpr=6028.236, tp1=15863.779, tp5=30141.180,
                              tp15=None, wall=10.980, rouge=0.576),
    ("mas", "t07-varied"): dict(pass1=0.449, pass5=0.107, pass15=0.020, DAR=0.647, alpha=0.279,
                                flip_rate=0.900, maj=0.540, ent=0.364, TAR=0.105, jac=0.999,
                                nlcs=0.638, mal=0.005, tpr=6458.193, tp1=14372.834, tp5=60432.365,
                                tp15=322909.667, wall=9.438, rouge=0.286),
    ("single", "pert-t0"): dict(pass1=0.080, pass5=0.000, DAR=0.880, alpha=0.443, flip_rate=0.300,
                                ent=0.108, rouge=0.843),
    ("single", "pert-t05"): dict(pass1=0.120, pass5=0.000, DAR=0.640, alpha=0.254, flip_rate=0.700,
                                 ent=0.302, rouge=0.332),
    ("single", "pert-t10"): dict(pass1=0.060, pass5=0.000, DAR=0.820, alpha=0.189, flip_rate=0.400,
                                 ent=0.157, rouge=0.284),
    ("mas", "pert-t0"): dict(pass1=0.100, pass5=0.100, DAR=0.800, alpha=0.575, flip_rate=0.400,
                             ent=0.169, rouge=0.516),
    ("mas", "pert-t05"): dict(pass1=0.060, pass5=0.000, DAR=0.710, alpha=0.239, flip_rate=0.500,
                              ent=0.250, rouge=0.354),
    ("mas", "pert-t10"): dict(pass1=0.120, pass5=0.000, DAR=0.720, alpha=0.304, flip_rate=0.600,
                              ent=0.241, rouge=0.282),
}

R_STATS = {
    "pass_frac": dict(mean=-0.156, ci=(-0.232, -0.081), p=0.000),
    "DAR": dict(mean=0.072, ci=(0.011, 0.130), p=0.024),
    "entropy": dict(mean=-0.052, ci=(-0.110, 0.009), p=0.101),
}

KEYS = [
    ("pass1", "pass1", "pass^1"), ("pass5", "pass5", "pass^5"), ("pass15", "pass15", "pass^15"),
    ("DAR", "DAR", "DAR"), ("alpha", "alpha", "kripp_alpha"), ("flip_rate", "flip_rate", "flip_rate"),
    ("maj", "maj_strict", "majority_acc"), ("ent", "mean_entropy", "mean_entropy"),
    ("TAR", "TAR", "TAR"), ("jac", "jaccard", "jaccard"), ("nlcs", "nLCS", "nLCS"),
    ("mal", "malformed_rate", "malformed_rate"), ("tpr", "tokens_per_run", "tokens_per_run"),
    ("tp1", "tokens_per_pass1", "tokens/pass^1"), ("tp5", "tokens_per_pass5", "tokens/pass^5"),
    ("tp15", "tokens_per_pass15", "tokens/pass^15"), ("wall", "wall_clock", "wall_clock_s"),
    ("rouge", "rouge", "rouge_l_f1"),
]
TOL = 0.005
TOL_REL = 0.001


def paired_stats(spc, mpc, metric, n_boot=20000, n_perm=20000, seed=987654321):
    cases = sorted(set(spc) & set(mpc))
    d = np.array([spc[c][metric] - mpc[c][metric] for c in cases])
    rng = np.random.default_rng(seed)
    n = len(d)
    boots = d[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
    obs = abs(d.mean())
    flips = rng.choice([-1.0, 1.0], size=(n_perm, n))
    p = (1 + int((np.abs((flips * d).mean(axis=1)) >= obs - 1e-12).sum())) / (n_perm + 1)
    return float(d.mean()), ci, float(p)


# ----------------------------------------------------------------- main

def main():
    selftest_lcs()
    labels = load_labels()
    single = jread(RES / "journal-single.jsonl")
    mas = jread(RES / "journal-mas.jsonl")
    manifest = json.load(open(RES / "manifest.json"))
    rows = single + mas

    print("=" * 80)
    print("1. INTEGRITY")
    print("=" * 80)
    probs = integrity(single, mas, manifest)
    for p in probs:
        print("  VIOLATION:", p)
    if not probs:
        print("  all integrity checks passed")

    print()
    print("=" * 80)
    print("2. METRIC RECOMPUTATION  (report vs mine; * = |diff| beyond tolerance)")
    print("=" * 80)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["arm"], r["condition"])].append(r)
    results = {}
    disc = []
    for key in sorted(groups):
        res = analyse_condition(groups[key], labels)
        results[key] = res
        rep = R.get(key, {})
        print(f"\n--- {key[0]} / {key[1]}  (cases={res['cases']}, repeats={res['repeats']}) ---")
        print(f"  {'metric':<16}{'report':>14}{'mine':>14}")
        for rk, mk, lab in KEYS:
            if rk not in rep:
                continue
            rv, mv = rep[rk], res[mk]
            if rv is None and mv is None:
                continue
            if rv is None or mv is None:
                ok = False
            elif abs(rv) > 10:
                ok = abs(mv - rv) / abs(rv) <= TOL_REL
            else:
                ok = abs(mv - rv) <= TOL
            note = ""
            if not ok and mk == "DAR" and rv is not None \
                    and abs(res["DAR_naive"] - rv) <= TOL:
                note = (f"  (convention: report counts malformed==malformed pairs "
                        f"as agreement -> {res['DAR_naive']:.3f}; "
                        f"malformed-never-agrees gives {mv:.3f})")
                ok = None
            if not ok and mk == "maj_strict":
                for alt, nm in (("maj_firstseen", "run-order tie-break"),
                                ("maj_lenient", "ties-favor-label")):
                    if rv is not None and abs(res[alt] - rv) <= TOL:
                        note = f"  (convention: report = {nm} {res[alt]:.3f})"
                        ok = None
                        break
            if ok is False:
                disc.append((key, lab, rv, mv))
            f = lambda v: "      —" if v is None else f"{v:,.3f}"
            print(f"  {lab:<16}{f(rv):>14}{f(mv):>14}   {'ok' if ok else ('' if ok is None else '*MISMATCH*')}{note}")

    print()
    print("=" * 80)
    print("3. T=0 FIXED-SEED FORENSICS")
    print("=" * 80)
    for cond in ("t0-fixed", "pert-t0"):
        F = forensics(rows, cond)
        print(f"\n### condition {cond}: {F['n_groups']} (arm,case) groups x 5 repeats, seed=42, T=0")
        print(f"  byte-level divergent groups     : {len(F['byte_div'])} / {F['n_groups']}")
        print(f"    of which decision-divergent   : {len(F['dec_div'])}")
        print(f"    of which trajectory-divergent : {len(F['traj_div'])} (tool_calls sequence differs)")
        bd = Counter(k[0] for k in F["byte_div"])
        dd = Counter(k[0] for k in F["dec_div"])
        td = Counter(k[0] for k in F["traj_div"])
        for arm in ("single", "mas"):
            tot = sum(1 for k in F["groups"] if k[0] == arm)
            print(f"    {arm}: byte {bd[arm]}/{tot}, decision {dd[arm]}, trajectory {td[arm]}")
        print(f"  harness constancy violations inside groups (seed/temp/digest/version/prompt_tokens): "
              f"{len(F['harness_flags'])}")
        for hf in F["harness_flags"][:5]:
            print("    ", hf)
        print(f"  equivalence-class patterns over repeats 0..4 (0=first distinct output):")
        for arm in ("single", "mas"):
            print(f"    {arm}: " + ", ".join(f"{p}x{c}" for p, c in F["patterns"][arm].most_common(12)))
        for arm in ("single", "mas"):
            print(f"  deviant-from-modal repeats [{arm}]: by repeat_idx "
                  f"{dict(sorted(F['deviant_repeats'][arm].items()))}; "
                  f"wall-clock predecessor {dict(F['deviant_prev'][arm])}")
        # timing: gaps within diverging groups vs all groups
        allgaps, divgaps_before_dev = [], []
        for key, gaps, sig in F["gap_records"]:
            allgaps.extend(gaps)
        big = [(k, g) for k, g, s in F["gap_records"] if max(g) > 60]
        print(f"  within-group started_at gaps in diverging groups: "
              f"median {np.median(allgaps) if allgaps else float('nan'):.1f}s, "
              f"max {max(allgaps) if allgaps else float('nan'):.1f}s; "
              f"groups with a >60s internal gap: {len(big)}")
        # examples
        ex = 0
        for key in F["byte_div"]:
            same_dec = key not in set(F["dec_div"])
            wanted = (ex == 0 and same_dec) or (ex == 1 and not same_dec)
            if wanted:
                kind = "same-decision" if same_dec else "DECISION-FLIP"
                print(f"  example ({kind}) group {key}:")
                show_example(F["groups"][key])
                ex += 1
            if ex >= 2:
                break
        # global run-order / time continuity for this condition's arms
        if cond == "t0-fixed":
            for arm in ("single", "mas"):
                seq = sorted((r for r in rows if r["arm"] == arm), key=lambda r: r["started_at"])
                gaps = [((ts(b) - ts(a)).total_seconds(), a["run_id"], b["run_id"])
                        for a, b in zip(seq, seq[1:])]
                gaps.sort(reverse=True)
                print(f"  [{arm}] journal continuity: {len(seq)} runs "
                      f"{seq[0]['started_at']} -> {seq[-1]['started_at']}; "
                      f"largest inter-run gaps: "
                      + ", ".join(f"{g:.0f}s before {b.split(':',1)[1]}" for g, a, b in gaps[:3]))

    print()
    print("=" * 80)
    print("4. STATS  (single - mas, t07-varied, per-case paired)")
    print("=" * 80)
    spc = results[("single", "t07-varied")]["_per_case"]
    mpc = results[("mas", "t07-varied")]["_per_case"]
    for metric, rkey in (("pass_frac", "pass_frac"), ("DAR", "DAR"), ("entropy", "entropy")):
        mean, ci, p = paired_stats(spc, mpc, metric)
        rep = R_STATS[rkey]
        ok = abs(mean - rep["mean"]) <= TOL
        if not ok:
            disc.append((("stats", "t07"), metric, rep["mean"], mean))
        print(f"  {metric:<10} mean {mean:+.3f} (report {rep['mean']:+.3f}) "
              f"CI [{ci[0]:+.3f},{ci[1]:+.3f}] (report [{rep['ci'][0]:+.3f},{rep['ci'][1]:+.3f}]) "
              f"p={p:.4f} (report {rep['p']:.3f})  {'ok' if ok else '*MISMATCH*'}")
    for arm in ("single", "mas"):
        pc = results[(arm, "t07-varied")]["_per_case"]
        worst = sorted(pc, key=lambda c: -pc[c]["entropy"])[:3]
        print(f"  worst-entropy ({arm}, t07-varied): {', '.join(worst)}")

    print()
    print("=" * 80)
    if disc:
        print(f"METRIC VERDICT: {len(disc)} discrepancy(ies) beyond tolerance")
        for k, lab, rv, mv in disc:
            print(f"  {k} {lab}: report={rv} mine={mv}")
    else:
        print("METRIC VERDICT: every reported number reproduced within tolerance")
    print(f"INTEGRITY VERDICT: {'CLEAN' if not probs else f'{len(probs)} violation(s)'}")


if __name__ == "__main__":
    main()
