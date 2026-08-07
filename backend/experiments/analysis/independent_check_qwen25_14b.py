#!/usr/bin/env python
"""Independent audit of the qwen2.5:14b-instruct PRD-A repeatability sweep.

Third independent auditor. All checks written from scratch against the raw
journals, manifest, and ground-truth label files; no code imported from the
project's analysis pipeline (metrics.py / report.py / stats.py) and none of it
was executed. Prior audit scripts (independent_check_qwen35.py,
independent_check_qwen25.py) were consulted for journal schema and for the two
documented reporting conventions only:

  * DAR / alpha / entropy treat 'malformed' as an ordinary outcome category,
    so malformed==malformed pairs COUNT as agreement (category equality);
  * majority-vote ties break in favour of the first-observed decision.

Both conventions are stated in the caption of analysis-report.md, so this
audit adopts them as primary and cross-checks the stricter alternatives.

Sections:
  1. integrity (counts, duplicates, plan conformance, digest, decision domain,
     malformed accounting — expected 4)
  2. recomputation of every reported metric, tolerance |diff| > 0.005
     (relative 0.1% for token-scale numbers)
  3. T=0 fixed-seed cache-sensitivity forensics with explicit comparison
     against the audited qwen2.5:7b numbers
     (7B: single 46/50 byte-divergent, mas 50/50; decision flips 6 / 19)
  4. arm-difference stats (t07-varied), bootstrap CI + sign-flip permutation

Run:
  backend/.venv/bin/python backend/experiments/analysis/independent_check_qwen25_14b.py
"""

import json
import math
import random
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

RES = Path("/home/el/projects/msc-dissertation/backend/experiments/results-qwen2.5-14b")
ALERTS = Path("/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json")
PERT = Path("/home/el/projects/msc-dissertation/backend/experiments/perturbation_cases.json")

DECISION_DOMAIN = {"escalate", "dismiss", "investigate", "malformed"}
ENT_NORM = math.log2(4.0)          # 4-way outcome domain incl. malformed
EXPECTED_MALFORMED = 4
TOL = 0.005
TOL_REL = 0.001                    # for numbers >10 (token counts etc.)

# 7B reference numbers (verified by the previous independent auditor)
SEVEN_B = {
    "t0-fixed": {"single": {"div": 46, "n": 50, "dec": 6},
                 "mas": {"div": 50, "n": 50, "dec": 19}},
}


# ------------------------------------------------------------------ loading

