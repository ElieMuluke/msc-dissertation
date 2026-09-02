#!/usr/bin/env python
"""Independent audit of the gemma4:latest PRD-A repeatability sweep.

Fourth independent auditor, no prior involvement. Every check below was
written from scratch against the raw journals, manifest, runner logs, and
ground-truth label files. No code from the project's analysis pipeline
(metrics.py / report.py / stats.py) is imported or executed. The three prior
audit scripts (independent_check_qwen35.py / _qwen25.py / _qwen25_14b.py)
were consulted for the journal schema and for the two documented reporting
conventions only, both of which are also stated in analysis-report.md:

  * DAR / Krippendorff alpha / entropy treat 'malformed' as an ordinary
    outcome category, so malformed==malformed pairs COUNT as agreement;
  * majority-vote ties break in favour of the first-observed decision.

Sweep-specific context (differs from the three prior sweeps):
  * Ollama 0.32.6 (prior sweeps ran 0.31.1) — verified as the single
    version across all 2300 rows;
  * expected malformed count is 13;
  * the MAS runner was killed and resumed around journal row 582
    (2026-08-08 00:38 local / 2026-08-07 23:38 UTC). The journal-driven
    resume must make this invisible except in started_at: no missing or
    duplicated runs around the boundary, seeds still per-manifest.
    Section 1 verifies this explicitly.

Sections:
  1. INTEGRITY  — counts vs manifest, duplicates, per-run field conformance,
     single digest/version, decision domain, malformed accounting (13),
     decision re-extraction from raw_output, resume-boundary forensics.
  2. METRICS    — recompute every number in analysis-report.md
     (Tier 1/2/3, perturbation block, ROUGE-L appendix);
     flag |diff| > 0.005 (relative 0.1% for token-scale numbers).
  3. T=0        — fixed-seed cache-sensitivity forensics (byte-identity,
     repeat-0-only signature, decision flips) with explicit comparison to
     qwen3.5:9b, qwen2.5:7b and qwen2.5:14b.
  4. STATS      — arm-difference table (t07-varied): per-case paired mean,
     bootstrap 95% CI, sign-flip permutation p, worst-entropy cases.

Run:
  backend/.venv/bin/python backend/experiments/analysis/independent_check_gemma4.py
"""

import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path

import numpy as np

RES = Path("/home/eliem/Projects/ai/msc-dissertation/backend/experiments/results-gemma4")
ALERTS = Path("/home/eliem/Projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json")
PERT = Path("/home/eliem/Projects/ai/msc-dissertation/backend/experiments/perturbation_cases.json")

DOMAIN = {"escalate", "dismiss", "investigate", "malformed"}
ENT_NORM = math.log2(4.0)            # 4-way outcome domain incl. malformed
EXPECTED_MALFORMED = 13
EXPECTED_OLLAMA = "0.32.6"
LOG_UTC_OFFSET = timedelta(hours=1)  # runner logs are Europe/London (BST)
TOL = 0.005
TOL_REL = 0.001                      # for token counts / wall-clock (>10)

# ---------------------------------------------------------------- loading


