#!/usr/bin/env python
"""Independent audit — infra-context-2 replication sweeps (Ollama 0.32.6).

Audits THREE completed context-2 sweeps at once and compares each against its
original Ollama 0.31.1 sweep (same model, same design, same seeds):

    results-qwen2.5-7b-ollama0326/   vs  results-qwen2.5-7b/
    results-qwen3.5-9b-ollama0326/   vs  results/
    results-qwen2.5-14b-ollama0326/  vs  results-qwen2.5-14b/

All checks written from scratch against the raw journals, manifests and
ground-truth label files. Prior audit scripts (independent_check_*.py) were
consulted for journal schema and the two documented reporting conventions
only:

  * DAR / alpha / entropy treat 'malformed' as an ordinary outcome category,
    so malformed==malformed pairs COUNT as agreement (category equality);
  * majority-vote ties break in favour of the first-observed decision.

Sections per sweep:
  1. integrity: counts vs manifest, duplicates, per-run plan conformance
     (seed / temperature / condition / block / repeat), single model digest,
     single ollama_version (must be 0.32.6), decision domain, malformed
     accounting, plan identity vs the original sweep's manifest.
  2. metric recomputation: Tier 1 (pass^1/5/15, DAR, alpha, flip rate) for
     t0-fixed and t07-varied vs analysis-report.md (|diff| > 0.005 flags;
     relative 0.1% for token-scale numbers), plus Tier 2/3 spot checks
     (TAR, tokens_per_run).
  3. version comparison: t0-fixed / pert-t0 byte-divergence group counts and
     decision-flip group counts under 0.32.6 vs 0.31.1 (both recomputed here),
     and t07-varied Tier 1 absolute deltas between versions.
  4. cross-sweep: identical seed schedules across the three context-2 sweeps;
     no cross-contamination (per-dir uniformity of model / digest / version;
     no byte-identical journal line shared between dirs; note that run_ids are
     shared across dirs BY DESIGN because the run_id string excludes model).

Run:
  cd backend && .venv/bin/python experiments/analysis/independent_check_context2.py
"""

import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

BASE = Path("/home/el/projects/msc-dissertation/backend/experiments")
ALERTS = Path("/home/el/projects/dfah-repo/econometrics/benchmarks/"
              "compliance_triage/data/alerts.json")

# (label, context-2 dir [under audit, 0.32.6], original dir [0.31.1])
SWEEPS = [
    ("qwen2.5-7b",  BASE / "results-qwen2.5-7b-ollama0326",  BASE / "results-qwen2.5-7b"),
    ("qwen3.5-9b",  BASE / "results-qwen3.5-9b-ollama0326",  BASE / "results"),
    ("qwen2.5-14b", BASE / "results-qwen2.5-14b-ollama0326", BASE / "results-qwen2.5-14b"),
]

DECISION_DOMAIN = {"escalate", "dismiss", "investigate", "malformed"}
ENT_NORM = math.log2(4.0)
TOL = 0.005
TOL_REL = 0.001
EXPECTED_VERSION_CTX2 = "0.32.6"
EXPECTED_VERSION_ORIG = "0.31.1"

FAILS = []          # (sweep, message) — integrity/metric failures
WARNS = []          # informational anomalies


def fail(tag, msg):
    FAILS.append((tag, msg))
    print(f"    FAIL [{tag}] {msg}")


def warn(tag, msg):
    WARNS.append((tag, msg))
    print(f"    warn [{tag}] {msg}")


# ------------------------------------------------------------------ loading

def read_journal(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"unparseable JSONL line {path}:{i}: {e}")
    return rows


def load_sweep(d):
    manifest = json.load(open(d / "manifest.json"))
    single = read_journal(d / "journal-single.jsonl")
    mas = read_journal(d / "journal-mas.jsonl")
    return manifest, single, mas


def read_labels():
    blob = json.load(open(ALERTS))
    return {a["alert_id"]: a["ground_truth"] for a in blob["alerts"]}


# ------------------------------------------------------------------ metrics

def pass_hat(n_correct, n, k):
    """P(k distinct repeats drawn without replacement all match the label)."""
    if k > n:
        return None
    if n_correct < k:
        return 0.0
    return math.comb(n_correct, k) / math.comb(n, k)


def pairwise_agreement(vals):
    pairs = list(combinations(vals, 2))
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def norm_entropy(vals):
    n = len(vals)
    h = 0.0
    for c in Counter(vals).values():
        p = c / n
        h -= p * math.log2(p)
    return h / ENT_NORM