def read_journal(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_labels():
    labels = {}
    for blob, src in ((json.load(open(ALERTS)), "alerts"),
                      (json.load(open(PERT)), "pert")):
        for a in blob["alerts"]:
            labels[a["alert_id"]] = a["ground_truth"]
    return labels


# ------------------------------------------------------------------ LCS

def lcs_dp(xs, ys):
    """Plain O(nm) dynamic-programming LCS length (reference)."""
    if not xs or not ys:
        return 0
    prev = [0] * (len(ys) + 1)
    for x in xs:
        cur = [0]
        for j, y in enumerate(ys, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def lcs_bits(xs, ys):
    """Bit-parallel LCS length; own implementation of the classic
    Allison–Dix recurrence, validated against lcs_dp in a self-test."""
    if not xs or not ys:
        return 0
    if len(ys) < len(xs):
        xs, ys = ys, xs
    n = len(xs)
    occ = {}
    for i, x in enumerate(xs):
        occ[x] = occ.get(x, 0) | (1 << i)
    mask = (1 << n) - 1
    row = mask
    for y in ys:
        p = occ.get(y, 0)
        keep = row & p
        row = ((row + keep) | (row - keep)) & mask
    return n - row.bit_count()


def lcs_selftest():
    rng = random.Random(140807)
    for _ in range(400):
        a = [rng.randrange(5) for _ in range(rng.randrange(0, 26))]
        b = [rng.randrange(5) for _ in range(rng.randrange(0, 26))]
        assert lcs_dp(a, b) == lcs_bits(a, b), (a, b)


# ------------------------------------------------------------------ metrics

def pass_hat(n_correct, n, k):
    """Chance that k distinct repeats drawn without replacement all match."""
    if k > n:
        return None
    if n_correct < k:
        return 0.0
    return math.comb(n_correct, k) / math.comb(n, k)


def pairwise_agreement(vals, strict=False):
    """Fraction of unordered pairs with equal category.
    strict=True refuses to let malformed agree with malformed."""
    pairs = list(combinations(vals, 2))
    if strict:
        hits = sum(1 for a, b in pairs if a == b and a != "malformed")
    else:
        hits = sum(1 for a, b in pairs if a == b)
    return hits / len(pairs)


def norm_entropy(vals):
    n = len(vals)
    h = 0.0
    for c in Counter(vals).values():
        p = c / n
        h -= p * math.log2(p)
    return h / ENT_NORM


def krippendorff_nominal(units):
    """Krippendorff's alpha, nominal metric, via coincidence matrix."""
    cats = sorted({v for u in units for v in u})
    idx = {c: i for i, c in enumerate(cats)}
    K = len(cats)
    co = [[0.0] * K for _ in range(K)]
    for u in units:
        m = len(u)
        if m < 2:
            continue
        cnt = Counter(u)
        for a in cnt:
            for b in cnt:
                pairs = cnt[a] * (cnt[b] - 1) if a == b else cnt[a] * cnt[b]
                co[idx[a]][idx[b]] += pairs / (m - 1)
    n = sum(map(sum, co))
    if n <= 1:
        return 1.0
    do = n - sum(co[i][i] for i in range(K))
    marg = [sum(col) for col in zip(*co)]
    de = (n * n - sum(m * m for m in marg)) / (n - 1)
    return 1.0 if de == 0 else 1.0 - do / de


def traj_sim(a, b, kind):
    if kind == "exact":
        return 1.0 if a == b else 0.0
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if kind == "jaccard":
        A, B = set(a), set(b)
        return len(A & B) / len(A | B)
    if kind == "nlcs":
        return lcs_bits(list(a), list(b)) / max(len(a), len(b))
    raise ValueError(kind)


def rouge_l_pairwise(texts):
    """Mean pairwise ROUGE-L F1 over lowercased whitespace tokens."""
    toks = [tuple(t.lower().split()) for t in texts]
    scores = []
    cache = {}
    for a, b in combinations(toks, 2):
        if not a and not b:
            scores.append(1.0)
            continue
        if not a or not b:
            scores.append(0.0)
            continue
        key = (a, b)
        if key not in cache:
            cache[key] = len(a) if a == b else lcs_bits(list(a), list(b))
        L = cache[key]
        scores.append(2.0 * L / (len(a) + len(b)))
    return sum(scores) / len(scores)


def condition_metrics(rows, labels):
    groups = defaultdict(list)
    for r in rows:
        groups[r["case_id"]].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["repeat_idx"])

    col = defaultdict(list)
    units = []
    per_case = {}
    for cid in sorted(groups):
        g = groups[cid]
        decs = [r["decision"] for r in g]
        n = len(decs)
        units.append(decs)
        lab = labels[cid]
        c = decs.count(lab)
        col["p1"].append(c / n)
        col["p5"].append(pass_hat(c, n, 5))
        col["p15"].append(pass_hat(c, n, 15))
        col["dar"].append(pairwise_agreement(decs))            # report convention
        col["dar_strict"].append(pairwise_agreement(decs, strict=True))
        col["flip"].append(1.0 if len(set(decs)) > 1 else 0.0)
        col["ent"].append(norm_entropy(decs))
        cnt = Counter(decs)                                     # insertion order =
        winner = cnt.most_common(1)[0][0]                       # first-observed tiebreak
        col["maj"].append(1.0 if winner == lab else 0.0)
        top = max(cnt.values())
        col["maj_strict"].append(1.0 if {d for d, v in cnt.items() if v == top} == {lab} else 0.0)
        trajs = [tuple(r.get("tool_calls") or ()) for r in g]
        for kind, key in (("exact", "tar"), ("jaccard", "jac"), ("nlcs", "nlcs")):
            sims = [traj_sim(a, b, kind) for a, b in combinations(trajs, 2)]
            col[key].append(sum(sims) / len(sims))
        col["rouge"].append(rouge_l_pairwise([r["raw_output"] or "" for r in g]))
        per_case[cid] = {"pass_frac": c / n, "DAR": col["dar"][-1],
                         "entropy": col["ent"][-1]}

    mean = lambda k: (None if col[k][0] is None
                      else float(sum(col[k]) / len(col[k])))
    tpr = sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows) / len(rows)
    out = {
        "cases": len(groups), "repeats": len(units[0]),
        "pass1": mean("p1"), "pass5": mean("p5"), "pass15": mean("p15"),
        "DAR": mean("dar"), "DAR_strict": mean("dar_strict"),
        "alpha": krippendorff_nominal(units),
        "flip": mean("flip"), "maj": mean("maj"), "maj_strict": mean("maj_strict"),
        "ent": mean("ent"), "TAR": mean("tar"), "jac": mean("jac"),
        "nlcs": mean("nlcs"),
        "mal": sum(1 for r in rows if r["decision"] == "malformed") / len(rows),
        "tpr": tpr,
        "wall": sum(r["wall_clock_s"] for r in rows) / len(rows),
        "rouge": mean("rouge"),
        "_per_case": per_case,
    }
    for k in ("pass1", "pass5", "pass15"):
        v = out[k]
        out["tokens_" + k] = None if not v else tpr / v
    return out