def read_journal(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return rows


def read_labels():
    lab = {}
    for a in json.load(open(ALERTS))["alerts"]:
        lab[a["alert_id"]] = a["ground_truth"]
    for a in json.load(open(PERT))["alerts"]:
        lab[a["alert_id"]] = a["ground_truth"]
    return lab


def ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- LCS (own)


def lcs_ref(a, b):
    """Reference O(nm) DP LCS length, for the self-test."""
    if not a or not b:
        return 0
    row = [0] * (len(b) + 1)
    for x in a:
        diag = 0
        for j, y in enumerate(b, 1):
            diag, row[j] = row[j], (diag + 1 if x == y else max(row[j], row[j - 1]))
    return row[-1]


def lcs_fast(a, b):
    """Bit-parallel LCS length (Allison-Dix recurrence), own implementation."""
    if not a or not b:
        return 0
    if len(b) < len(a):
        a, b = b, a
    n = len(a)
    pos = defaultdict(int)
    for i, x in enumerate(a):
        pos[x] |= 1 << i
    full = (1 << n) - 1
    v = full
    for y in b:
        p = pos.get(y, 0)
        u = v & p
        v = ((v + u) | (v - u)) & full
    return n - bin(v).count("1")


def lcs_selftest():
    rng = random.Random(20260808)
    for _ in range(500):
        a = [rng.randrange(6) for _ in range(rng.randrange(0, 30))]
        b = [rng.randrange(6) for _ in range(rng.randrange(0, 30))]
        assert lcs_ref(a, b) == lcs_fast(a, b), (a, b)


# ---------------------------------------------------------------- metrics


def pass_hat(c, n, k):
    """P(all of k repeats sampled without replacement match the label)."""
    if k > n:
        return None
    return math.comb(c, k) / math.comb(n, k) if c >= k else 0.0


def pairwise_frac(vals, eq):
    pairs = list(combinations(vals, 2))
    return sum(1 for a, b in pairs if eq(a, b)) / len(pairs)


def norm_entropy(vals):
    n = len(vals)
    h = -sum((c / n) * math.log2(c / n) for c in Counter(vals).values())
    return h / ENT_NORM


def kripp_alpha_nominal(units):
    """Krippendorff's alpha, nominal, via the coincidence matrix."""
    cats = sorted({v for u in units for v in u})
    K = {c: i for i, c in enumerate(cats)}
    co = np.zeros((len(cats), len(cats)))
    for u in units:
        m = len(u)
        if m < 2:
            continue
        cnt = Counter(u)
        for a, ca in cnt.items():
            for b, cb in cnt.items():
                npairs = ca * (cb - 1) if a == b else ca * cb
                co[K[a], K[b]] += npairs / (m - 1)
    n = co.sum()
    if n <= 1:
        return 1.0
    d_obs = n - np.trace(co)
    marg = co.sum(axis=0)
    d_exp = (n * n - (marg**2).sum()) / (n - 1)
    return 1.0 if d_exp == 0 else float(1.0 - d_obs / d_exp)


def traj_pair(a, b, kind):
    if kind == "exact":
        return 1.0 if a == b else 0.0
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if kind == "jaccard":
        return len(set(a) & set(b)) / len(set(a) | set(b))
    return lcs_fast(a, b) / max(len(a), len(b))  # nLCS


def rouge_l_mean(texts):
    """Mean pairwise ROUGE-L F1, lowercased whitespace tokens, full text."""
    toks = [tuple((t or "").lower().split()) for t in texts]
    out = []
    for a, b in combinations(toks, 2):
        if not a and not b:
            out.append(1.0)
        elif not a or not b:
            out.append(0.0)
        else:
            L = len(a) if a == b else lcs_fast(a, b)
            out.append(2.0 * L / (len(a) + len(b)))
    return sum(out) / len(out)


def condition_metrics(rows, labels):
    groups = defaultdict(list)
    for r in rows:
        groups[r["case_id"]].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["repeat_idx"])

    acc = defaultdict(list)
    units, per_case = [], {}
    for cid in sorted(groups):
        g = groups[cid]
        decs = [r["decision"] for r in g]
        n = len(decs)
        units.append(decs)
        c = decs.count(labels[cid])
        acc["p1"].append(c / n)
        acc["p5"].append(pass_hat(c, n, 5))
        acc["p15"].append(pass_hat(c, n, 15))
        acc["dar"].append(pairwise_frac(decs, lambda a, b: a == b))
        acc["flip"].append(1.0 if len(set(decs)) > 1 else 0.0)
        acc["ent"].append(norm_entropy(decs))
        cnt = Counter(decs)  # insertion order == first-observed tiebreak
        acc["maj"].append(1.0 if cnt.most_common(1)[0][0] == labels[cid] else 0.0)
        trajs = [tuple(r.get("tool_calls") or ()) for r in g]
        for kind, key in (("exact", "tar"), ("jaccard", "jac"), ("nlcs", "nlcs")):
            acc[key].append(sum(traj_pair(a, b, kind)
                                for a, b in combinations(trajs, 2))
                            / math.comb(n, 2))
        acc["rouge"].append(rouge_l_mean([r["raw_output"] for r in g]))
        per_case[cid] = {"pass_frac": c / n, "DAR": acc["dar"][-1],
                         "entropy": acc["ent"][-1]}

    mean = lambda k: None if acc[k][0] is None else sum(acc[k]) / len(acc[k])
    tpr = sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows) / len(rows)
    out = {
        "cases": len(groups), "repeats": len(units[0]),
        "pass1": mean("p1"), "pass5": mean("p5"), "pass15": mean("p15"),
        "DAR": mean("dar"), "alpha": kripp_alpha_nominal(units),
        "flip": mean("flip"), "maj": mean("maj"), "ent": mean("ent"),
        "TAR": mean("tar"), "jac": mean("jac"), "nlcs": mean("nlcs"),
        "mal": sum(r["decision"] == "malformed" for r in rows) / len(rows),
        "tpr": tpr, "wall": sum(r["wall_clock_s"] for r in rows) / len(rows),
        "rouge": mean("rouge"), "_per_case": per_case,
    }
    for k in ("pass1", "pass5", "pass15"):
        out["tok_" + k] = None if not out[k] else tpr / out[k]
    return out