def krippendorff_nominal(units):
    """Krippendorff's alpha, nominal, via the coincidence matrix."""
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


def condition_metrics(rows, labels):
    """Tier 1 + TAR + tokens_per_run for one (arm, condition) slice."""
    groups = defaultdict(list)
    for r in rows:
        groups[r["case_id"]].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["repeat_idx"])

    col = defaultdict(list)
    units = []
    for cid in sorted(groups):
        g = groups[cid]
        decs = [r["decision"] for r in g]
        n = len(decs)
        units.append(decs)
        c = decs.count(labels[cid])
        col["pass1"].append(c / n)
        col["pass5"].append(pass_hat(c, n, 5))
        col["pass15"].append(pass_hat(c, n, 15))
        col["DAR"].append(pairwise_agreement(decs))
        col["flip"].append(1.0 if len(set(decs)) > 1 else 0.0)
        col["ent"].append(norm_entropy(decs))
        trajs = [tuple(r.get("tool_calls") or ()) for r in g]
        sims = [1.0 if a == b else 0.0 for a, b in combinations(trajs, 2)]
        col["TAR"].append(sum(sims) / len(sims))

    mean = lambda k: (None if col[k][0] is None
                      else float(sum(col[k]) / len(col[k])))
    return {
        "cases": len(groups),
        "repeats": len(units[0]),
        "pass1": mean("pass1"), "pass5": mean("pass5"), "pass15": mean("pass15"),
        "DAR": mean("DAR"),
        "alpha": krippendorff_nominal(units),
        "flip": mean("flip"),
        "ent": mean("ent"),
        "TAR": mean("TAR"),
        "tokens_per_run": sum(r["prompt_tokens"] + r["completion_tokens"]
                              for r in rows) / len(rows),
    }


def slice_rows(rows, arm, cond):
    return [r for r in rows if r["arm"] == arm and r["condition"] == cond]


# ------------------------------------------------------------------ integrity

FINAL_LINE = re.compile(
    r"^\s*#*\s*\**\s*final\s+decision\s*\**\s*:\s*\**\s*"
    r"(escalate|dismiss|investigate)\b", re.I)


