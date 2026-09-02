"""Independent audit of results-deepseek-r1-14b-thinking (2,300 runs).

Pure-Python, read-only over JSONL + manifest + label files. No LLM calls,
no GPU, no imports from experiments.analysis.metrics (metrics are
re-implemented here from their pre-registered definitions so the recompute
is genuinely independent).

Run from backend/:  ./.venv/bin/python experiments/analysis/eval_deepseek_audit.py
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

RES = Path("experiments/results-deepseek-r1-14b-thinking")
LABELS_PATH = Path(
    "/home/eliem/Projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json"
)
PERT_PATH = Path("experiments/perturbation_cases.json")
OUTCOMES = ("escalate", "dismiss", "investigate", "malformed")

out: dict = {}


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------
def load_jsonl(p: Path) -> list[dict]:
    rows = []
    with p.open() as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                rows.append({"__parse_error__": str(e), "__line__": i})
    return rows


manifest = json.loads((RES / "manifest.json").read_text())
single = load_jsonl(RES / "journal-single.jsonl")
mas = load_jsonl(RES / "journal-mas.jsonl")
runs = single + mas

labels_doc = json.loads(LABELS_PATH.read_text())
pert_doc = json.loads(PERT_PATH.read_text())
labels = {a["alert_id"]: a["ground_truth"] for a in labels_doc["alerts"]}
labels.update({a["alert_id"]: a["ground_truth"] for a in pert_doc["alerts"]})

out["load"] = {
    "n_single": len(single),
    "n_mas": len(mas),
    "n_total": len(runs),
    "parse_errors": sum(1 for r in runs if "__parse_error__" in r),
    "manifest_planned": len(manifest["runs"]),
    "manifest_totals": manifest["totals"],
    "labels_primary": len(labels_doc["alerts"]),
    "labels_pert": len(pert_doc["alerts"]),
    "label_dist_primary": dict(Counter(a["ground_truth"] for a in labels_doc["alerts"])),
    "label_dist_meta_claim": labels_doc["metadata"].get("ground_truth_distribution"),
    "label_dist_pert": dict(Counter(a["ground_truth"] for a in pert_doc["alerts"])),
}

# --------------------------------------------------------------------------
# 1. DATA INTEGRITY
# --------------------------------------------------------------------------
key = lambda r: (r["arm"], r["case_id"], r["condition"], r["repeat_idx"])
plan = {key(r): r for r in manifest["runs"]}
seen = Counter(key(r) for r in runs)

dupes = {str(k): v for k, v in seen.items() if v > 1}
missing = sorted(str(k) for k in plan if k not in seen)
extra = sorted(str(k) for k in seen if k not in plan)

# per-run plan match: seed / temperature / block / run_id
mismatch = defaultdict(list)
for r in runs:
    p = plan.get(key(r))
    if p is None:
        continue
    for f in ("seed", "temperature", "block", "run_id"):
        if r.get(f) != p.get(f):
            mismatch[f].append({"key": str(key(r)), "journal": r.get(f), "plan": p.get(f)})

integ = {
    "duplicate_keys": dupes,
    "n_duplicates": len(dupes),
    "missing_keys": missing[:20],
    "n_missing": len(missing),
    "unplanned_keys": extra[:20],
    "n_unplanned": len(extra),
    "plan_field_mismatches": {k: {"n": len(v), "examples": v[:5]} for k, v in mismatch.items()},
    "model_digest_values": dict(Counter(r.get("model_digest") for r in runs)),
    "ollama_version_values": dict(Counter(r.get("ollama_version") for r in runs)),
    "model_values": dict(Counter(r.get("model") for r in runs)),
    "think_values": dict(Counter(str(r.get("think")) for r in runs)),
    "num_predict_values": dict(Counter(r.get("num_predict") for r in runs)),
    "cache_policy_values": dict(Counter(r.get("cache_policy") for r in runs)),
    "manifest_digest": manifest["model_digest"],
    "manifest_ollama": manifest["ollama_version"],
    "decision_domain": dict(Counter(str(r.get("decision")) for r in runs)),
    "errors_nonnull": sum(1 for r in runs if r.get("error")),
    "error_values": dict(Counter(str(r.get("error")) for r in runs if r.get("error")).most_common(10)),
    "empty_raw_output": sum(1 for r in runs if not (r.get("raw_output") or "").strip()),
    "null_fields": {
        f: sum(1 for r in runs if r.get(f) is None)
        for f in ("decision", "raw_output", "prompt_tokens", "completion_tokens", "wall_clock_s", "seed", "temperature")
    },
}

# decision domain by arm
integ["decision_by_arm"] = {
    a: dict(Counter(r["decision"] for r in runs if r["arm"] == a)) for a in ("single", "mas")
}

# seed policy sanity: t0-fixed / pert-t0 must be seed 42 everywhere; varied seeds unique?
seed_check = {}
for cond in ("t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10"):
    sub = [r for r in runs if r["condition"] == cond]
    seeds = [r["seed"] for r in sub]
    temps = set(r["temperature"] for r in sub)
    seed_check[cond] = {
        "n": len(sub),
        "distinct_seeds": len(set(seeds)),
        "all_42": all(s == 42 for s in seeds),
        "temperatures": sorted(temps),
        "seed_reuse_across_arms": len(seeds) - len(set((r["arm"], r["seed"]) for r in sub)),
    }
# do single and mas share the same seed sequence per (case, condition, repeat)?
paired_seed_same = 0
paired_seed_diff = 0
for k, p in plan.items():
    if k[0] != "single":
        continue
    q = plan.get(("mas",) + k[1:])
    if q is None:
        continue
    if p["seed"] == q["seed"]:
        paired_seed_same += 1
    else:
        paired_seed_diff += 1
seed_check["single_vs_mas_same_seed_pairs"] = {"same": paired_seed_same, "diff": paired_seed_diff}
integ["seed_check"] = seed_check

# timestamps
def ts(r):
    return datetime.strptime(r["started_at"], "%Y-%m-%dT%H:%M:%SZ")


gaps = {}
for name, rows in (("single", single), ("mas", mas), ("all", runs)):
    srt = sorted(rows, key=ts)
    g = []
    for a, b in zip(srt, srt[1:]):
        d = (ts(b) - ts(a)).total_seconds()
        if d > 600:
            g.append({"gap_s": d, "after": a["run_id"], "at": a["started_at"], "before": b["run_id"], "next_at": b["started_at"]})
    gaps[name] = {
        "first": srt[0]["started_at"],
        "last": srt[-1]["started_at"],
        "span_h": round((ts(srt[-1]) - ts(srt[0])).total_seconds() / 3600, 2),
        "n_gaps_gt_10min": len(g),
        "gaps": g[:15],
        "total_gap_h": round(sum(x["gap_s"] for x in g) / 3600, 2),
    }
# arm overlap in wall-clock: do single and mas run at the same time?
s_times = sorted(ts(r) for r in single)
m_times = sorted(ts(r) for r in mas)
overlap_start = max(s_times[0], m_times[0])
overlap_end = min(s_times[-1], m_times[-1])
gaps["arm_overlap"] = {
    "single_window": [s_times[0].isoformat(), s_times[-1].isoformat()],
    "mas_window": [m_times[0].isoformat(), m_times[-1].isoformat()],
    "overlap_h": round(max(0.0, (overlap_end - overlap_start).total_seconds()) / 3600, 2),
    "single_runs_inside_mas_window": sum(1 for t in s_times if m_times[0] <= t <= m_times[-1]),
    "mas_runs_inside_single_window": sum(1 for t in m_times if s_times[0] <= t <= s_times[-1]),
}
# identical started_at collisions between arms (same second)
sset = Counter(r["started_at"] for r in single)
mset = Counter(r["started_at"] for r in mas)
gaps["same_second_both_arms"] = sum(min(sset[k], mset[k]) for k in sset if k in mset)
integ["timestamps"] = gaps

# host load / env
integ["env_load_high"] = sum(1 for r in runs if (r.get("env") or {}).get("host_load_high"))
loads = [(r.get("env") or {}).get("host_load_1m") for r in runs]
loads = [x for x in loads if isinstance(x, (int, float))]
integ["host_load_1m"] = {
    "min": min(loads), "max": max(loads),
    "mean": round(statistics.mean(loads), 2), "median": round(statistics.median(loads), 2),
} if loads else None
gpus = Counter((r.get("env") or {}).get("gpu_name") for r in runs)
integ["gpu_names"] = dict(gpus)
out["integrity"] = integ

# --------------------------------------------------------------------------
# 2. THINKING-TRACK CONTAMINATION
# --------------------------------------------------------------------------
def collect_text_fields(r):
    """Every free-text surface stored for a run."""
    yield "raw_output", r.get("raw_output") or ""
    no = r.get("node_outputs")
    if isinstance(no, dict):
        for k, v in no.items():
            if isinstance(v, str):
                yield f"node_outputs.{k}", v
            else:
                yield f"node_outputs.{k}", json.dumps(v)


OPEN_RE = re.compile(r"<think(?:ing)?\b[^>]*>", re.I)
CLOSE_RE = re.compile(r"</think(?:ing)?\s*>", re.I)
ANALYSIS_RE = re.compile(r"<\|(?:channel|start|end|message)\|>|<\|assistant\|>", re.I)

think = {
    "raw_output_open_tags": 0,
    "raw_output_close_tags": 0,
    "raw_output_runs_with_open": 0,
    "raw_output_runs_with_close": 0,
    "raw_output_orphan_close_runs": 0,   # close present, no open
    "raw_output_orphan_open_runs": 0,    # open present, no close
    "raw_output_balanced_pairs_runs": 0,
    "node_outputs_open_tags": 0,
    "node_outputs_close_tags": 0,
    "node_outputs_runs_with_any_tag": 0,
    "special_channel_marker_runs": 0,
    "examples": [],
}
for r in runs:
    ro = r.get("raw_output") or ""
    o = len(OPEN_RE.findall(ro))
    c = len(CLOSE_RE.findall(ro))
    think["raw_output_open_tags"] += o
    think["raw_output_close_tags"] += c
    if o:
        think["raw_output_runs_with_open"] += 1
    if c:
        think["raw_output_runs_with_close"] += 1
    if c and not o:
        think["raw_output_orphan_close_runs"] += 1
        if len(think["examples"]) < 5:
            think["examples"].append({"run_id": r["run_id"], "kind": "orphan_close", "head": ro[:200]})
    if o and not c:
        think["raw_output_orphan_open_runs"] += 1
        if len(think["examples"]) < 5:
            think["examples"].append({"run_id": r["run_id"], "kind": "orphan_open", "head": ro[:200]})
    if o and c:
        think["raw_output_balanced_pairs_runs"] += 1
    if ANALYSIS_RE.search(ro):
        think["special_channel_marker_runs"] += 1
    no_any = False
    for fname, txt in collect_text_fields(r):
        if fname == "raw_output":
            continue
        oo, cc = len(OPEN_RE.findall(txt)), len(CLOSE_RE.findall(txt))
        think["node_outputs_open_tags"] += oo
        think["node_outputs_close_tags"] += cc
        if oo or cc:
            no_any = True
    if no_any:
        think["node_outputs_runs_with_any_tag"] += 1

# Is the reasoning channel actually stored anywhere? (journal key inventory)
allkeys = Counter()
for r in runs:
    allkeys.update(r.keys())
think["journal_keys"] = dict(allkeys)
think["has_thinking_field"] = any(
    k.lower() in {"thinking", "think_text", "reasoning", "reasoning_content"} for k in allkeys
)

# token accounting: completion_tokens vs whitespace tokens actually in raw_output
ratios = []
for r in runs:
    vis = len((r.get("raw_output") or "").split())
    ct = r.get("completion_tokens") or 0
    if vis:
        ratios.append(ct / vis)
think["completion_vs_visible_token_ratio"] = {
    "median": round(statistics.median(ratios), 2),
    "mean": round(statistics.mean(ratios), 2),
    "p10": round(sorted(ratios)[len(ratios) // 10], 2),
    "p90": round(sorted(ratios)[int(len(ratios) * 0.9)], 2),
}
for arm in ("single", "mas"):
    rr = []
    for r in runs:
        if r["arm"] != arm:
            continue
        vis = len((r.get("raw_output") or "").split())
        if vis:
            rr.append((r.get("completion_tokens") or 0) / vis)
    think[f"completion_vs_visible_ratio_median_{arm}"] = round(statistics.median(rr), 2)

# num_predict truncation pressure
think["completion_tokens_at_or_above_num_predict"] = sum(
    1 for r in runs if (r.get("completion_tokens") or 0) >= (r.get("num_predict") or 10**9)
)
think["completion_tokens_ge_2040"] = sum(1 for r in runs if (r.get("completion_tokens") or 0) >= 2040)
think["max_completion_tokens"] = max((r.get("completion_tokens") or 0) for r in runs)
out["thinking"] = think

# --------------------------------------------------------------------------
# 3. METRICS (re-implemented)
# --------------------------------------------------------------------------
def pass_hat_k(n, c, k):
    if k > n:
        return None
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def dar(ds):
    prs = list(combinations(ds, 2))
    return sum(a == b for a, b in prs) / len(prs)


def kripp(units):
    co = Counter()
    for u in units:
        m = len(u)
        if m < 2:
            continue
        for i, a in enumerate(u):
            for j, b in enumerate(u):
                if i != j:
                    co[(a, b)] += 1.0 / (m - 1)
    nc = Counter()
    for (a, _b), w in co.items():
        nc[a] += w
    n = sum(nc.values())
    if n <= 1:
        return None
    do = sum(w for (a, b), w in co.items() if a != b)
    de = sum(nc[a] * nc[b] for a in nc for b in nc if a != b) / (n - 1)
    return 1.0 if de == 0 else 1.0 - do / de


def majority(ds):
    cnt = Counter(ds)
    top = max(cnt.values())
    winners = [o for o in OUTCOMES if cnt.get(o, 0) == top]
    return winners[0], len(winners) > 1


def nentropy(ds):
    cnt = Counter(ds)
    tot = sum(cnt.values())
    h = -sum((c / tot) * math.log2(c / tot) for c in cnt.values() if c)
    return h / math.log2(len(OUTCOMES))


def lcs_len(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def pw(items, score):
    prs = list(combinations(items, 2))
    return sum(score(a, b) for a, b in prs) / len(prs)


def tool_names(tc):
    names = []
    for t in tc or []:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict):
            names.append(t.get("name") or t.get("tool") or t.get("function") or json.dumps(t, sort_keys=True))
        else:
            names.append(str(t))
    return names


groups: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
for r in runs:
    groups[(r["arm"], r["condition"])][r["case_id"]].append(r)
for g in groups.values():
    for cid in g:
        g[cid].sort(key=lambda r: r["repeat_idx"])


def summarise(arm, cond):
    g = groups[(arm, cond)]
    cases = sorted(g)
    dec = {c: [r["decision"] for r in g[c]] for c in cases}
    n = min(len(v) for v in dec.values())
    s = {"arm": arm, "condition": cond, "cases": len(cases), "repeats": n}
    ks = sorted({k for k in (1, 5, 15) if k <= n} | {n})
    for k in ks:
        vals = [pass_hat_k(len(dec[c]), sum(d == labels[c] for d in dec[c]), k) for c in cases]
        s[f"pass^{k}"] = statistics.mean(vals)
    s["DAR"] = statistics.mean([dar(dec[c]) for c in cases])
    s["alpha"] = kripp([dec[c] for c in cases])
    s["flip_rate"] = statistics.mean([float(len(set(dec[c])) > 1) for c in cases])
    maj = {c: majority(dec[c]) for c in cases}
    s["majority_vote_accuracy"] = statistics.mean([float(maj[c][0] == labels[c]) for c in cases])
    s["majority_ties"] = sum(1 for c in cases if maj[c][1])
    ent = {c: nentropy(dec[c]) for c in cases}
    s["mean_entropy"] = statistics.mean(ent.values())
    s["worst_entropy_cases"] = sorted(ent, key=lambda c: (-ent[c], c))[:3]
    traj = {c: [tool_names(r.get("tool_calls")) for r in g[c]] for c in cases}
    s["TAR"] = statistics.mean([pw(traj[c], lambda a, b: float(a == b)) for c in cases])
    s["jaccard"] = statistics.mean(
        [pw(traj[c], lambda a, b: 1.0 if not set(a) and not set(b) else len(set(a) & set(b)) / len(set(a) | set(b))) for c in cases]
    )
    s["nLCS"] = statistics.mean(
        [pw(traj[c], lambda a, b: 1.0 if not a and not b else (0.0 if not a or not b else lcs_len(a, b) / max(len(a), len(b)))) for c in cases]
    )
    s["mean_tool_calls_per_run"] = statistics.mean([len(t) for c in cases for t in traj[c]])
    s["runs_with_any_tool_call"] = sum(1 for c in cases for t in traj[c] if t)
    tok = [(r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for c in cases for r in g[c]]
    s["tokens_per_run"] = statistics.mean(tok)
    s["prompt_tokens_per_run"] = statistics.mean([r.get("prompt_tokens") or 0 for c in cases for r in g[c]])
    s["completion_tokens_per_run"] = statistics.mean([r.get("completion_tokens") or 0 for c in cases for r in g[c]])
    s["mean_wall_clock_s"] = statistics.mean([r.get("wall_clock_s") or 0.0 for c in cases for r in g[c]])
    s["total_wall_clock_h"] = sum(r.get("wall_clock_s") or 0.0 for c in cases for r in g[c]) / 3600
    s["malformed_rate"] = statistics.mean([sum(d == "malformed" for d in dec[c]) / len(dec[c]) for c in cases])
    for k in ks:
        p = s[f"pass^{k}"]
        s[f"tokens_per_pass^{k}"] = (s["tokens_per_run"] / p) if p else None
    s["decision_dist"] = dict(Counter(d for c in cases for d in dec[c]))
    s["per_case_decisions"] = {c: dict(Counter(dec[c])) for c in cases}
    return s


summaries = {}
for arm in ("single", "mas"):
    for cond in ("t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10"):
        summaries[f"{arm}|{cond}"] = summarise(arm, cond)
out["summaries"] = summaries

# --------------------------------------------------------------------------
# 3b. ARM-DIFFERENCE STATS (bootstrap CI over cases + paired permutation)
# --------------------------------------------------------------------------
rng = random.Random(20260814)


def per_case_stat(arm, cond, fn):
    g = groups[(arm, cond)]
    return {c: fn([r["decision"] for r in g[c]], c) for c in sorted(g)}


STATS = {
    "pass^1": lambda ds, c: sum(d == labels[c] for d in ds) / len(ds),
    "DAR": lambda ds, c: dar(ds),
    "flip": lambda ds, c: float(len(set(ds)) > 1),
    "majority_acc": lambda ds, c: float(majority(ds)[0] == labels[c]),
    "entropy": lambda ds, c: nentropy(ds),
}

arm_diff = {}
for cond in ("t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10"):
    for name, fn in STATS.items():
        a = per_case_stat("mas", cond, fn)
        b = per_case_stat("single", cond, fn)
        cases = sorted(set(a) & set(b))
        d = [a[c] - b[c] for c in cases]
        obs = statistics.mean(d)
        # paired bootstrap over cases
        boots = []
        for _ in range(10000):
            samp = [d[rng.randrange(len(d))] for _ in range(len(d))]
            boots.append(sum(samp) / len(samp))
        boots.sort()
        lo, hi = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]
        # exact-ish paired permutation (sign flip)
        cnt = 0
        N = 10000
        for _ in range(N):
            s = sum(x if rng.random() < 0.5 else -x for x in d) / len(d)
            if abs(s) >= abs(obs) - 1e-12:
                cnt += 1
        p = (cnt + 1) / (N + 1)
        arm_diff[f"{cond}|{name}"] = {
            "mas_mean": statistics.mean(a[c] for c in cases),
            "single_mean": statistics.mean(b[c] for c in cases),
            "diff_mas_minus_single": obs,
            "ci95": [lo, hi],
            "perm_p": p,
            "n_cases": len(cases),
            "n_nonzero_pairs": sum(1 for x in d if x != 0),
        }
out["arm_diff"] = arm_diff

# --------------------------------------------------------------------------
# 4. T=0 FIXED-SEED DETERMINISM
# --------------------------------------------------------------------------
det = {}
for cond in ("t0-fixed", "pert-t0"):
    for arm in ("single", "mas"):
        g = groups[(arm, cond)]
        byte_id, dec_id, node_id = [], [], []
        flip_groups = []
        for c in sorted(g):
            rs = g[c]
            raws = [r.get("raw_output") or "" for r in rs]
            decs = [r["decision"] for r in rs]
            nodes = [json.dumps(r.get("node_outputs"), sort_keys=True) for r in rs]
            b = len(set(raws)) == 1
            dd = len(set(decs)) == 1
            byte_id.append(b)
            dec_id.append(dd)
            node_id.append(len(set(nodes)) == 1)
            if not dd:
                flip_groups.append({"case": c, "decisions": decs, "label": labels[c]})
        det[f"{arm}|{cond}"] = {
            "cases": len(g),
            "byte_identical_cases": sum(byte_id),
            "byte_identical_rate": sum(byte_id) / len(byte_id),
            "decision_identical_cases": sum(dec_id),
            "decision_identical_rate": sum(dec_id) / len(dec_id),
            "node_outputs_identical_cases": sum(node_id),
            "decision_flip_groups": flip_groups,
            "n_decision_flip_cases": len(flip_groups),
        }
        # distinct-output multiplicity distribution
        det[f"{arm}|{cond}"]["distinct_raw_outputs_hist"] = dict(
            Counter(len(set(r.get("raw_output") or "" for r in g[c])) for c in g)
        )
out["determinism"] = det

# --------------------------------------------------------------------------
# 5. DEGENERACY
# --------------------------------------------------------------------------
deg = {}
prim_labels = Counter(labels_doc["alerts"][i]["ground_truth"] for i in range(50))
for kk, s in summaries.items():
    dist = s["decision_dist"]
    tot = sum(dist.values())
    deg[kk] = {
        "decision_share": {d: round(v / tot, 4) for d, v in sorted(dist.items(), key=lambda x: -x[1])},
        "modal": max(dist, key=dist.get),
        "modal_share": max(dist.values()) / tot,
        "n_distinct_decisions": len(dist),
    }
deg["label_share_primary"] = {k: round(v / 50, 4) for k, v in prim_labels.items()}
deg["label_share_pert"] = {
    k: round(v / 10, 4) for k, v in Counter(a["ground_truth"] for a in pert_doc["alerts"]).items()
}
# per-case: does the arm ever emit anything other than its global mode?
for arm in ("single", "mas"):
    for cond in ("t0-fixed", "t07-varied"):
        s = summaries[f"{arm}|{cond}"]
        pc = s["per_case_decisions"]
        deg[f"{arm}|{cond}|cases_unanimous_on_global_mode"] = sum(
            1 for c, d in pc.items() if len(d) == 1 and next(iter(d)) == deg[f"{arm}|{cond}"]["modal"]
        )
        # confusion vs label
        conf = Counter()
        for c, d in pc.items():
            for dec, n in d.items():
                conf[(labels[c], dec)] += n
        deg[f"{arm}|{cond}|confusion"] = {f"{a}->{b}": n for (a, b), n in sorted(conf.items())}
        # per-label recall
        rec = {}
        for lab in ("escalate", "dismiss", "investigate"):
            tot = sum(n for (a, b), n in conf.items() if a == lab)
            hit = conf.get((lab, lab), 0)
            rec[lab] = round(hit / tot, 4) if tot else None
        deg[f"{arm}|{cond}|per_label_agreement"] = rec
# perturbation responsiveness: does the decision move with the intended flip?
pert_meta = {a["alert_id"]: a for a in pert_doc["alerts"]}
for arm in ("single", "mas"):
    for cond in ("pert-t0", "pert-t05", "pert-t10"):
        g = groups[(arm, cond)]
        rows = []
        for c in sorted(g):
            decs = [r["decision"] for r in g[c]]
            rows.append({
                "case": c,
                "flip": pert_meta[c]["flip"],
                "target": labels[c],
                "dist": dict(Counter(decs)),
                "hit_rate": sum(d == labels[c] for d in decs) / len(decs),
            })
        deg[f"{arm}|{cond}|perturbation_detail"] = rows
out["degeneracy"] = deg

# --------------------------------------------------------------------------
# 6. misc: node_outputs / agent_messages / tool usage
# --------------------------------------------------------------------------
misc = {}
misc["agent_messages"] = {
    a: dict(Counter(r.get("agent_messages") for r in runs if r["arm"] == a)) for a in ("single", "mas")
}
misc["node_outputs_present"] = {
    a: sum(1 for r in runs if r["arm"] == a and r.get("node_outputs")) for a in ("single", "mas")
}
node_keys = Counter()
for r in mas:
    if isinstance(r.get("node_outputs"), dict):
        node_keys.update(r["node_outputs"].keys())
misc["mas_node_keys"] = dict(node_keys)
misc["total_tool_calls"] = sum(len(r.get("tool_calls") or []) for r in runs)
misc["runs_with_tool_calls"] = sum(1 for r in runs if r.get("tool_calls"))
misc["empty_node_output_strings"] = sum(
    1 for r in mas if isinstance(r.get("node_outputs"), dict)
    for v in r["node_outputs"].values() if isinstance(v, str) and not v.strip()
)
# raw_output leading-whitespace signature (thinking strip artefact)
misc["raw_output_starts_with_double_newline"] = sum(
    1 for r in runs if (r.get("raw_output") or "").startswith("\n\n")
)
misc["wall_clock_by_arm"] = {
    a: {
        "mean": round(statistics.mean([r["wall_clock_s"] for r in runs if r["arm"] == a]), 2),
        "median": round(statistics.median([r["wall_clock_s"] for r in runs if r["arm"] == a]), 2),
        "max": max(r["wall_clock_s"] for r in runs if r["arm"] == a),
        "total_h": round(sum(r["wall_clock_s"] for r in runs if r["arm"] == a) / 3600, 2),
    }
    for a in ("single", "mas")
}
# sum of wall clock vs span -> concurrency evidence
span_h = (max(ts(r) for r in runs) - min(ts(r) for r in runs)).total_seconds() / 3600
misc["span_h_all"] = round(span_h, 2)
misc["sum_wall_clock_h"] = round(sum(r["wall_clock_s"] for r in runs) / 3600, 2)
out["misc"] = misc

Path("/tmp/claude-1000/-home-el-projects-msc-research/84658f1b-978b-4126-8079-caf661a8abd1/scratchpad").mkdir(parents=True, exist_ok=True)
Path(
    "/tmp/claude-1000/-home-el-projects-msc-research/84658f1b-978b-4126-8079-caf661a8abd1/scratchpad/audit.json"
).write_text(json.dumps(out, indent=1, default=str))
print("written")