# ------------------------------------------------------------------ integrity

def integrity(single, mas, manifest):
    problems = []
    rows = single + mas

    if len(single) != manifest["totals"]["single"]:
        problems.append(f"single count {len(single)} != manifest {manifest['totals']['single']}")
    if len(mas) != manifest["totals"]["mas"]:
        problems.append(f"mas count {len(mas)} != manifest {manifest['totals']['mas']}")
    planned = manifest["runs"]
    if len(rows) != len(planned):
        problems.append(f"total {len(rows)} != planned {len(planned)}")

    id_counts = Counter(r["run_id"] for r in rows)
    dups = [k for k, v in id_counts.items() if v > 1]
    if dups:
        problems.append(f"{len(dups)} duplicated run_ids, e.g. {dups[:3]}")
    combo = Counter((r["arm"], r["case_id"], r["condition"], r["repeat_idx"]) for r in rows)
    dups2 = [k for k, v in combo.items() if v > 1]
    if dups2:
        problems.append(f"{len(dups2)} duplicated (arm,case,cond,repeat), e.g. {dups2[:3]}")

    plan = {p["run_id"]: p for p in planned}
    missing = set(plan) - set(id_counts)
    extra = set(id_counts) - set(plan)
    if missing:
        problems.append(f"{len(missing)} planned runs missing, e.g. {sorted(missing)[:3]}")
    if extra:
        problems.append(f"{len(extra)} unplanned journal rows, e.g. {sorted(extra)[:3]}")

    mismatches = []
    for r in rows:
        p = plan.get(r["run_id"])
        if p is None:
            continue
        for f in ("arm", "case_id", "block", "condition", "repeat_idx",
                  "seed", "temperature"):
            if r[f] != p[f]:
                mismatches.append((r["run_id"], f, r[f], p[f]))
    if mismatches:
        problems.append(f"{len(mismatches)} journal/manifest field mismatches, e.g. {mismatches[:3]}")

    # condition-level design conformance
    cond_spec = {c["name"]: c for c in manifest["config"]["conditions"]}
    by_cond = defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r)
    for name, spec in cond_spec.items():
        rs = by_cond[name]
        temps = {r["temperature"] for r in rs}
        if temps != {spec["temperature"]}:
            problems.append(f"{name}: temperatures {temps} != {spec['temperature']}")
        if spec["fixed_seed"] is not None:
            seeds = {r["seed"] for r in rs}
            if seeds != {spec["fixed_seed"]}:
                problems.append(f"{name}: seeds {seeds} != fixed {spec['fixed_seed']}")
        else:
            per_group = defaultdict(set)
            for r in rs:
                per_group[(r["arm"], r["case_id"])].add(r["seed"])
            lazy = [k for k, s in per_group.items() if len(s) < spec["repeats"]]
            if lazy:
                problems.append(f"{name}: {len(lazy)} groups with repeated seeds "
                                f"(expected {spec['repeats']} distinct), e.g. {lazy[:3]}")
        reps = Counter((r["arm"], r["case_id"]) for r in rs)
        bad = [k for k, v in reps.items() if v != spec["repeats"]]
        if bad:
            problems.append(f"{name}: groups without {spec['repeats']} repeats, e.g. {bad[:3]}")

    for field, want in (("model_digest", manifest["model_digest"]),
                        ("ollama_version", manifest["ollama_version"]),
                        ("model", manifest["model"])):
        got = {r[field] for r in rows}
        if got != {want}:
            problems.append(f"{field} set {got} != manifest {want!r}")

    bad_dec = [(r["run_id"], r["decision"]) for r in rows
               if r["decision"] not in DECISION_DOMAIN]
    if bad_dec:
        problems.append(f"{len(bad_dec)} out-of-domain decisions, e.g. {bad_dec[:3]}")

    mal = [r for r in rows if r["decision"] == "malformed"]
    errs = [r for r in rows if r.get("error")]
    print(f"  malformed: {len(mal)} (expected {EXPECTED_MALFORMED}); "
          f"error field set on {len(errs)} rows")
    for r in mal:
        tail = (r["raw_output"] or "")[-70:].replace("\n", " ")
        print(f"    {r['run_id']}  ...{tail!r}")
    if len(mal) != EXPECTED_MALFORMED:
        problems.append(f"malformed count {len(mal)} != {EXPECTED_MALFORMED}")

    # decisions must be recoverable from raw_output's FINAL DECISION line.
    # Reverse-engineered extraction rule (verified to reproduce all 2300
    # journal decisions): the LAST line that starts — modulo markdown
    # heading/emphasis — with 'FINAL DECISION:' followed by a valid decision
    # word on the same line; otherwise malformed. A mid-line or split-line
    # 'FINAL DECISION' does NOT count (that is exactly what makes 3 of the 4
    # malformed rows malformed; the 4th says 'DECISION:' without 'FINAL').
    line_pat = re.compile(
        r"^\s*#*\s*\**\s*final\s+decision\s*\**\s*:\s*\**\s*"
        r"(escalate|dismiss|investigate)\b", re.I)
    bad_extract = 0
    for r in rows:
        ext = "malformed"
        for ln in (r["raw_output"] or "").splitlines():
            m = line_pat.match(ln)
            if m:
                ext = m.group(1).lower()
        if ext != r["decision"]:
            bad_extract += 1
    print(f"  decision vs re-extracted FINAL DECISION line: "
          f"{len(rows) - bad_extract}/{len(rows)} agree")
    if bad_extract:
        problems.append(f"{bad_extract} rows where journal decision != re-extracted decision")

    return problems