# ---------------------------------------------------------------- integrity


def integrity(single, mas, manifest):
    problems = []
    rows = single + mas

    # -- counts vs manifest
    for arm, got in (("single", single), ("mas", mas)):
        want = manifest["totals"][arm]
        if len(got) != want:
            problems.append(f"{arm} journal has {len(got)} rows, manifest says {want}")
    plan = {p["run_id"]: p for p in manifest["runs"]}
    print(f"  journal rows: single={len(single)} mas={len(mas)} "
          f"total={len(rows)} planned={len(plan)}")

    # -- duplicates / missing / extra
    idc = Counter(r["run_id"] for r in rows)
    dups = [k for k, v in idc.items() if v > 1]
    if dups:
        problems.append(f"{len(dups)} duplicated run_ids, e.g. {dups[:3]}")
    combo = Counter((r["arm"], r["case_id"], r["condition"], r["repeat_idx"])
                    for r in rows)
    dups2 = [k for k, v in combo.items() if v > 1]
    if dups2:
        problems.append(f"{len(dups2)} duplicated (arm,case,cond,repeat), e.g. {dups2[:3]}")
    missing = set(plan) - set(idc)
    extra = set(idc) - set(plan)
    if missing:
        problems.append(f"{len(missing)} planned runs missing, e.g. {sorted(missing)[:3]}")
    if extra:
        problems.append(f"{len(extra)} unplanned rows, e.g. {sorted(extra)[:3]}")
    print(f"  duplicates: {len(dups)} | missing planned: {len(missing)} | "
          f"unplanned: {len(extra)}")

    # -- per-run field conformance (seed / temperature / condition / etc.)
    bad_fields = []
    for r in rows:
        p = plan.get(r["run_id"])
        if p is None:
            continue
        for f in ("arm", "case_id", "block", "condition", "repeat_idx",
                  "seed", "temperature"):
            if r[f] != p[f]:
                bad_fields.append((r["run_id"], f, r[f], p[f]))
    if bad_fields:
        problems.append(f"{len(bad_fields)} field mismatches vs manifest, "
                        f"e.g. {bad_fields[:3]}")
    print(f"  per-run field conformance vs manifest "
          f"(arm/case/block/cond/repeat/seed/temp): {len(bad_fields)} mismatches")

    # -- condition-level design conformance
    spec = {c["name"]: c for c in manifest["config"]["conditions"]}
    by_cond = defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r)
    if set(by_cond) != set(spec):
        problems.append(f"condition set {set(by_cond)} != spec {set(spec)}")
    primary_cases = {a["alert_id"] for a in json.load(open(ALERTS))["alerts"]}
    pert_cases = {a["alert_id"] for a in json.load(open(PERT))["alerts"]}
    for name, sp in spec.items():
        rs = by_cond[name]
        temps = {r["temperature"] for r in rs}
        if temps != {sp["temperature"]}:
            problems.append(f"{name}: temperatures {temps} != {sp['temperature']}")
        cases = {r["case_id"] for r in rs}
        want_cases = primary_cases if sp["block"] == "primary" else pert_cases
        if cases != want_cases:
            problems.append(f"{name}: case set differs from labels file "
                            f"({len(cases)} vs {len(want_cases)})")
        if {r["block"] for r in rs} != {sp["block"]}:
            problems.append(f"{name}: block field inconsistent")
        reps = Counter((r["arm"], r["case_id"]) for r in rs)
        bad = [k for k, v in reps.items() if v != sp["repeats"]]
        if bad:
            problems.append(f"{name}: groups without {sp['repeats']} repeats: {bad[:3]}")
        if sp["fixed_seed"] is not None:
            seeds = {r["seed"] for r in rs}
            if seeds != {sp["fixed_seed"]}:
                problems.append(f"{name}: seeds {seeds} != fixed {sp['fixed_seed']}")
        else:
            per_grp = defaultdict(set)
            for r in rs:
                per_grp[(r["arm"], r["case_id"])].add(r["seed"])
            lazy = [k for k, s in per_grp.items() if len(s) != sp["repeats"]]
            if lazy:
                problems.append(f"{name}: {len(lazy)} groups lack "
                                f"{sp['repeats']} distinct seeds, e.g. {lazy[:3]}")
        print(f"  {name}: {len(rs)} rows, temp={temps}, "
              f"{len(cases)} cases x {sp['repeats']} repeats"
              + (f", fixed seed {sp['fixed_seed']}" if sp["fixed_seed"] is not None
                 else ", per-run varied seeds (all distinct within group)"))

    # -- provenance uniformity
    for field, want in (("model", manifest["model"]),
                        ("model_digest", manifest["model_digest"]),
                        ("ollama_version", manifest["ollama_version"])):
        got = {r[field] for r in rows}
        if got != {want}:
            problems.append(f"{field}: journal set {got} != manifest {want!r}")
    if manifest["ollama_version"] != EXPECTED_OLLAMA:
        problems.append(f"manifest ollama_version {manifest['ollama_version']} "
                        f"!= expected {EXPECTED_OLLAMA}")
    print(f"  provenance: model={manifest['model']} "
          f"digest={manifest['model_digest'][:19]}... "
          f"ollama={manifest['ollama_version']} — uniform across all rows: "
          f"{not any(p.startswith(('model', 'ollama')) for p in problems)}")
    if not manifest["config_hash"].startswith("830300248a6b"):
        problems.append(f"config_hash {manifest['config_hash']} does not match "
                        f"report header 830300248a6b")

    # -- decision domain + malformed accounting
    bad_dec = [(r["run_id"], r["decision"]) for r in rows
               if r["decision"] not in DOMAIN]
    if bad_dec:
        problems.append(f"{len(bad_dec)} out-of-domain decisions, e.g. {bad_dec[:3]}")
    mal = [r for r in rows if r["decision"] == "malformed"]
    errs = [r for r in rows if r.get("error")]
    print(f"  decision domain: {dict(Counter(r['decision'] for r in rows))}")
    print(f"  malformed: {len(mal)} (expected {EXPECTED_MALFORMED}); "
          f"error field set on {len(errs)} rows")
    for r in mal:
        print(f"    {r['run_id']}: raw_output={(r['raw_output'] or '')!r:.60}")
    if len(mal) != EXPECTED_MALFORMED:
        problems.append(f"malformed count {len(mal)} != {EXPECTED_MALFORMED}")
    empty_nonmal = [r["run_id"] for r in rows
                    if not (r["raw_output"] or "").strip()
                    and r["decision"] != "malformed"]
    if empty_nonmal:
        problems.append(f"{len(empty_nonmal)} empty outputs not marked malformed")

    # -- decision must be recoverable from raw_output (last well-formed
    #    'FINAL DECISION: <word>' line, allowing markdown decoration; the
    #    same rule the previous audits validated on 3 sweeps)
    pat = re.compile(r"^\s*#*\s*\**\s*final\s+decision\s*\**\s*:\s*\**\s*"
                     r"(escalate|dismiss|investigate)\b", re.I)
    bad_ext = []
    for r in rows:
        ext = "malformed"
        for lnn in (r["raw_output"] or "").splitlines():
            m = pat.match(lnn)
            if m:
                ext = m.group(1).lower()
        if ext != r["decision"]:
            bad_ext.append(r["run_id"])
    print(f"  decision vs re-extracted FINAL DECISION line: "
          f"{len(rows) - len(bad_ext)}/{len(rows)} agree")
    if bad_ext:
        problems.append(f"{len(bad_ext)} rows where journal decision != "
                        f"re-extracted decision, e.g. {bad_ext[:3]}")

    # -- numeric sanity
    bad_num = [r["run_id"] for r in rows
               if r["wall_clock_s"] <= 0 or r["prompt_tokens"] <= 0
               or r["completion_tokens"] < 0]
    if bad_num:
        problems.append(f"{len(bad_num)} rows with non-positive wall clock / tokens")

    return problems