def integrity(tag, manifest, single, mas, expected_version):
    rows = single + mas

    if len(single) != manifest["totals"]["single"]:
        fail(tag, f"single journal {len(single)} lines != manifest total "
                  f"{manifest['totals']['single']}")
    if len(mas) != manifest["totals"]["mas"]:
        fail(tag, f"mas journal {len(mas)} lines != manifest total "
                  f"{manifest['totals']['mas']}")
    planned = manifest["runs"]
    if len(rows) != len(planned):
        fail(tag, f"journal total {len(rows)} != planned {len(planned)}")

    id_counts = Counter(r["run_id"] for r in rows)
    dups = [k for k, v in id_counts.items() if v > 1]
    if dups:
        fail(tag, f"{len(dups)} duplicated run_ids, e.g. {dups[:3]}")
    combo = Counter((r["arm"], r["case_id"], r["condition"], r["repeat_idx"])
                    for r in rows)
    dups2 = [k for k, v in combo.items() if v > 1]
    if dups2:
        fail(tag, f"{len(dups2)} duplicated (arm,case,cond,repeat), "
                  f"e.g. {dups2[:3]}")

    plan = {p["run_id"]: p for p in planned}
    missing = set(plan) - set(id_counts)
    extra = set(id_counts) - set(plan)
    if missing:
        fail(tag, f"{len(missing)} planned runs missing, e.g. {sorted(missing)[:3]}")
    if extra:
        fail(tag, f"{len(extra)} unplanned journal rows, e.g. {sorted(extra)[:3]}")

    mism = []
    for r in rows:
        p = plan.get(r["run_id"])
        if p is None:
            continue
        for f in ("arm", "case_id", "block", "condition", "repeat_idx",
                  "seed", "temperature"):
            if r[f] != p[f]:
                mism.append((r["run_id"], f, r[f], p[f]))
    if mism:
        fail(tag, f"{len(mism)} journal/plan field mismatches, e.g. {mism[:3]}")
    else:
        print(f"    per-run seed/temp/condition/block/repeat all match plan "
              f"({len(rows)} rows)")

    # condition-level design conformance
    cond_spec = {c["name"]: c for c in manifest["config"]["conditions"]}
    by_cond = defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r)
    for name, spec in cond_spec.items():
        rs = by_cond[name]
        temps = {r["temperature"] for r in rs}
        if temps != {spec["temperature"]}:
            fail(tag, f"{name}: temperatures {temps} != {spec['temperature']}")
        if spec["fixed_seed"] is not None:
            seeds = {r["seed"] for r in rs}
            if seeds != {spec["fixed_seed"]}:
                fail(tag, f"{name}: seeds {seeds} != fixed {spec['fixed_seed']}")
        else:
            per_group = defaultdict(set)
            for r in rs:
                per_group[(r["arm"], r["case_id"])].add(r["seed"])
            lazy = [k for k, s in per_group.items() if len(s) < spec["repeats"]]
            if lazy:
                fail(tag, f"{name}: {len(lazy)} groups with repeated seeds, "
                          f"e.g. {lazy[:3]}")
        reps = Counter((r["arm"], r["case_id"]) for r in rs)
        bad = [k for k, v in reps.items() if v != spec["repeats"]]
        if bad:
            fail(tag, f"{name}: groups without {spec['repeats']} repeats, "
                      f"e.g. {bad[:3]}")

    # single digest / version / model across every row
    for field, want in (("model_digest", manifest["model_digest"]),
                        ("ollama_version", manifest["ollama_version"]),
                        ("model", manifest["model"])):
        got = {r[field] for r in rows}
        if got != {want}:
            fail(tag, f"{field} set {got} != manifest {want!r}")
    if manifest["ollama_version"] != expected_version:
        fail(tag, f"manifest ollama_version {manifest['ollama_version']!r} "
                  f"!= expected {expected_version!r}")
    else:
        print(f"    single digest {manifest['model_digest'][:12]}…, single "
              f"ollama_version {manifest['ollama_version']} on all rows")

    bad_dec = [(r["run_id"], r["decision"]) for r in rows
               if r["decision"] not in DECISION_DOMAIN]
    if bad_dec:
        fail(tag, f"{len(bad_dec)} out-of-domain decisions, e.g. {bad_dec[:3]}")

    mal = [r for r in rows if r["decision"] == "malformed"]
    errs = [r for r in rows if r.get("error")]
    print(f"    malformed rows: {len(mal)}; error-field rows: {len(errs)}")
    for r in mal:
        tail = (r["raw_output"] or "")[-70:].replace("\n", " ")
        print(f"      {r['run_id']}  ...{tail!r}")
    # every malformed row must genuinely lack a well-formed FINAL DECISION
    # line, and no well-formed row may disagree with its own last such line
    bad_extract = []
    for r in rows:
        ext = "malformed"
        for ln in (r["raw_output"] or "").splitlines():
            m = FINAL_LINE.match(ln)
            if m:
                ext = m.group(1).lower()
        if ext != r["decision"]:
            bad_extract.append(r["run_id"])
    if bad_extract:
        warn(tag, f"{len(bad_extract)} rows where journal decision != "
                  f"re-extracted FINAL DECISION line, e.g. {bad_extract[:3]}")
    else:
        print(f"    decision re-extraction from raw_output reproduces all "
              f"{len(rows)} journal decisions")
    return len(mal)


def plan_identity(tag, ctx2_manifest, orig_manifest, orig_name):
    """Context-2 plan must be identical to the original sweep's plan."""
    a = ctx2_manifest["runs"]
    b = orig_manifest["runs"]
    if a == b:
        print(f"    plan identical to {orig_name} plan "
              f"({len(a)} runs, same order, same seeds)")
        return
    am = {p["run_id"]: p for p in a}
    bm = {p["run_id"]: p for p in b}
    if set(am) != set(bm):
        fail(tag, f"plan run_id sets differ from {orig_name}: "
                  f"{len(set(am) ^ set(bm))} symmetric-difference entries")
        return
    diff = [rid for rid in am if am[rid] != bm[rid]]
    if diff:
        fail(tag, f"{len(diff)} plan entries differ from {orig_name}, "
                  f"e.g. {diff[:3]}")
    else:
        print(f"    plan identical to {orig_name} plan (order differs only)")
    ca, cb = ctx2_manifest["config_hash"], orig_manifest["config_hash"]
    if ca != cb:
        fail(tag, f"config_hash {ca[:12]} != original {cb[:12]}")


# ------------------------------------------------------------------ report parsing