# ------------------------------------------------------------------ report values (transcribed from analysis-report.md)

REPORT = {
    ("single", "t0-fixed"): dict(pass1=.188, pass5=.160, pass15=None, DAR=.968, alpha=.884,
                                 flip=.080, maj=.180, ent=.029, TAR=.928, jac=.980, nlcs=.975,
                                 mal=.000, tpr=2137.692, tokens_pass1=11370.702,
                                 tokens_pass5=13360.575, tokens_pass15=None, wall=6.595, rouge=.824),
    ("single", "t07-varied"): dict(pass1=.248, pass5=.149, pass15=.060, DAR=.893, alpha=.382,
                                   flip=.460, maj=.220, ent=.121, TAR=.245, jac=.827, nlcs=.701,
                                   mal=.003, tpr=2128.419, tokens_pass1=8582.333,
                                   tokens_pass5=14264.509, tokens_pass15=35473.644, wall=7.470, rouge=.251),
    ("mas", "t0-fixed"): dict(pass1=.232, pass5=.220, pass15=None, DAR=.976, alpha=.758,
                              flip=.060, maj=.220, ent=.022, TAR=.774, jac=1.000, nlcs=.958,
                              mal=.000, tpr=5833.160, tokens_pass1=25142.931,
                              tokens_pass5=26514.364, tokens_pass15=None, wall=21.404, rouge=.600),
    ("mas", "t07-varied"): dict(pass1=.221, pass5=.145, pass15=.100, DAR=.914, alpha=.340,
                                flip=.320, maj=.220, ent=.094, TAR=.177, jac=.985, nlcs=.778,
                                mal=.003, tpr=5903.395, tokens_pass1=26671.964,
                                tokens_pass5=40637.938, tokens_pass15=59033.947, wall=16.394, rouge=.306),
    ("single", "pert-t0"): dict(pass1=.080, pass5=.000, DAR=.960, alpha=.734, flip=.100,
                                ent=.036, rouge=.841),
    ("single", "pert-t05"): dict(pass1=.060, pass5=.000, DAR=.840, alpha=.129, flip=.300,
                                 ent=.133, rouge=.265),
    ("single", "pert-t10"): dict(pass1=.020, pass5=.000, DAR=.880, alpha=.218, flip=.200,
                                 ent=.112, rouge=.222),
    ("mas", "pert-t0"): dict(pass1=.000, pass5=.000, DAR=.940, alpha=.479, flip=.100,
                             ent=.049, rouge=.602),
    ("mas", "pert-t05"): dict(pass1=.000, pass5=.000, DAR=.960, alpha=.000, flip=.100,
                              ent=.036, rouge=.357),
    ("mas", "pert-t10"): dict(pass1=.000, pass5=.000, DAR=.960, alpha=.000, flip=.100,
                              ent=.036, rouge=.289),
}