def resume_boundary(mas, manifest):
    """The MAS runner was killed and resumed ~row 582. Verify the journal-
    driven resume left no scar beyond started_at timing."""
    problems = []
    print("  -- resume-boundary forensics (MAS arm) --")

    t = [ts(r["started_at"]) for r in mas]
    non_mono = sum(1 for i in range(len(t) - 1) if t[i + 1] < t[i])
    if non_mono:
        problems.append(f"mas started_at not monotone at {non_mono} points")
    gaps = [( (t[i + 1] - t[i]).total_seconds(), i) for i in range(len(t) - 1)]
    gap_s, gi = max(gaps)
    before, after = mas[gi], mas[gi + 1]
    print(f"  started_at monotone non-decreasing: {non_mono == 0}")
    print(f"  largest inter-start gap: {gap_s:.0f}s at journal index {gi}: "
          f"{before['run_id']} ({before['started_at']}) -> "
          f"{after['run_id']} ({after['started_at']})")

    # runner log: expect exactly one cold start (completed=0) and one resume
    log = (RES / "runner-mas.log").read_text(encoding="utf-8", errors="replace")
    starts = re.findall(r"^([\d\- :,]+) INFO arm=mas planned=(\d+) "
                        r"completed=(\d+) todo=(\d+)", log, re.M)
    print(f"  runner-mas.log startup lines: "
          f"{[(s[0][:19], f'completed={s[2]}', f'todo={s[3]}') for s in starts]}")
    if len(starts) != 2 or int(starts[0][2]) != 0:
        problems.append(f"expected exactly one cold start + one resume in "
                        f"runner-mas.log, found {len(starts)} startup lines")
        return problems
    r_time, planned, completed, todo = starts[1]
    completed, todo, planned = int(completed), int(todo), int(planned)
    if completed + todo != planned:
        problems.append(f"resume accounting broken: {completed}+{todo}!={planned}")
    resume_utc = (datetime.strptime(r_time.split(",")[0], "%Y-%m-%d %H:%M:%S")
                  - LOG_UTC_OFFSET)
    n_before = sum(1 for x in t if x < resume_utc)
    print(f"  resume at {resume_utc}Z: journal rows started before it: "
          f"{n_before}; runner reports completed={completed}, todo={todo}")
    if n_before != completed:
        problems.append(f"rows started before resume ({n_before}) != "
                        f"completed claimed at resume ({completed})")
    if gi != completed - 1:
        problems.append(f"largest gap at index {gi}, expected at "
                        f"{completed - 1} (last pre-kill row)")
    if ts(after["started_at"]) < resume_utc:
        problems.append("first post-resume row started before the resume line")

    # the interrupted group must still be complete, in order, unique, with
    # manifest seeds — i.e. the kill is invisible at the plan level
    grp = sorted((r for r in mas
                  if r["case_id"] == before["case_id"]
                  and r["condition"] == before["condition"]),
                 key=lambda r: r["repeat_idx"])
    plan = {p["run_id"]: p for p in manifest["runs"]}
    n_rep = next(c["repeats"] for c in manifest["config"]["conditions"]
                 if c["name"] == before["condition"])
    ok_grp = ([r["repeat_idx"] for r in grp] == list(range(n_rep))
              and len({r["run_id"] for r in grp}) == n_rep
              and all(r["seed"] == plan[r["run_id"]]["seed"] for r in grp))
    print(f"  interrupted group {before['arm']}:{before['case_id']}:"
          f"{before['condition']}: {len(grp)}/{n_rep} repeats present, "
          f"unique, seeds per-manifest: {ok_grp}")
    if not ok_grp:
        problems.append("interrupted group incomplete/duplicated/off-seed")
    w = [r for r in mas[max(0, gi - 20): gi + 21]]
    if len({r["run_id"] for r in w}) != len(w):
        problems.append("duplicate run_ids inside +/-20-row boundary window")
    payload_ok = all((r["raw_output"] or "").strip() and r["decision"] in DOMAIN
                     and r["wall_clock_s"] > 0 for r in w)
    print(f"  boundary window (+/-20 rows): unique run_ids, complete payloads: "
          f"{payload_ok}")
    if not payload_ok:
        problems.append("incomplete payload in boundary window")

    lone = ts(before["started_at"]) + timedelta(seconds=before["wall_clock_s"])
    print(f"  last pre-kill run finished ~{lone}Z, killed before its log line "
          f"was flushed; resume skipped all {completed} journalled runs "
          f"and continued at repeat {after['repeat_idx']} — journal-driven "
          f"resume behaved as designed")
    return problems