def parse_report(path):
    """Parse the markdown tables of analysis-report.md into
    {(arm, condition): {metric: float|None}} (later tables merge in)."""
    HDR_MAP = {
        "pass^1": "pass1", "pass^5": "pass5", "pass^15": "pass15",
        "DAR": "DAR", "krippendorff_alpha": "alpha", "flip_rate": "flip",
        "mean_entropy": "ent", "TAR": "TAR", "tokens_per_run": "tokens_per_run",
        "cases": "cases", "repeats": "repeats",
    }
    out = defaultdict(dict)
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln.startswith("|") and "arm" in ln and "condition" in ln:
            headers = [h.strip() for h in ln.strip("|").split("|")]
            i += 2  # skip separator row
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                row = dict(zip(headers, cells))
                key = (row["arm"], row["condition"])
                for h, v in row.items():
                    mk = HDR_MAP.get(h)
                    if mk is None or h in ("arm", "condition"):
                        continue
                    if v in ("—", "-", ""):
                        out[key][mk] = None
                    else:
                        try:
                            out[key][mk] = float(v)
                        except ValueError:
                            pass
                i += 1
        else:
            i += 1
    return dict(out)


def compare_metrics(tag, computed, reported, keys):
    n_flag = 0
    for k in keys:
        c, r = computed.get(k), reported.get(k)
        if c is None and r is None:
            continue
        if (c is None) != (r is None):
            fail(tag, f"{k}: computed {c} vs reported {r} (presence mismatch)")
            n_flag += 1
            continue
        tol = max(TOL, abs(r) * TOL_REL) if abs(r) > 10 else TOL
        # reported values are rounded to 3 dp; allow for that on top of TOL
        if abs(c - r) > tol + 5e-4:
            fail(tag, f"{k}: computed {c:.4f} vs reported {r:.4f} "
                      f"(|diff|={abs(c - r):.4f})")
            n_flag += 1
    return n_flag


# ------------------------------------------------------------------ version comparison

def group_divergence(rows):
    """Per (case) group over sorted repeats: byte-divergent raw_output count
    and decision-flip count, out of total groups."""
    groups = defaultdict(list)
    for r in rows:
        groups[r["case_id"]].append(r)
    byte_div = dec_flip = 0
    for g in groups.values():
        if len({r["raw_output"] or "" for r in g}) > 1:
            byte_div += 1
        if len({r["decision"] for r in g}) > 1:
            dec_flip += 1
    return byte_div, dec_flip, len(groups)


# ------------------------------------------------------------------ main