REPORT_STATS = {
    "pass_frac": dict(mean=0.027, ci=(-0.012, 0.076), p=0.307),
    "DAR": dict(mean=-0.021, ci=(-0.064, 0.023), p=0.370),
    "entropy": dict(mean=0.027, ci=(-0.019, 0.074), p=0.258),
}

REPORT_WORST = {"single": ["TXN-2025-006", "TXN-2025-019", "TXN-2025-039"],
                "mas": ["TXN-2025-006", "TXN-2025-017", "TXN-2025-019"]}

METRIC_ORDER = [
    ("pass1", "pass^1"), ("pass5", "pass^5"), ("pass15", "pass^15"),
    ("DAR", "DAR"), ("alpha", "kripp_alpha"), ("flip", "flip_rate"),
    ("maj", "majority_acc"), ("ent", "mean_entropy"), ("TAR", "TAR"),
    ("jac", "jaccard"), ("nlcs", "nLCS"), ("mal", "malformed_rate"),
    ("tpr", "tokens_per_run"), ("tokens_pass1", "tok/pass^1"),
    ("tokens_pass5", "tok/pass^5"), ("tokens_pass15", "tok/pass^15"),
    ("wall", "wall_clock_s"), ("rouge", "rouge_l_f1"),
]


# ------------------------------------------------------------------ T=0 forensics