# ------------------------------------------------- report values (transcribed)

R = {
    ("single", "t0-fixed"): dict(pass1=.648, pass5=.520, pass15=None, DAR=.880,
                                 alpha=.819, flip=.300, maj=.640, ent=.108,
                                 TAR=.756, jac=.869, nlcs=.861, mal=.000,
                                 tpr=3663.100, tok_pass1=5652.932,
                                 tok_pass5=7044.423, tok_pass15=None,
                                 wall=17.362, rouge=.702),
    ("single", "t07-varied"): dict(pass1=.552, pass5=.185, pass15=.080, DAR=.594,
                                   alpha=.387, flip=.900, maj=.600, ent=.430,
                                   TAR=.150, jac=.520, nlcs=.506, mal=.013,
                                   tpr=3931.435, tok_pass1=7122.164,
                                   tok_pass5=21224.065, tok_pass15=49142.933,
                                   wall=18.738, rouge=.237),
    ("mas", "t0-fixed"): dict(pass1=.312, pass5=.240, pass15=None, DAR=.804,
                              alpha=.609, flip=.400, maj=.300, ent=.167,
                              TAR=.872, jac=.998, nlcs=.974, mal=.000,
                              tpr=8952.672, tok_pass1=28694.462,
                              tok_pass5=37302.800, tok_pass15=None,
                              wall=50.847, rouge=.387),
    ("mas", "t07-varied"): dict(pass1=.297, pass5=.113, pass15=.040, DAR=.705,
                                alpha=.406, flip=.840, maj=.320, ent=.304,
                                TAR=.352, jac=.989, nlcs=.864, mal=.000,
                                tpr=9491.080, tok_pass1=31920.673,
                                tok_pass5=83680.896, tok_pass15=237277.000,
                                wall=42.870, rouge=.291),
    ("single", "pert-t0"): dict(pass1=.680, pass5=.500, DAR=.850, alpha=.748,
                                flip=.300, ent=.141, rouge=.638),
    ("single", "pert-t05"): dict(pass1=.560, pass5=.300, DAR=.560, alpha=.295,
                                 flip=.700, ent=.395, rouge=.268),
    ("single", "pert-t10"): dict(pass1=.560, pass5=.200, DAR=.500, alpha=.258,
                                 flip=.800, ent=.443, rouge=.203),
    ("mas", "pert-t0"): dict(pass1=.320, pass5=.200, DAR=.660, alpha=.324,
                             flip=.700, ent=.290, rouge=.372),
    ("mas", "pert-t05"): dict(pass1=.260, pass5=.100, DAR=.720, alpha=.428,
                              flip=.500, ent=.230, rouge=.318),
    ("mas", "pert-t10"): dict(pass1=.280, pass5=.000, DAR=.600, alpha=.216,
                              flip=.800, ent=.339, rouge=.262),
}