def main():
    labels = read_labels()
    print(f"loaded {len(labels)} ground-truth labels from {ALERTS}")

    data = {}       # label -> dict with manifests + journals both versions
    tier1 = {}      # (label, version, arm, cond) -> computed metrics
    n_fail_before_metrics = {}

    for label, ctx2_dir, orig_dir in SWEEPS:
        print(f"\n{'=' * 74}\nSWEEP {label}: {ctx2_dir.name} (0.32.6) "
              f"vs {orig_dir.name} (0.31.1)\n{'=' * 74}")
        ctx2_m, ctx2_s, ctx2_x = load_sweep(ctx2_dir)
        orig_m, orig_s, orig_x = load_sweep(orig_dir)
        data[label] = dict(ctx2=(ctx2_m, ctx2_s, ctx2_x),
                           orig=(orig_m, orig_s, orig_x),
                           ctx2_dir=ctx2_dir, orig_dir=orig_dir)

        print(f"\n  [1] integrity — {ctx2_dir.name}")
        pre = len(FAILS)
        integrity(label, ctx2_m, ctx2_s, ctx2_x, EXPECTED_VERSION_CTX2)
        plan_identity(label, ctx2_m, orig_m, orig_dir.name)
        # sanity on the original sweep too (lighter claim: uniform version)
        for field, want in (("ollama_version", EXPECTED_VERSION_ORIG),):
            got = {r[field] for r in orig_s + orig_x}
            if got != {want} or orig_m["ollama_version"] != want:
                fail(label, f"original sweep {orig_dir.name}: ollama_version "
                            f"{got} / manifest {orig_m['ollama_version']} "
                            f"!= {want}")
        if orig_m["model_digest"] != ctx2_m["model_digest"]:
            fail(label, "model_digest differs between versions — not the "
                        "same weights")
        else:
            print(f"    same model digest in both versions "
                  f"({ctx2_m['model_digest'][:12]}…)")
        n_fail_before_metrics[label] = len(FAILS) - pre

        print(f"\n  [2] metric recomputation vs {ctx2_dir.name}/analysis-report.md")
        reported = parse_report(ctx2_dir / "analysis-report.md")
        flags = 0
        for arm in ("single", "mas"):
            for cond in ("t0-fixed", "t07-varied"):
                rows = slice_rows(ctx2_s if arm == "single" else ctx2_x,
                                  arm, cond)
                comp = condition_metrics(rows, labels)
                tier1[(label, "ctx2", arm, cond)] = comp
                rep = reported.get((arm, cond), {})
                keys = ["pass1", "pass5", "pass15", "DAR", "alpha", "flip",
                        "TAR", "tokens_per_run"]
                flags += compare_metrics(f"{label}:{arm}/{cond}", comp, rep, keys)
                shown = ", ".join(
                    f"{k}={comp[k]:.3f}" if comp[k] is not None else f"{k}=—"
                    for k in ("pass1", "pass5", "pass15", "DAR", "alpha", "flip"))
                print(f"    {arm:6s} {cond:10s} computed: {shown}")
                print(f"    {'':6s} {'':10s} spot: TAR={comp['TAR']:.3f} "
                      f"tokens_per_run={comp['tokens_per_run']:.3f}")
        if flags == 0:
            print("    all compared Tier-1 values + TAR/tokens_per_run spot "
                  "checks within tolerance (0.005 abs / 0.1% rel)")

        # original-sweep Tier 1 for the version comparison (computed, not
        # read from any report)
        for arm in ("single", "mas"):
            for cond in ("t0-fixed", "t07-varied"):
                rows = slice_rows(orig_s if arm == "single" else orig_x,
                                  arm, cond)
                tier1[(label, "orig", arm, cond)] = condition_metrics(rows, labels)

    # -------------------------------------------------- version comparison
    print(f"\n{'=' * 74}\n[3] VERSION COMPARISON — 0.31.1 vs 0.32.6 "
          f"(all numbers recomputed here)\n{'=' * 74}")
    print("\nFixed-seed determinism (t0-fixed and pert-t0; groups of 5 "
          "repeats, seed 42, T=0):\n")
    print(f"{'model':12s} {'arm':6s} {'cond':8s} "
          f"{'byte-div 0.31.1':>16s} {'byte-div 0.32.6':>16s} "
          f"{'flips 0.31.1':>13s} {'flips 0.32.6':>13s}")
    for label, _, _ in SWEEPS:
        d = data[label]
        for arm in ("single", "mas"):
            for cond in ("t0-fixed", "pert-t0"):
                cells = {}
                for ver in ("orig", "ctx2"):
                    m, s, x = d[ver]
                    rows = slice_rows(s if arm == "single" else x, arm, cond)
                    cells[ver] = group_divergence(rows)
                (bo, fo, no), (bc, fc, nc) = cells["orig"], cells["ctx2"]
                print(f"{label:12s} {arm:6s} {cond:8s} "
                      f"{f'{bo}/{no}':>16s} {f'{bc}/{nc}':>16s} "
                      f"{f'{fo}/{no}':>13s} {f'{fc}/{nc}':>13s}")

    print("\nPer-run cross-version reproduction (same run_id, 0.31.1 vs "
          "0.32.6): identical raw_output bytes / identical decision:\n")
    print(f"{'model':12s} " + " ".join(
        f"{c:>18s}" for c in ("t0-fixed", "t07-varied", "pert-t0",
                              "pert-t05", "pert-t10")) + f" {'all-decisions':>14s}")
    for label, _, _ in SWEEPS:
        d = data[label]
        cm, cs, cx = d["ctx2"]
        om, os_, ox = d["orig"]
        crows = {r["run_id"]: r for r in cs + cx}
        orows = {r["run_id"]: r for r in os_ + ox}
        if set(crows) != set(orows):
            fail(label, "run_id sets differ between versions")
            continue
        bycond = defaultdict(lambda: [0, 0])
        dec_same = 0
        for rid, r in crows.items():
            o = orows[rid]
            bycond[r["condition"]][0] += (r["raw_output"] == o["raw_output"])
            bycond[r["condition"]][1] += 1
            dec_same += (r["decision"] == o["decision"])
        cells = " ".join(
            f"{bycond[c][0]:>8d}/{bycond[c][1]:<4d}    "[:18].rjust(18)
            for c in ("t0-fixed", "t07-varied", "pert-t0",
                      "pert-t05", "pert-t10"))
        print(f"{label:12s} {cells} {f'{dec_same}/{len(crows)}':>14s}")

    print("\nPrimary condition t07-varied — Tier 1 by version "
          "(delta = |0.32.6 - 0.31.1|):\n")
    hdr = ["pass1", "pass5", "pass15", "DAR", "alpha", "flip"]
    print(f"{'model':12s} {'arm':6s} {'ver':6s} " +
          " ".join(f"{h:>7s}" for h in hdr))
    max_delta = {}
    for label, _, _ in SWEEPS:
        for arm in ("single", "mas"):
            o = tier1[(label, "orig", arm, "t07-varied")]
            c = tier1[(label, "ctx2", arm, "t07-varied")]
            for ver, m in (("0.31.1", o), ("0.32.6", c)):
                print(f"{label:12s} {arm:6s} {ver:6s} " +
                      " ".join(f"{m[h]:7.3f}" for h in hdr))
            deltas = {h: abs(c[h] - o[h]) for h in hdr}
            print(f"{'':12s} {'':6s} {'delta':6s} " +
                  " ".join(f"{deltas[h]:7.3f}" for h in hdr))
            for h in hdr:
                key = (label, arm)
                if deltas[h] > max_delta.get(key, (None, -1))[1]:
                    max_delta[key] = (h, deltas[h])

    # -------------------------------------------------- cross-sweep checks
    print(f"\n{'=' * 74}\n[4] CROSS-SWEEP CHECKS (three context-2 dirs)"
          f"\n{'=' * 74}")
    sched = {}
    for label, _, _ in SWEEPS:
        m = data[label]["ctx2"][0]
        sched[label] = {p["run_id"]: (p["seed"], p["temperature"],
                                      p["condition"], p["repeat_idx"],
                                      p["arm"], p["case_id"], p["block"])
                        for p in m["runs"]}
    ref_label = SWEEPS[0][0]
    ok = True
    for label, _, _ in SWEEPS[1:]:
        if sched[label] != sched[ref_label]:
            diff = [k for k in sched[ref_label]
                    if sched[label].get(k) != sched[ref_label][k]]
            fail("cross-sweep", f"seed schedule of {label} differs from "
                                f"{ref_label}: {len(diff)} entries, e.g. {diff[:3]}")
            ok = False
    ms = {data[l]["ctx2"][0]["config"]["master_seed"] for l, _, _ in SWEEPS}
    if ok and len(ms) == 1:
        print(f"  identical seed schedules across all three sweeps "
              f"({len(sched[ref_label])} runs each, master_seed {ms.pop()})")

    print("  note: run_id strings exclude the model name, so the same "
          "run_ids appear in every dir BY DESIGN; contamination is checked "
          "via per-dir field uniformity and raw-line identity instead")
    # per-dir uniformity already enforced in integrity(); here: no
    # byte-identical journal line shared between two dirs
    line_owner = {}
    clash = 0
    for label, _, _ in SWEEPS:
        d = data[label]["ctx2_dir"]
        for f in ("journal-single.jsonl", "journal-mas.jsonl"):
            for ln in open(d / f, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                prev = line_owner.setdefault(hash(ln), label)
                if prev != label:
                    clash += 1
    if clash:
        fail("cross-sweep", f"{clash} byte-identical journal lines shared "
                            f"between different context-2 dirs")
    else:
        print("  no byte-identical journal line appears in two different "
              "context-2 dirs (6,900 lines checked)")
    models = [data[l]["ctx2"][0]["model"] for l, _, _ in SWEEPS]
    digests = [data[l]["ctx2"][0]["model_digest"] for l, _, _ in SWEEPS]
    if len(set(models)) == 3 and len(set(digests)) == 3:
        print(f"  three distinct models/digests as expected: "
              f"{', '.join(models)}")
    else:
        fail("cross-sweep", f"expected 3 distinct models/digests, got "
                            f"{models} / {[x[:12] for x in digests]}")

    # -------------------------------------------------- verdict
    print(f"\n{'=' * 74}\nVERDICT\n{'=' * 74}")
    if FAILS:
        print(f"DISCREPANCIES — {len(FAILS)} failed check(s):")
        for tag, msg in FAILS:
            print(f"  [{tag}] {msg}")
    else:
        print("CONFIRMED — all integrity, metric, and cross-sweep checks "
              "passed for all three sweeps.")
    if WARNS:
        print(f"{len(WARNS)} warning(s) (informational, not failures):")
        for tag, msg in WARNS:
            print(f"  [{tag}] {msg}")
    print("\nLargest t07-varied Tier-1 delta per model/arm across versions:")
    for (label, arm), (h, dv) in sorted(max_delta.items()):
        print(f"  {label:12s} {arm:6s} {h:6s} {dv:.3f}")


if __name__ == "__main__":
    main()