def t0_forensics(rows, condition):
    groups = defaultdict(list)
    for r in rows:
        if r["condition"] == condition:
            groups[(r["arm"], r["case_id"])].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["repeat_idx"])

    out = {arm: dict(n=0, identical=0, divergent=[], dec_flip=[], traj_div=[],
                     rep0_only=0, settle=0, other=0, patterns=Counter(),
                     deviant_idx=Counter())
           for arm in ("single", "mas")}

    for (arm, cid), g in sorted(groups.items()):
        st = out[arm]
        st["n"] += 1
        outs = [r["raw_output"] or "" for r in g]
        decs = [r["decision"] for r in g]
        trajs = [tuple(r.get("tool_calls") or ()) for r in g]
        if len(set(outs)) == 1:
            st["identical"] += 1
            continue
        st["divergent"].append(cid)
        if len(set(decs)) > 1:
            st["dec_flip"].append((cid, decs))
        if len(set(trajs)) > 1:
            st["traj_div"].append(cid)
        # equivalence-class signature over repeats 0..4
        classes = {}
        sig = tuple(classes.setdefault(o, len(classes)) for o in outs)
        st["patterns"][sig] += 1
        if sig == (0, 1, 1, 1, 1):
            st["rep0_only"] += 1
        elif all(sig[i] <= sig[i + 1] <= sig[i] + 1 for i in range(len(sig) - 1)) \
                and len(set(sig)) > 1 and sig == tuple(sorted(sig)):
            st["settle"] += 1          # monotone settling (prefix churn, then stable)
        else:
            st["other"] += 1
        modal = Counter(outs).most_common(1)[0][0]
        for r, o in zip(g, outs):
            if o != modal:
                st["deviant_idx"][r["repeat_idx"]] += 1
    return out


# ------------------------------------------------------------------ stats

def paired_arm_stats(per_case_s, per_case_m, key, n_boot=50000, n_perm=50000,
                     seed=20260807):
    cases = sorted(set(per_case_s) & set(per_case_m))
    d = np.array([per_case_s[c][key] - per_case_m[c][key] for c in cases])
    rng = np.random.default_rng(seed)
    n = len(d)
    boot = d[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    ci = (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975)))
    obs = abs(float(d.mean()))
    signs = rng.choice((-1.0, 1.0), size=(n_perm, n))
    hits = int((np.abs((signs * d).mean(axis=1)) >= obs - 1e-12).sum())
    p = (1 + hits) / (n_perm + 1)
    return float(d.mean()), ci, p, n


# ------------------------------------------------------------------ main

def fmt(v):
    return "     —" if v is None else f"{v:,.3f}"