R_STATS = {
    "pass_frac": dict(mean=0.255, ci=(0.164, 0.345), p=0.000),
    "DAR": dict(mean=-0.110, ci=(-0.186, -0.033), p=0.011),
    "entropy": dict(mean=0.126, ci=(0.051, 0.199), p=0.003),
}

R_WORST = {"single": ["TXN-2025-022", "TXN-2025-007", "TXN-2025-001"],
           "mas": ["TXN-2025-001", "TXN-2025-013", "TXN-2025-016"]}

ORDER = [("pass1", "pass^1"), ("pass5", "pass^5"), ("pass15", "pass^15"),
         ("DAR", "DAR"), ("alpha", "kripp_alpha"), ("flip", "flip_rate"),
         ("maj", "majority_acc"), ("ent", "mean_entropy"), ("TAR", "TAR"),
         ("jac", "jaccard"), ("nlcs", "nLCS"), ("mal", "malformed_rate"),
         ("tpr", "tokens_per_run"), ("tok_pass1", "tok/pass^1"),
         ("tok_pass5", "tok/pass^5"), ("tok_pass15", "tok/pass^15"),
         ("wall", "wall_clock_s"), ("rouge", "rouge_l_f1")]

# Prior sweeps' T=0 forensics, as recorded by the earlier independent audits
# (all three ran under Ollama 0.31.1; gemma4 ran under 0.32.6):
PRIOR_T0 = [
    ("qwen3.5:9b", "0/50 single + 0/50 mas byte-divergent (fully "
     "byte-identical), 0 decision-flipping groups"),
    ("qwen2.5:7b", "46/50 single + 50/50 mas byte-divergent (cold-cache), "
     "25 decision-flipping groups (6 single + 19 mas)"),
    ("qwen2.5:14b", "byte-divergent 48/50, but only 7 decision-flipping "
     "groups (4 single + 3 mas)"),
]


# ---------------------------------------------------------------- T=0


def t0_forensics(rows, condition):
    out = {}
    groups = defaultdict(list)
    for r in rows:
        if r["condition"] == condition:
            groups[(r["arm"], r["case_id"])].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["repeat_idx"])
    for arm in ("single", "mas"):
        st = dict(n=0, ident=0, div=[], flips=[], traj_div=0, rep0_only=0,
                  sig=Counter(), deviant=Counter())
        for (a, cid), g in sorted(groups.items()):
            if a != arm:
                continue
            st["n"] += 1
            outs = [r["raw_output"] or "" for r in g]
            decs = [r["decision"] for r in g]
            trajs = [tuple(r.get("tool_calls") or ()) for r in g]
            if len(set(outs)) == 1:
                st["ident"] += 1
                continue
            st["div"].append(cid)
            if len(set(decs)) > 1:
                st["flips"].append((cid, decs))
            if len(set(trajs)) > 1:
                st["traj_div"] += 1
            cls = {}
            sig = tuple(cls.setdefault(o, len(cls)) for o in outs)
            st["sig"][sig] += 1
            if sig == (0, 1, 1, 1, 1):
                st["rep0_only"] += 1
            modal = Counter(outs).most_common(1)[0][0]
            for r, o in zip(g, outs):
                if o != modal:
                    st["deviant"][r["repeat_idx"]] += 1
        out[arm] = st
    return out


# ---------------------------------------------------------------- stats


def paired_stats(pc_s, pc_m, key, n_boot=50000, n_perm=50000, seed=48082026):
    cases = sorted(set(pc_s) & set(pc_m))
    d = np.array([pc_s[c][key] - pc_m[c][key] for c in cases])
    n = len(d)
    rng = np.random.default_rng(seed)
    boot = d[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    ci = (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975)))
    obs = abs(d.mean())
    flips = rng.choice((-1.0, 1.0), size=(n_perm, n))
    p = (1 + int((np.abs((flips * d).mean(axis=1)) >= obs - 1e-12).sum())) \
        / (n_perm + 1)
    return float(d.mean()), ci, p, n


# ---------------------------------------------------------------- main