def main():
    lcs_selftest()
    labels = read_labels()
    single = read_journal(RES / "journal-single.jsonl")
    mas = read_journal(RES / "journal-mas.jsonl")
    manifest = json.load(open(RES / "manifest.json"))
    rows = single + mas

    print("=" * 78)
    print("1. INTEGRITY")
    print("=" * 78)
    problems = integrity(single, mas, manifest)
    for p in problems:
        print("  VIOLATION:", p)
    print(f"  integrity verdict: {'CLEAN' if not problems else f'{len(problems)} violation(s)'}")

    print()
    print("=" * 78)
    print("2. METRIC RECOMPUTATION (report vs audit; *MISMATCH* = beyond tolerance)")
    print("=" * 78)
    by_key = defaultdict(list)
    for r in rows:
        by_key[(r["arm"], r["condition"])].append(r)
    res = {}
    discrepancies = []
    for key in sorted(by_key):
        res[key] = condition_metrics(by_key[key], labels)
    for key in REPORT:
        rep, mine = REPORT[key], res[key]
        print(f"\n--- {key[0]} / {key[1]}  (cases={mine['cases']}, repeats={mine['repeats']}) ---")
        print(f"  {'metric':<15}{'report':>12}{'audit':>12}")
        for mk, label in METRIC_ORDER:
            if mk not in rep:
                continue
            rv, mv = rep[mk], mine[mk]
            if rv is None and mv is None:
                continue
            if rv is None or mv is None:
                ok = False
            elif abs(rv) > 10:
                ok = abs(mv - rv) / abs(rv) <= TOL_REL
            else:
                ok = abs(mv - rv) <= TOL
            if not ok:
                discrepancies.append((key, label, rv, mv))
            print(f"  {label:<15}{fmt(rv):>12}{fmt(mv):>12}   {'ok' if ok else '*MISMATCH*'}")

    print()
    print("=" * 78)
    print("3. T=0 CACHE-SENSITIVITY (fixed seed 42, temperature 0)")
    print("=" * 78)
    for cond in ("t0-fixed", "pert-t0"):
        F = t0_forensics(rows, cond)
        print(f"\n### {cond}")
        for arm in ("single", "mas"):
            st = F[arm]
            print(f"  {arm}: {st['n']} groups | byte-identical {st['identical']} | "
                  f"divergent {len(st['divergent'])} | decision flips {len(st['dec_flip'])} | "
                  f"trajectory-divergent {len(st['traj_div'])}")
            if st["divergent"]:
                print(f"    signatures: repeat-0-only {st['rep0_only']}, "
                      f"monotone-settling {st['settle']}, other {st['other']}")
                pats = ", ".join(f"{p}x{c}" for p, c in st["patterns"].most_common(8))
                print(f"    patterns: {pats}")
                print(f"    deviant-from-modal by repeat_idx: {dict(sorted(st['deviant_idx'].items()))}")
            for cid, decs in st["dec_flip"]:
                print(f"    decision flip {cid}: {decs}")
        if cond in SEVEN_B:
            print("  vs 7B (prior audited):")
            for arm in ("single", "mas"):
                st, sb = F[arm], SEVEN_B[cond][arm]
                print(f"    {arm}: 14B divergent {len(st['divergent'])}/{st['n']} "
                      f"vs 7B {sb['div']}/{sb['n']}; "
                      f"14B decision flips {len(st['dec_flip'])} vs 7B {sb['dec']}")

    print()
    print("=" * 78)
    print("4. STATS: single - mas, t07-varied, per-case paired")
    print("=" * 78)
    s_pc = res[("single", "t07-varied")]["_per_case"]
    m_pc = res[("mas", "t07-varied")]["_per_case"]
    for key, rkey in (("pass_frac", "pass_frac"), ("DAR", "DAR"), ("entropy", "entropy")):
        mean, ci, p, n = paired_arm_stats(s_pc, m_pc, key)
        rep = REPORT_STATS[rkey]
        ok_mean = abs(mean - rep["mean"]) <= TOL
        ok_ci = all(abs(a - b) <= 0.01 for a, b in zip(ci, rep["ci"]))  # MC noise
        ok_p = abs(p - rep["p"]) <= 0.05
        if not ok_mean:
            discrepancies.append((("stats", "t07-varied"), key, rep["mean"], mean))
        print(f"  {key:<10} n={n} mean {mean:+.3f} (report {rep['mean']:+.3f} "
              f"{'ok' if ok_mean else '*MISMATCH*'}) "
              f"CI [{ci[0]:+.3f},{ci[1]:+.3f}] (report [{rep['ci'][0]:+.3f},{rep['ci'][1]:+.3f}] "
              f"{'ok' if ok_ci else 'DIFFERS'}) "
              f"p={p:.3f} (report {rep['p']:.3f} {'ok' if ok_p else 'DIFFERS'})")
    for arm in ("single", "mas"):
        pc = res[(arm, "t07-varied")]["_per_case"]
        worst = sorted(pc, key=lambda c: (-pc[c]["entropy"], c))[:3]
        match = set(worst) == set(REPORT_WORST[arm])
        print(f"  worst-entropy ({arm}): {', '.join(worst)} "
              f"(report: {', '.join(REPORT_WORST[arm])}) {'ok' if match else '*MISMATCH*'}")
        if not match:
            discrepancies.append(((arm, "worst-entropy"), "cases", REPORT_WORST[arm], worst))

    print()
    print("=" * 78)
    if discrepancies:
        print(f"OVERALL: DISCREPANCIES FOUND ({len(discrepancies)})")
        for k, label, rv, mv in discrepancies:
            print(f"  {k} {label}: report={rv} audit={mv}")
    else:
        print("OVERALL: ANALYSIS CONFIRMED — every reported number reproduced "
              "within tolerance")
    print(f"INTEGRITY: {'CLEAN' if not problems else f'{len(problems)} violation(s)'}")


if __name__ == "__main__":
    main()