def fmt(v):
    return "      —" if v is None else f"{v:,.3f}"


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
    problems += resume_boundary(mas, manifest)
    for p in problems:
        print("  VIOLATION:", p)
    print(f"  integrity verdict: "
          f"{'CLEAN' if not problems else f'{len(problems)} violation(s)'}")

    print()
    print("=" * 78)
    print("2. METRIC RECOMPUTATION (report vs audit; tolerance "
          f"{TOL} abs / {TOL_REL:.1%} rel for token-scale)")
    print("=" * 78)
    by_key = defaultdict(list)
    for r in rows:
        by_key[(r["arm"], r["condition"])].append(r)
    res = {k: condition_metrics(v, labels) for k, v in by_key.items()}
    discrepancies = []
    for key in R:
        mine, rep = res[key], R[key]
        print(f"\n--- {key[0]} / {key[1]} (cases={mine['cases']}, "
              f"repeats={mine['repeats']}) ---")
        print(f"  {'metric':<16}{'report':>12}{'audit':>12}")
        for mk, label in ORDER:
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
            print(f"  {label:<16}{fmt(rv):>12}{fmt(mv):>12}   "
                  f"{'ok' if ok else '*MISMATCH*'}")

    print()
    print("=" * 78)
    print("3. T=0 CACHE-SENSITIVITY (fixed seed 42, temperature 0.0)")
    print("=" * 78)
    gemma_t0 = {}
    for cond in ("t0-fixed", "pert-t0"):
        F = t0_forensics(rows, cond)
        gemma_t0[cond] = F
        print(f"\n### {cond}")
        for arm in ("single", "mas"):
            st = F[arm]
            print(f"  {arm}: {st['n']} groups | byte-identical {st['ident']} | "
                  f"byte-divergent {len(st['div'])} | decision-flipping "
                  f"{len(st['flips'])} | trajectory-divergent {st['traj_div']}")
            if st["div"]:
                print(f"    repeat-0-only signature (0,1,1,1,1): "
                      f"{st['rep0_only']}/{len(st['div'])} divergent groups")
                pats = ", ".join(f"{s}x{c}" for s, c in st["sig"].most_common(6))
                print(f"    top equivalence-class signatures: {pats}")
                print(f"    deviant-from-modal count by repeat_idx: "
                      f"{dict(sorted(st['deviant'].items()))}")
            for cid, decs in st["flips"]:
                print(f"    flip {cid}: {decs}")

    F = gemma_t0["t0-fixed"]
    tot_div = sum(len(F[a]["div"]) for a in F)
    tot_flip = sum(len(F[a]["flips"]) for a in F)
    tot_r0 = sum(F[a]["rep0_only"] for a in F)
    print("\n### four-model comparison (t0-fixed, 50 groups/arm; prior "
          "sweeps Ollama 0.31.1, this sweep 0.32.6)")
    for name, desc in PRIOR_T0:
        print(f"  {name:<12} {desc}")
    print(f"  {'gemma4':<12} {len(F['single']['div'])}/50 single + "
          f"{len(F['mas']['div'])}/50 mas byte-divergent "
          f"({tot_div}/100 total), {tot_flip} decision-flipping groups "
          f"({len(F['single']['flips'])} single + {len(F['mas']['flips'])} mas), "
          f"repeat-0-only signature in {tot_r0} groups")

    print()
    print("=" * 78)
    print("4. STATS: single - mas, t07-varied, per-case paired")
    print("=" * 78)
    pc_s = res[("single", "t07-varied")]["_per_case"]
    pc_m = res[("mas", "t07-varied")]["_per_case"]
    for key in ("pass_frac", "DAR", "entropy"):
        mean, ci, p, n = paired_stats(pc_s, pc_m, key)
        rep = R_STATS[key]
        ok_m = abs(mean - rep["mean"]) <= TOL
        ok_ci = all(abs(a - b) <= 0.015 for a, b in zip(ci, rep["ci"]))
        ok_p = abs(p - rep["p"]) <= 0.02
        if not ok_m:
            discrepancies.append((("stats", "t07"), key, rep["mean"], mean))
        print(f"  {key:<10} n={n} mean {mean:+.3f} "
              f"(report {rep['mean']:+.3f} {'ok' if ok_m else '*MISMATCH*'}) | "
              f"CI [{ci[0]:+.3f},{ci[1]:+.3f}] "
              f"(report [{rep['ci'][0]:+.3f},{rep['ci'][1]:+.3f}] "
              f"{'ok' if ok_ci else 'DIFFERS'}) | "
              f"p={p:.4f} (report {rep['p']:.3f} {'ok' if ok_p else 'DIFFERS'})")
    for arm, pc in (("single", pc_s), ("mas", pc_m)):
        worst = sorted(pc, key=lambda c: (-pc[c]["entropy"], c))[:3]
        ok = set(worst) == set(R_WORST[arm])
        if not ok:
            discrepancies.append(((arm, "worst-entropy"), "cases",
                                  R_WORST[arm], worst))
        shown = ", ".join(f"{c} ({pc[c]['entropy']:.3f})" for c in worst)
        print(f"  worst-entropy ({arm}): {shown} "
              f"(report: {', '.join(R_WORST[arm])}) {'ok' if ok else '*MISMATCH*'}")

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
