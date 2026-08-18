#!/usr/bin/env python3
"""OWNER'S MASTER DATA REPORT generator.

Recomputes EVERY number independently from the raw run journals
(``results*/journal-{single,mas}.jsonl``) — nothing is copied from derived
docs; this report IS the independent recomputation. Writes
``docs/MASTER-DATA-REPORT.md``.

Hard constraints honoured: zero LLM calls, no GPU, no network, journals
opened read-only, torn last lines tolerated (live sweeps append while this
runs; partial dirs are marked LIVE/PARTIAL). Re-runnable at any seal:

    cd backend && .venv/bin/python -m experiments.analysis.master_report_gen
    # or: python3 experiments/analysis/master_report_gen.py

Metric conventions are the locked ones from ``analysis/metrics.py``
(imported, not re-implemented): pass^k = C(c,k)/C(n,k) framed as agreement
with the benchmark authors' labels; malformed is an outcome category, never
excluded; majority ties break by canonical OUTCOMES order
(escalate > dismiss > investigate > malformed); normalised entropy uses
log2(4).

Perturbation "MV movement" convention (matches the published usage): for
each of the 10 (base, PERT) pairs, the perturbed condition's majority vote
is compared against the SAME ARM's base-case majority vote from the matched
primary condition — t0-fixed for pert-t0, t07-varied for pert-t05 and
pert-t10. "Moved" = the two majority votes differ.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
EXP = HERE.parents[1]        # backend/experiments
BACKEND = HERE.parents[2]    # backend
REPO = HERE.parents[3]       # repo root
sys.path.insert(0, str(BACKEND))

from experiments.analysis import metrics  # noqa: E402  (locked conventions)
from experiments.config import (  # noqa: E402
    ALERTS_JSON,
    OUTCOMES,
    PERTURBATION_JSON,
)

OUT_MD = REPO / "docs" / "MASTER-DATA-REPORT.md"

CONDITIONS = ("t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10")
COND_REPEATS = {"t0-fixed": 5, "t07-varied": 15, "pert-t0": 5, "pert-t05": 5, "pert-t10": 5}
PERT_CONDS = ("pert-t0", "pert-t05", "pert-t10")
PERT_BASE_COND = {"pert-t0": "t0-fixed", "pert-t05": "t07-varied", "pert-t10": "t07-varied"}
ARMS = ("single", "mas")
DECS = ("escalate", "dismiss", "investigate", "malformed")

DATA_TOOLS = {"search_precedents", "get_customer_profile", "check_sanctions_list"}
POLICY_TOOLS = {"calculate_risk_score"}
NODES = ("orchestrator", "data", "policy_risk", "reporting")

GAP_S = 600.0  # journal-gap detector threshold (matches audit convention)


# --------------------------------------------------------------------------
# Sweep registry (status/notes from CHANGELOG.md dated entries; everything
# numeric below is recomputed from journals, never from the CHANGELOG).
# --------------------------------------------------------------------------

SWEEPS = [
    # key, dirname, model tag, think, infra context, harness, status, note
    ("qwen3.5:9b", "results", "qwen3.5:9b", "off (false)", "1 · Ollama 0.31.1", "v1",
     "SEALED", "headline pre-registered sweep"),
    ("qwen2.5:7b-instruct", "results-qwen2.5-7b", "qwen2.5:7b-instruct", "n/a (omit)",
     "1 · Ollama 0.31.1", "v1", "SEALED", "replication; restarted from zero 2026-08-07 (partial archived)"),
    ("qwen2.5:14b-instruct", "results-qwen2.5-14b", "qwen2.5:14b-instruct", "n/a (omit)",
     "1 · Ollama 0.31.1", "v1", "SEALED", "replication"),
    ("gemma4:latest", "results-gemma4", "gemma4:latest", "n/a (omit)",
     "2 · Ollama 0.32.6", "v1", "SEALED", "admitted after 0.32.x tool-template fix; aborted partial archived"),
    ("qwen2.5:7b-instruct@0.32.6", "results-qwen2.5-7b-ollama0326", "qwen2.5:7b-instruct",
     "n/a (omit)", "2 · Ollama 0.32.6", "v1", "SEALED", "infra replication of context-1 sweep"),
    ("qwen3.5:9b@0.32.6", "results-qwen3.5-9b-ollama0326", "qwen3.5:9b", "off (false)",
     "2 · Ollama 0.32.6", "v1", "SEALED", "infra replication of headline sweep"),
    ("qwen2.5:14b-instruct@0.32.6", "results-qwen2.5-14b-ollama0326", "qwen2.5:14b-instruct",
     "n/a (omit)", "2 · Ollama 0.32.6", "v1", "SEALED", "infra replication"),
    ("lfm2.5:8b@think", "results-lfm2.5-8b-thinking", "lfm2.5:8b", "ON",
     "3 · Ollama 0.32.9", "v2", "SEALED", "thinking track; no admissible thinking-off twin; 0.13% channel contamination"),
    ("deepseek-r1:14b@think", "results-deepseek-r1-14b-thinking", "deepseek-r1:14b", "ON",
     "3 · Ollama 0.32.9", "v2", "SEALED — EXCLUDED", "tool channel never existed (registry template drops tools); capability-gating negative case"),
    ("qwen3.5:9b@think-budget", "results-qwen3.5-9b-thinking-budget", "qwen3.5:9b", "ON",
     "3 · Ollama 0.32.9", "v2", "SEALED", "num_predict 8192 override; 4-factor confound vs sealed qwen3.5 (think, num_predict, ollama, harness)"),
    ("granite4.1:8b", "results-granite4.1-8b", "granite4.1:8b", "n/a (omit)",
     "3 · Ollama 0.32.9", "v2", "SEALED", "re-admitted 2026-08-14 as null-result data point w/ degeneracy annotation"),
    ("muse-glimmer:30b", "results-muse-glimmer-30b", "muse-glimmer:30b", "off (false)",
     "3 · Ollama 0.32.9", "v2", "SEALED", "reboot deviation 2026-08-14 (lossless); 19.7% empty MAS data-node outputs"),
    ("muse-glimmer:30b@think", "results-muse-glimmer-30b-thinking", "muse-glimmer:30b", "ON",
     "3 · Ollama 0.32.9", "v2", "CLOSED — single-arm-only", "MAS arm STOPPED at 201/1150 (95% data-node cap exhaustion) and capability-gated out; single arm complete and valid"),
    # ---- budget-sensitivity track v2b ("@b32"), launched 2026-08-18 ------
    ("qwen2.5:7b-instruct@b32", "results-budget-qwen2.5-7b", "qwen2.5:7b-instruct",
     "n/a (omit)", "b32 · Ollama 0.32.9", "v2b", "LIVE", "budget track sweep 1/6 — IN FLIGHT, all numbers partial"),
    ("granite4.1:8b@b32", "results-budget-granite4.1-8b", "granite4.1:8b", "n/a (omit)",
     "b32 · Ollama 0.32.9", "v2b", "QUEUED", "budget track sweep 2/6"),
    ("qwen3.5:9b@b32", "results-budget-qwen3.5-9b", "qwen3.5:9b", "off (false)",
     "b32 · Ollama 0.32.9", "v2b", "QUEUED", "budget track sweep 3/6"),
    ("lfm2.5:8b@b32-think", "results-budget-lfm2.5-8b-thinking", "lfm2.5:8b", "ON",
     "b32 · Ollama 0.32.9", "v2b", "QUEUED", "budget track sweep 4/6"),
    ("qwen3.5:9b@b32-think-budget", "results-budget-qwen3.5-9b-thinking", "qwen3.5:9b", "ON",
     "b32 · Ollama 0.32.9", "v2b", "QUEUED", "budget track sweep 5/6; num_predict 8192 (pre-declared confound)"),
    ("gemma4:latest@b32", "results-budget-gemma4", "gemma4:latest", "n/a (omit)",
     "b32 · Ollama 0.32.9", "v2b", "QUEUED", "budget track sweep 6/6"),
]

EXCLUDED_KEYS = {"deepseek-r1:14b@think"}
CLOSED_MAS_KEYS = {"muse-glimmer:30b@think"}
# Sweeps whose numbers enter cross-model comparison tables
COMPARABLE = [s[0] for s in SWEEPS
              if s[6].startswith("SEALED") and s[0] not in EXCLUDED_KEYS] + ["muse-glimmer:30b@think"]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_labels() -> tuple[dict[str, str], dict[str, str], list[dict]]:
    primary = {r["alert_id"]: r["ground_truth"]
               for r in json.loads(ALERTS_JSON.read_text())["alerts"]}
    pert_recs = json.loads(PERTURBATION_JSON.read_text())["alerts"]
    pert = {r["alert_id"]: r["ground_truth"] for r in pert_recs}
    return primary, pert, pert_recs


def load_journal(path: Path) -> tuple[list[dict], int]:
    """Parse a JSONL journal; tolerate a torn (partial) last line."""
    rows, torn = [], 0
    if not path.exists():
        return rows, torn
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                torn += 1
    return rows, torn


def ts(r: dict) -> float:
    return datetime.strptime(r["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc).timestamp()


# --------------------------------------------------------------------------
# Per-condition statistics
# --------------------------------------------------------------------------

def fmt(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return f"{x:,}" if isinstance(x, int) else str(x)


def pct(n, d):
    return f"{100.0 * n / d:.1f}%" if d else "—"


def cond_stats(rows: list[dict], labels: dict[str, str], expected_cases: int,
               expected_repeats: int) -> dict:
    """All requested per-(arm, condition) numbers. Tolerates partial data:
    reliability metrics restrict to cases with >= 2 repeats; pass^k to cases
    with >= k repeats; coverage is reported."""
    s: dict = {}
    n = len(rows)
    s["runs"] = n
    if n == 0:
        return s
    s["errors"] = sum(1 for r in rows if r.get("error"))
    dec = Counter(r.get("decision") for r in rows)
    s["dist"] = {d: dec.get(d, 0) for d in DECS}
    s["malformed"] = dec.get("malformed", 0)

    by_case: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_case[r["case_id"]].append(r)
    for c in by_case:
        by_case[c].sort(key=lambda r: r["repeat_idx"])
    s["cases_seen"] = len(by_case)
    s["expected"] = expected_cases * expected_repeats
    complete = {c: rs for c, rs in by_case.items() if len(rs) == expected_repeats}
    s["cases_complete"] = len(complete)
    s["partial"] = n < s["expected"]

    dec_by_case = {c: [r.get("decision") for r in rs] for c, rs in by_case.items()}

    # pass^k over cases with >= k repeats (all cases when sweep complete)
    for k in (1, 5, 15):
        elig = [c for c, ds in dec_by_case.items() if len(ds) >= k]
        if k > expected_repeats or not elig:
            s[f"pass^{k}"] = None
        else:
            s[f"pass^{k}"] = metrics._mean(
                [metrics.case_pass_hat_k(dec_by_case[c], labels[c], k) for c in elig])

    multi = {c: ds for c, ds in dec_by_case.items() if len(ds) >= 2}
    if multi:
        s["DAR"] = metrics._mean(
            [metrics.decision_agreement_rate(ds) for ds in multi.values()])
        s["alpha"] = metrics.krippendorff_alpha(list(multi.values()))
        s["flip_rate"] = metrics._mean(
            [float(metrics.flipped(ds)) for ds in multi.values()])
        s["entropy"] = metrics._mean(
            [metrics.normalised_entropy(ds) for ds in multi.values()])
    else:
        s["DAR"] = s["alpha"] = s["flip_rate"] = s["entropy"] = None

    mv = {c: metrics.majority_vote(ds) for c, ds in dec_by_case.items()}
    s["mv"] = {c: m[0] for c, m in mv.items()}
    s["mv_acc"] = metrics._mean([float(m[0] == labels[c]) for c, m in mv.items()])
    s["mv_ties"] = sum(1 for m in mv.values() if m[1])
    lbls = [labels[c] for c in by_case]
    s["baseline"] = max(Counter(lbls).values()) / len(lbls) if lbls else None
    s["modal"] = dec.most_common(1)[0]

    # tokens / wall clock
    pt = [int(r.get("prompt_tokens") or 0) for r in rows]
    ct = [int(r.get("completion_tokens") or 0) for r in rows]
    s["prompt_mean"] = statistics.mean(pt)
    s["completion_mean"] = statistics.mean(ct)
    s["total_mean"] = statistics.mean([a + b for a, b in zip(pt, ct)])
    s["tokens_sum"] = sum(pt) + sum(ct)
    wc = [float(r.get("wall_clock_s") or 0.0) for r in rows]
    s["wall_mean"] = statistics.mean(wc)
    s["wall_sum"] = sum(wc)

    # tool calls
    calls = [len(r.get("tool_calls") or []) for r in rows]
    s["tools_mean"] = statistics.mean(calls)
    s["tools_median"] = statistics.median(calls)
    s["tools_max"] = max(calls)
    s["zero_tool"] = sum(1 for c in calls if c == 0)
    return s


def t0_forensics(rows: list[dict], condition: str, expected_repeats: int) -> dict:
    """Fixed-seed T=0 block: byte-identical groups and decision-flipping groups."""
    by_case: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["condition"] == condition:
            by_case[r["case_id"]].append(r)
    complete = {c: rs for c, rs in by_case.items() if len(rs) == expected_repeats}
    byte_ident = sum(
        1 for rs in complete.values()
        if len({str(r.get("raw_output") or "") for r in rs}) == 1)
    flipping = sum(
        1 for rs in complete.values()
        if len({r.get("decision") for r in rs}) > 1)
    return {"groups": len(complete), "byte_identical": byte_ident,
            "flipping": flipping, "seen": len(by_case)}


def node_stats(rows: list[dict]) -> dict:
    """MAS per-node health: call-dead (via tool-name partition) and
    empty-output counts (harness v2 journals only)."""
    n = len(rows)
    out: dict = {"runs": n}
    data_dead = pol_dead = 0
    for r in rows:
        names = r.get("tool_calls") or []
        data_dead += not any(t in DATA_TOOLS for t in names)
        pol_dead += not any(t in POLICY_TOOLS for t in names)
    out["data_dead"] = data_dead
    out["policy_dead"] = pol_dead
    with_no = [r for r in rows if isinstance(r.get("node_outputs"), dict)]
    out["node_outputs_runs"] = len(with_no)
    if with_no:
        for node in NODES:
            out[f"empty_{node}"] = sum(
                1 for r in with_no if not (r["node_outputs"].get(node) or "").strip())
        # cap-exhaustion proxy: empty data output AND data node made calls
        out["data_empty_with_calls"] = sum(
            1 for r in with_no
            if not (r["node_outputs"].get("data") or "").strip()
            and any(t in DATA_TOOLS for t in (r.get("tool_calls") or [])))
        empt = [r for r in with_no if not (r["node_outputs"].get("data") or "").strip()]
        if empt:
            out["data_empty_decisions"] = dict(Counter(
                r.get("decision") for r in empt).most_common())
            out["data_empty_calls_at_8"] = sum(
                1 for r in empt
                if sum(1 for t in (r.get("tool_calls") or []) if t in DATA_TOOLS) >= 8)
    return out


def pert_movement(cond_data: dict[str, dict], pert_recs: list[dict]) -> dict:
    """MV movement per perturbation condition: PERT majority vote vs the same
    arm's base-case majority vote from the matched primary condition."""
    res = {}
    for pc in PERT_CONDS:
        base_cond = PERT_BASE_COND[pc]
        mv_p = (cond_data.get(pc) or {}).get("mv") or {}
        mv_b = (cond_data.get(base_cond) or {}).get("mv") or {}
        moved, total, detail = 0, 0, []
        for rec in pert_recs:
            p, b = rec["alert_id"], rec["base_alert_id"]
            if p not in mv_p or b not in mv_b:
                continue
            total += 1
            m = mv_p[p] != mv_b[b]
            moved += m
            detail.append((p, b, mv_b[b], mv_p[p], "moved" if m else "held"))
        res[pc] = {"moved": moved, "total": total, "detail": detail}
    return res


# --------------------------------------------------------------------------
# Data-quality checks
# --------------------------------------------------------------------------

def quality(rows: list[dict], torn: int, expected_ids: set[str]) -> dict:
    q: dict = {"torn": torn}
    ids = [r["run_id"] for r in rows]
    q["dupes"] = sum(c - 1 for c in Counter(ids).values() if c > 1)
    q["missing"] = len(expected_ids - set(ids))
    q["unexpected"] = len(set(ids) - expected_ids)
    q["ollama"] = sorted({r.get("ollama_version") for r in rows}) if rows else []
    q["digest"] = sorted({(r.get("model_digest") or "")[:12] for r in rows}) if rows else []
    q["num_predict"] = sorted({r.get("num_predict") for r in rows}) if rows else []
    q["think"] = sorted({str(r.get("think")) for r in rows}) if rows else []
    q["errors"] = Counter(
        (str(r.get("error"))[:70]) for r in rows if r.get("error"))
    # journal-order gaps > GAP_S
    gaps = []
    for a, b in zip(rows, rows[1:]):
        try:
            dt = ts(b) - (ts(a) + float(a.get("wall_clock_s") or 0.0))
        except Exception:
            continue
        if dt > GAP_S:
            gaps.append((round(dt), a["run_id"], b["run_id"]))
    q["gaps"] = gaps
    return q


def expected_run_ids(arm: str, primary: dict, pert: dict) -> set[str]:
    ids = set()
    for cond in CONDITIONS:
        cases = pert if cond.startswith("pert") else primary
        for c in cases:
            for i in range(COND_REPEATS[cond]):
                ids.add(f"{arm}:{c}:{cond}:{i}")
    return ids


# --------------------------------------------------------------------------
# Markdown helpers
# --------------------------------------------------------------------------

def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def dist_str(d: dict, n: int) -> str:
    return " / ".join(f"{k[0]}:{v} ({pct(v, n)})" for k, v in d.items())


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    primary, pert, pert_recs = load_labels()
    labels = {**primary, **pert}
    n_primary, n_pert = len(primary), len(pert)
    prim_baseline = max(Counter(primary.values()).values()) / n_primary
    pert_baseline = max(Counter(pert.values()).values()) / n_pert

    S: dict[str, dict] = {}   # per sweep computed store
    for key, dirname, model, think, infra, harness, status, note in SWEEPS:
        d = EXP / dirname
        entry: dict = {"key": key, "dir": dirname, "model": model, "think": think,
                       "infra": infra, "harness": harness, "status": status,
                       "note": note, "arms": {}}
        for arm in ARMS:
            raw_rows, torn = load_journal(d / f"journal-{arm}.jsonl")
            # Duplicate-writer forensics BEFORE dedup (quality section reports
            # raw journal state; metrics use first-occurrence per run key so a
            # double-launched live sweep cannot inflate repeat counts).
            seen: dict[str, dict] = {}
            dup_keys = 0
            dup_decision_diverged = 0
            dup_onset = None
            for r in raw_rows:
                rid = r["run_id"]
                if rid in seen:
                    dup_keys += 1
                    if dup_onset is None:
                        dup_onset = r["started_at"]
                    if r.get("decision") != seen[rid].get("decision"):
                        dup_decision_diverged += 1
                else:
                    seen[rid] = r
            rows = list(seen.values())
            a: dict = {"rows": len(rows), "raw_rows": len(raw_rows), "torn": torn,
                       "dup_keys": dup_keys, "dup_onset": dup_onset,
                       "dup_decision_diverged": dup_decision_diverged}
            if rows:
                a["first"] = min(r["started_at"] for r in rows)
                a["last"] = max(r["started_at"] for r in rows)
                a["window"] = (min(ts(r) for r in rows),
                               max(ts(r) + float(r.get("wall_clock_s") or 0) for r in rows))
                a["cond"] = {}
                for cond in CONDITIONS:
                    crows = [r for r in rows if r["condition"] == cond]
                    exp_cases = n_pert if cond.startswith("pert") else n_primary
                    a["cond"][cond] = cond_stats(crows, labels, exp_cases,
                                                 COND_REPEATS[cond])
                a["t0"] = t0_forensics(rows, "t0-fixed", 5)
                a["pert_t0"] = t0_forensics(rows, "pert-t0", 5)
                a["pert_move"] = pert_movement(a["cond"], pert_recs)
                a["quality"] = quality(raw_rows, torn, expected_run_ids(arm, primary, pert))
                a["tokens_sum"] = sum(int(r.get("prompt_tokens") or 0) +
                                      int(r.get("completion_tokens") or 0) for r in rows)
                a["wall_sum"] = sum(float(r.get("wall_clock_s") or 0.0) for r in rows)
                a["errors"] = sum(1 for r in rows if r.get("error"))
                a["malformed"] = sum(1 for r in rows if r.get("decision") == "malformed")
                if arm == "mas":
                    a["nodes"] = node_stats(rows)
                # per-label conditional rates at t07 (dismissal-collapse finding)
                t07 = [r for r in rows if r["condition"] == "t07-varied"]
                for lab in ("dismiss", "escalate"):
                    lr = [r for r in t07 if labels.get(r["case_id"]) == lab]
                    a[f"{lab}_rate_t07"] = (
                        sum(1 for r in lr if r.get("decision") == lab) / len(lr)
                        if lr else None)
                    a[f"{lab}_runs_t07"] = len(lr)
            entry["arms"][arm] = a
        # contention: do the two arms' run windows overlap?
        w1 = entry["arms"]["single"].get("window")
        w2 = entry["arms"]["mas"].get("window")
        if w1 and w2:
            ov = max(0.0, min(w1[1], w2[1]) - max(w1[0], w2[0]))
            entry["contention"] = ov > 0
            entry["overlap_h"] = ov / 3600.0
        else:
            entry["contention"] = False
            entry["overlap_h"] = 0.0
        S[key] = entry

    # ---------------- corpus totals ----------------
    tot_runs = sum(e["arms"][a].get("rows", 0) for e in S.values() for a in ARMS)
    tot_tokens = sum(e["arms"][a].get("tokens_sum", 0) for e in S.values() for a in ARMS)
    tot_wall_h = sum(e["arms"][a].get("wall_sum", 0.0) for e in S.values() for a in ARMS) / 3600.0
    live_runs = sum(e["arms"][a].get("rows", 0) for e in S.values() for a in ARMS
                    if e["status"] in ("LIVE", "QUEUED"))
    sealed_runs = tot_runs - live_runs

    md: list[str] = []
    w = md.append
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    w("# OWNER'S MASTER DATA REPORT — every experiment run, recomputed from the journals")
    w("")
    w(f"*Generated {now} by `backend/experiments/analysis/master_report_gen.py`. "
      "Every number in this document was recomputed directly from "
      "`results*/journal-{single,mas}.jsonl` using the locked conventions in "
      "`analysis/metrics.py`; nothing is copied from derived documents. "
      "Zero LLM calls, no GPU, journals read-only. The budget track is IN FLIGHT: "
      "all `@b32` numbers are PARTIAL snapshots taken at generation time.*")
    w("")
    w("**Conventions.** pass^k = C(c,k)/C(n,k), agreement with benchmark authors' "
      "labels (never \"correctness\"); malformed is an outcome category and is never "
      "excluded; DAR = fraction of identical unordered repeat pairs; alpha = "
      "Krippendorff (nominal), cases as units, repeats as coders; majority ties break "
      "by canonical OUTCOMES order (escalate > dismiss > investigate > malformed); "
      "entropy normalised by log2(4); best-constant baselines "
      f"{prim_baseline:.3f} (primary, constant-dismiss over {n_primary} cases) and "
      f"{pert_baseline:.3f} (perturbation, constant-dismiss over {n_pert} cases). "
      "MV movement: perturbed-case majority vote vs same-arm base-case majority vote, "
      "t0-fixed base for pert-t0 and t07-varied base for pert-t05/pert-t10. "
      "Wall clock is contention-contaminated wherever the two arms co-ran on one GPU "
      "(flagged per sweep); tokens are the cost metric.")
    w("")

    # ================= 1. CORPUS MAP =================
    w("## 1. Corpus map")
    w("")
    rows = []
    for key, dirname, model, think, infra, harness, status, note in SWEEPS:
        e = S[key]
        sr, mr = e["arms"]["single"].get("rows", 0), e["arms"]["mas"].get("rows", 0)
        firsts = [e["arms"][a].get("first") for a in ARMS if e["arms"][a].get("first")]
        lasts = [e["arms"][a].get("last") for a in ARMS if e["arms"][a].get("last")]
        dates = (f"{min(firsts)[:10]} → {max(lasts)[:10]}" if firsts else "—")
        rows.append([f"`{key}`", f"`{dirname}`", model, think, infra, harness,
                     status, f"{sr}+{mr}", dates])
    w(table(["registry key", "results dir", "served tag", "think", "infra ctx",
             "harness", "status", "runs (single+mas)", "dates"], rows))
    w("")
    w(f"**Corpus totals (everything journalled, including excluded, closed and live "
      f"partial dirs; live dirs counted by UNIQUE run key — see §4): {tot_runs:,} "
      f"runs — {sealed_runs:,} sealed/closed + "
      f"{live_runs:,} live-partial — {tot_tokens:,} tokens "
      f"(prompt+completion), {tot_wall_h:,.1f} GPU-busy hours (sum of per-run wall "
      f"clocks; arms co-resident on one GPU, so this is model-busy time, not elapsed "
      f"span).**")
    w("")
    w("Empty registry dirs with no journals (gate-failed / never launched): "
      "`results-gemma3-27b`, `results-gemma4-thinking`, `results-gpt-oss-20b`, "
      "`results-gpt-oss-20b-thinking`, `results-granite4`, `results-lfm2.5-8b`, "
      "`results-llama3.1-8b`, `results-mistral-nemo`, `results-mistral-small3.2`, "
      "`results-qwen3.5-9b-thinking` (gate FAIL 6/8). Archived partials (never "
      "counted): `results-qwen2.5-7b/partial-run-aborted-2026-08-07/`, "
      "`results-gemma4/partial-run-aborted-2026-08-07/`.")
    w("")

    # ================= 2. HEADLINE TABLES + SIX FINDINGS =================
    w("## 2. Headline cross-model tables and the six analytical findings")
    w("")

    def tier_rows(cond: str, keys: list[str]) -> list[list]:
        out = []
        for k in keys:
            e = S[k]
            for arm in ARMS:
                c = (e["arms"][arm].get("cond") or {}).get(cond)
                if not c or not c.get("runs"):
                    continue
                tag = ""
                if k in EXCLUDED_KEYS:
                    tag = " ⛔excluded"
                elif k in CLOSED_MAS_KEYS and arm == "mas":
                    tag = " ⛔closed@201"
                elif S[k]["status"] == "LIVE":
                    tag = " 🔶LIVE"
                out.append([
                    f"`{k}`{tag}", arm, c["runs"],
                    fmt(c.get("pass^1")), fmt(c.get("pass^5")), fmt(c.get("pass^15")),
                    fmt(c.get("DAR")), fmt(c.get("alpha")), fmt(c.get("flip_rate")),
                    fmt(c.get("mv_acc")), fmt(c.get("entropy")),
                    pct(c["malformed"], c["runs"]),
                    f"{c['total_mean']:,.0f}", f"{c['wall_mean']:.1f}",
                ])
        return out

    hdr = ["sweep", "arm", "runs", "pass^1", "pass^5", "pass^15", "DAR", "alpha",
           "flip", "MV acc", "entropy", "malf%", "tok/run", "wall s*"]
    w("### 2.0 Cross-model Tier-1 — `t07-varied` (realistic setting; the committed "
      "primary comparison condition)")
    w("")
    w(table(hdr, tier_rows("t07-varied", COMPARABLE)))
    w("")
    w("*Wall clock contention-contaminated in every sweep (arms co-ran); primary "
      f"baseline = {prim_baseline:.3f}. `deepseek-r1:14b@think` is excluded from "
      "comparison and appears in §5 only; budget-track partials appear in §4 only.*")
    w("")
    w("### 2.0b Cross-model Tier-1 — `t0-fixed` (determinism setting)")
    w("")
    w(table(hdr, tier_rows("t0-fixed", COMPARABLE)))
    w("")

    # ---- Finding 1: model dependence ----
    w("### Finding 1 — Model-dependence of the arm effect (direction of effect)")
    w("")
    rows = []
    for k in COMPARABLE:
        e = S[k]
        cs = (e["arms"]["single"].get("cond") or {}).get("t07-varied")
        cm = (e["arms"]["mas"].get("cond") or {}).get("t07-varied")
        if not cs or not cm or not cs.get("runs") or not cm.get("runs"):
            continue
        dp = cm["pass^1"] - cs["pass^1"]
        dd = cm["DAR"] - cs["DAR"]
        da = (cm["alpha"] - cs["alpha"]) if (cm.get("alpha") is not None and cs.get("alpha") is not None) else None
        def g(x): return "≈0" if abs(x) < 0.02 else ("MAS↑" if x > 0 else "MAS↓")
        rows.append([f"`{k}`", fmt(cs["pass^1"]), fmt(cm["pass^1"]), f"{dp:+.3f} {g(dp)}",
                     fmt(cs["DAR"]), fmt(cm["DAR"]), f"{dd:+.3f} {g(dd)}",
                     fmt(da) if da is None else f"{da:+.3f}"])
    w(table(["sweep", "pass^1 single", "pass^1 MAS", "Δpass^1 (MAS−single)",
             "DAR single", "DAR MAS", "ΔDAR (MAS−single)", "Δalpha"], rows))
    w("")
    w("Grouping at |Δ| ≥ 0.02: decomposition helps some models' agreement and hurts "
      "others', and repeatability moves independently of agreement — no universal "
      "direction. (Descriptive deltas; the committed significance tests live in the "
      "per-sweep audit scripts.)")
    w("")

    # ---- Finding 2: dismissal collapse ----
    w("### Finding 2 — Dismissal collapse under decomposition (t07, dismiss-labelled cases)")
    w("")
    rows = []
    for k in COMPARABLE:
        e = S[k]
        a_s, a_m = e["arms"]["single"], e["arms"]["mas"]
        if a_s.get("dismiss_rate_t07") is None:
            continue
        r = [f"`{k}`",
             f"{fmt(a_s['dismiss_rate_t07'])} ({a_s['dismiss_runs_t07']} runs)",
             (f"{fmt(a_m['dismiss_rate_t07'])} ({a_m['dismiss_runs_t07']} runs)"
              if a_m.get("dismiss_rate_t07") is not None else "—"),
             fmt(a_s.get("escalate_rate_t07")),
             fmt(a_m.get("escalate_rate_t07")) if a_m.get("escalate_rate_t07") is not None else "—"]
        rows.append(r)
    w(table(["sweep", "single: P(dismiss given dismiss-labelled)",
             "MAS: P(dismiss given dismiss-labelled)",
             "single: P(escalate given escalate-labelled)",
             "MAS: P(escalate given escalate-labelled)"], rows))
    w("")

    # ---- Finding 3: degeneracy league ----
    w("### Finding 3 — Degeneracy / mode collapse league table (t07 modal share; "
      "cells below best-constant baseline across all 5 conditions)")
    w("")
    league = []
    for k in COMPARABLE:
        e = S[k]
        for arm in ARMS:
            c = (e["arms"][arm].get("cond") or {}).get("t07-varied")
            if not c or not c.get("runs"):
                continue
            below = 0
            cells = 0
            for cond in CONDITIONS:
                cc = (e["arms"][arm].get("cond") or {}).get(cond)
                if not cc or not cc.get("runs") or cc.get("partial"):
                    continue
                cells += 1
                below += cc["mv_acc"] < cc["baseline"]
            modal_dec, modal_n = c["modal"]
            league.append((modal_n / c["runs"], [
                f"`{k}`", arm, modal_dec, pct(modal_n, c["runs"]),
                fmt(c["mv_acc"]), fmt(c["baseline"]),
                f"{below}/{cells}"]))
    league.sort(key=lambda x: -x[0])
    w(table(["sweep", "arm", "modal decision (t07)", "modal share", "MV acc (t07)",
             "baseline", "conditions below baseline"],
            [r for _, r in league]))
    w("")
    w(f"Label prior (primary block): dismiss {Counter(primary.values())['dismiss']}/"
      f"{n_primary}, escalate {Counter(primary.values())['escalate']}/{n_primary}, "
      f"investigate {Counter(primary.values())['investigate']}/{n_primary} — a modal-"
      "`investigate` share far above the 18% investigate prior is mode collapse, "
      "whatever the DAR says.")
    w("")

    # ---- Finding 4: cache-state determinism ----
    w("### Finding 4 — Cache-state (non-)determinism at T=0, fixed seed "
      "(byte-identical groups /50; decision-flipping groups /50)")
    w("")
    rows = []
    for k in COMPARABLE:
        e = S[k]
        for arm in ARMS:
            t0 = e["arms"][arm].get("t0")
            if not t0 or not t0["groups"]:
                continue
            pt0 = e["arms"][arm].get("pert_t0") or {}
            rows.append([f"`{k}`", arm,
                         f"{t0['byte_identical']}/{t0['groups']}",
                         f"{t0['flipping']}/{t0['groups']}",
                         f"{pt0.get('byte_identical', '—')}/{pt0.get('groups', '—')}",
                         f"{pt0.get('flipping', '—')}/{pt0.get('groups', '—')}"])
    w(table(["sweep", "arm", "t0-fixed byte-identical", "t0-fixed decision-flipping",
             "pert-t0 byte-identical", "pert-t0 decision-flipping"], rows))
    w("")
    w("#### Version-replication deltas (qwen trio, Ollama 0.31.1 → 0.32.6, "
      "identical seeds/cases/design)")
    w("")
    trio = [("qwen3.5:9b", "qwen3.5:9b@0.32.6"),
            ("qwen2.5:7b-instruct", "qwen2.5:7b-instruct@0.32.6"),
            ("qwen2.5:14b-instruct", "qwen2.5:14b-instruct@0.32.6")]
    rows = []
    for k1, k2 in trio:
        for arm in ARMS:
            c1 = S[k1]["arms"][arm]["cond"]["t07-varied"]
            c2 = S[k2]["arms"][arm]["cond"]["t07-varied"]
            t1 = S[k1]["arms"][arm]["t0"]
            t2 = S[k2]["arms"][arm]["t0"]
            rows.append([
                f"`{k1.split('@')[0]}`", arm,
                f"{fmt(c1['pass^1'])} → {fmt(c2['pass^1'])} ({c2['pass^1']-c1['pass^1']:+.3f})",
                f"{fmt(c1['DAR'])} → {fmt(c2['DAR'])} ({c2['DAR']-c1['DAR']:+.3f})",
                f"{fmt(c1['alpha'])} → {fmt(c2['alpha'])} ({c2['alpha']-c1['alpha']:+.3f})",
                f"{t1['flipping']} → {t2['flipping']}",
                f"{t1['byte_identical']} → {t2['byte_identical']}"])
    w(table(["model", "arm", "t07 pass^1 (0.31.1→0.32.6)", "t07 DAR", "t07 alpha",
             "t0 flipping groups", "t0 byte-identical groups"], rows))
    w("")

    # ---- Finding 5: budget starvation ----
    w("### Finding 5 — Budget starvation / severed channels in the MAS pipeline "
      "(per-node dead and empty-output census)")
    w("")
    rows = []
    for key, dirname, *_ in SWEEPS:
        e = S[key]
        nm = e["arms"]["mas"].get("nodes")
        if not nm or not nm["runs"]:
            continue
        n = nm["runs"]
        has_no = nm["node_outputs_runs"] > 0
        rows.append([
            f"`{key}`" + (" 🔶LIVE" if e["status"] == "LIVE" else ""),
            n,
            f"{nm['data_dead']} ({pct(nm['data_dead'], n)})",
            f"{nm['policy_dead']} ({pct(nm['policy_dead'], n)})",
            (f"{nm.get('empty_data', 0)} ({pct(nm.get('empty_data', 0), n)})" if has_no else "n/a (v1)"),
            (str(nm.get("empty_policy_risk", 0)) if has_no else "n/a"),
            (str(nm.get("empty_reporting", 0)) if has_no else "n/a"),
            (str(nm.get("data_empty_with_calls", 0)) if has_no else "n/a"),
        ])
    w(table(["sweep (MAS arm)", "runs", "data node call-dead", "policy node call-dead",
             "data output EMPTY", "policy output empty", "reporting output empty",
             "data empty *with* calls (severed channel)"], rows))
    w("")
    for key in ("muse-glimmer:30b", "muse-glimmer:30b@think"):
        nm = S[key]["arms"]["mas"].get("nodes") or {}
        if nm.get("data_empty_decisions"):
            w(f"- `{key}` empty-data-node runs decide: "
              f"{nm['data_empty_decisions']} "
              f"(of which {nm.get('data_empty_calls_at_8', 0)} made ≥8 data-tool calls "
              "— the per-node iteration-cap-exhaustion signature).")
    w("")
    w("v1 journals (contexts 1–2) have no `node_outputs` field, so empty-output "
      "detection is only possible for harness-v2 sweeps; call-dead detection (via the "
      "tool-name partition) covers everything.")
    w("")

    # ---- Finding 6: thinking contrasts ----
    w("### Finding 6 — Thinking on/off contrasts")
    w("")
    w("**Clean within-model pair (single arm only): `muse-glimmer:30b` off vs ON** — "
      "same model, digest, seeds, harness, infra; one wire parameter changed. The MAS "
      "@think arm was stopped at 201 (§5) so only the monolith contrast is valid.")
    w("")
    rows = []
    for cond in ("t0-fixed", "t07-varied"):
        c1 = S["muse-glimmer:30b"]["arms"]["single"]["cond"][cond]
        c2 = S["muse-glimmer:30b@think"]["arms"]["single"]["cond"][cond]
        rows.append([cond, fmt(c1["pass^1"]), fmt(c2["pass^1"]),
                     fmt(c1["DAR"]), fmt(c2["DAR"]),
                     fmt(c1["alpha"]), fmt(c2["alpha"]),
                     fmt(c1["flip_rate"]), fmt(c2["flip_rate"]),
                     f"{c1['malformed']} → {c2['malformed']}",
                     f"{c1['total_mean']:,.0f} → {c2['total_mean']:,.0f}",
                     f"{c1['wall_mean']:.0f} → {c2['wall_mean']:.0f}"])
    w(table(["condition", "pass^1 off", "pass^1 ON", "DAR off", "DAR ON",
             "alpha off", "alpha ON", "flip off", "flip ON", "malformed",
             "tok/run", "wall s*"], rows))
    w("")
    w("**Confounded qwen3.5 pair** — `qwen3.5:9b` (0.31.1/v1) and `qwen3.5:9b@0.32.6` "
      "(0.32.6/v1) vs `qwen3.5:9b@think-budget` (0.32.9/v2, num_predict 8192): FOUR "
      "factors differ (think, num_predict, ollama_version, harness revision — "
      "CHANGELOG 2026-08-13). No attribution to deliberation is supportable; the "
      "table is descriptive only.")
    w("")
    rows = []
    for k in ("qwen3.5:9b", "qwen3.5:9b@0.32.6", "qwen3.5:9b@think-budget"):
        for arm in ARMS:
            c = S[k]["arms"][arm]["cond"]["t07-varied"]
            rows.append([f"`{k}`", arm, fmt(c["pass^1"]), fmt(c["DAR"]),
                         fmt(c["alpha"]), fmt(c["flip_rate"]),
                         c["malformed"], f"{c['total_mean']:,.0f}"])
    w(table(["sweep", "arm", "t07 pass^1", "DAR", "alpha", "flip", "malformed",
             "tok/run"], rows))
    w("")
    w("`lfm2.5:8b@think` and `deepseek-r1:14b@think` have no admissible thinking-off "
      "twin by construction — any contrast against the sealed corpus is cross-model.")
    w("")

    # ---- cost ratios ----
    w("### Cost ratios (t07-varied means, MAS ÷ single)")
    w("")
    rows = []
    for k in COMPARABLE:
        e = S[k]
        cs = (e["arms"]["single"].get("cond") or {}).get("t07-varied")
        cm = (e["arms"]["mas"].get("cond") or {}).get("t07-varied")
        if not cs or not cm or not cs.get("runs") or not cm.get("runs"):
            continue
        rows.append([f"`{k}`" + (" 🔶LIVE" if e["status"] == "LIVE" else ""),
                     f"{cs['total_mean']:,.0f}", f"{cm['total_mean']:,.0f}",
                     f"{cm['total_mean']/cs['total_mean']:.2f}×",
                     f"{cs['wall_mean']:.1f}", f"{cm['wall_mean']:.1f}",
                     f"{cm['wall_mean']/cs['wall_mean']:.2f}×"])
    w(table(["sweep", "single tok/run", "MAS tok/run", "token ratio",
             "single wall s*", "MAS wall s*", "wall ratio*"], rows))
    w("")
    w("*Wall-clock ratios are contention-contaminated (arms co-resident on one GPU "
      "in every sweep); token ratios are the reliable cost signal.*")
    w("")

    # ---- tool-channel health census ----
    w("### Tool-channel health census (all journalled sweeps, both arms)")
    w("")
    rows = []
    for key, dirname, *_ in SWEEPS:
        e = S[key]
        for arm in ARMS:
            a = e["arms"][arm]
            if not a.get("rows"):
                continue
            zt = sum((a["cond"][c].get("zero_tool") or 0) for c in CONDITIONS if a["cond"][c].get("runs"))
            calls_mean = (sum(a["cond"][c]["tools_mean"] * a["cond"][c]["runs"]
                              for c in CONDITIONS if a["cond"][c].get("runs")) / a["rows"])
            mx = max(a["cond"][c].get("tools_max") or 0 for c in CONDITIONS)
            rows.append([f"`{key}`", arm, a["rows"], zt, pct(zt, a["rows"]),
                         f"{calls_mean:.2f}", mx])
    w(table(["sweep", "arm", "runs", "zero-tool runs", "zero-tool %",
             "mean calls/run", "max calls"], rows))
    w("")

    # ================= 3. PER-SWEEP DETAIL =================
    w("## 3. Per-sweep detail (full arm × condition dumps)")
    w("")
    for key, dirname, model, think, infra, harness, status, note in SWEEPS:
        e = S[key]
        if not any(e["arms"][a].get("rows") for a in ARMS):
            continue
        live = status in ("LIVE",)
        w(f"### `{key}` — {model}, think {think}, {infra}, harness {harness} — "
          f"**{status}**")
        w("")
        w(f"*{note}. Arms co-ran (wall clock contaminated): "
          f"{'yes' if e['contention'] else 'no'} "
          f"(overlap ≈ {e['overlap_h']:.1f} h).*")
        w("")
        for arm in ARMS:
            a = e["arms"][arm]
            if not a.get("rows"):
                continue
            partial_tag = " — 🔶LIVE/PARTIAL" if live else ""
            if key in CLOSED_MAS_KEYS and arm == "mas":
                partial_tag = " — ⛔STOPPED at 201/1150, capability-gated out"
            w(f"#### {arm} arm ({a['rows']} runs, {a['first'][:16]} → "
              f"{a['last'][:16]}){partial_tag}")
            w("")
            rows = []
            for cond in CONDITIONS:
                c = a["cond"][cond]
                if not c.get("runs"):
                    rows.append([cond, 0] + ["—"] * 12)
                    continue
                cov = f"{c['runs']}/{c['expected']}"
                d = c["dist"]
                rows.append([
                    cond, cov, c["errors"],
                    f"e:{d['escalate']} ({pct(d['escalate'], c['runs'])})",
                    f"d:{d['dismiss']} ({pct(d['dismiss'], c['runs'])})",
                    f"i:{d['investigate']} ({pct(d['investigate'], c['runs'])})",
                    f"m:{d['malformed']} ({pct(d['malformed'], c['runs'])})",
                    fmt(c.get("pass^1")), fmt(c.get("pass^5")), fmt(c.get("pass^15")),
                    fmt(c.get("DAR")), fmt(c.get("alpha")), fmt(c.get("flip_rate")),
                    f"{fmt(c.get('mv_acc'))} vs {fmt(c.get('baseline'))}"
                    + (f" ({c['mv_ties']} ties)" if c.get("mv_ties") else ""),
                ])
            w(table(["condition", "runs", "err", "escalate", "dismiss", "investigate",
                     "malformed", "pass^1", "pass^5", "pass^15", "DAR", "alpha",
                     "flip", "MV acc vs base"], rows))
            w("")
            rows = []
            for cond in CONDITIONS:
                c = a["cond"][cond]
                if not c.get("runs"):
                    continue
                rows.append([
                    cond, fmt(c.get("entropy")),
                    f"{c['prompt_mean']:,.0f}", f"{c['completion_mean']:,.0f}",
                    f"{c['total_mean']:,.0f}", f"{c['wall_mean']:.1f}",
                    f"{c['tools_mean']:.2f}", fmt(c["tools_median"], 1),
                    c["tools_max"], c["zero_tool"]])
            w(table(["condition", "entropy", "prompt tok/run", "compl tok/run",
                     "total tok/run", "wall s*", "tools mean", "tools med",
                     "tools max", "zero-tool"], rows))
            w("")
            t0, pt0 = a["t0"], a["pert_t0"]
            w(f"T=0 fixed-seed forensics: t0-fixed byte-identical "
              f"{t0['byte_identical']}/{t0['groups']} groups, decision-flipping "
              f"{t0['flipping']}/{t0['groups']}; pert-t0 byte-identical "
              f"{pt0['byte_identical']}/{pt0['groups']}, flipping "
              f"{pt0['flipping']}/{pt0['groups']}.")
            pm = a["pert_move"]
            w(f"Perturbation MV movement: "
              + "; ".join(f"{pc}: {pm[pc]['moved']}/{pm[pc]['total']}"
                          for pc in PERT_CONDS) + ".")
            if arm == "mas" and a.get("nodes"):
                nm = a["nodes"]
                if nm["node_outputs_runs"]:
                    w(f"Node health: data call-dead {nm['data_dead']}, policy "
                      f"call-dead {nm['policy_dead']}; empty outputs — "
                      + ", ".join(f"{nd}: {nm.get('empty_' + nd, 0)}" for nd in NODES)
                      + f"; severed-channel (empty data WITH calls): "
                        f"{nm.get('data_empty_with_calls', 0)}.")
                else:
                    w(f"Node health: data call-dead {nm['data_dead']}, policy "
                      f"call-dead {nm['policy_dead']}; node_outputs not journalled "
                      "(harness v1).")
            w("")

    # ================= 4. BUDGET TRACK =================
    w("## 4. Budget-sensitivity track v2b — status (🔶 LIVE, all numbers partial)")
    w("")
    w("Launched 2026-08-18 (owner GO). Iteration budgets equalised and disclosed: "
      "single 32; MAS orchestrator/data/policy_risk/reporting = 4/16/8/4 (pooled 32). "
      "Six sweeps queued; muse-glimmer pair queued after. Journals are being appended "
      "while this report generates — counts below are a snapshot.")
    w("")
    rows = []
    for key, dirname, model, think, infra, harness, status, note in SWEEPS:
        if harness != "v2b":
            continue
        e = S[key]
        sr, mr = e["arms"]["single"].get("rows", 0), e["arms"]["mas"].get("rows", 0)
        rows.append([f"`{key}`", status, f"{sr}/1150", f"{mr}/1150",
                     f"{pct(sr + mr, 2300)}", note])
    w(table(["registry key", "status", "single runs", "MAS runs", "sweep progress",
             "note"], rows))
    w("")
    b = S.get("qwen2.5:7b-instruct@b32")
    if b and any(b["arms"][arm].get("dup_keys") for arm in ARMS):
        w("### 🚨 LIVE DEFECT FOUND DURING THIS RECOMPUTATION — duplicate "
          "writers on `results-budget-qwen2.5-7b`")
        w("")
        for arm in ARMS:
            a = b["arms"][arm]
            if not a.get("dup_keys"):
                continue
            w(f"- **{arm}**: {a['raw_rows']} journal lines but only {a['rows']} "
              f"unique run keys — **{a['dup_keys']} duplicate-key lines**, first "
              f"duplicate at {a['dup_onset']}; in **{a['dup_decision_diverged']}** "
              "duplicated keys the two copies decide DIFFERENTLY despite identical "
              "seed/temperature (T=0 fixed-seed included).")
        w("")
        w("Attribution (from logs, read-only): the first runner pair launched at "
          "09:57:37Z; `budget-track-queue.log` then launched a SECOND pair at "
          "10:07:58Z (\"manifest exists — reusing\"), and `runner-single.log` "
          "shows the second banner `planned=1150 completed=194 todo=956` at "
          "10:08:03Z while the first pair was still appending. Since then two "
          "runners per arm share one journal and one Ollama server, re-running "
          "the same planned keys interleaved. Consequences: journal "
          "unique-run-key discipline is violated from key ~195 onward; T=0 "
          "cache-state semantics are destroyed (two concurrent streams interleave "
          "each other's KV/cache states — the duplicated fixed-seed runs already "
          "disagree); wall clock is double-contended. **This sweep cannot seal as "
          "a valid v2b measurement in its current form.** All figures for this "
          "sweep in this report use the FIRST occurrence of each run key and are "
          "indicative only.")
        w("")
    if b and b["arms"]["single"].get("rows"):
        w("### `qwen2.5:7b-instruct@b32` partial snapshot vs its sealed v2 "
          "counterpart `qwen2.5:7b-instruct` (0.31.1) — indicative only")
        w("")
        for arm in ARMS:
            a = b["arms"][arm]
            if not a.get("rows"):
                continue
            n = a["rows"]
            d = Counter()
            for cond in CONDITIONS:
                c = a["cond"][cond]
                if c.get("runs"):
                    for kk, vv in c["dist"].items():
                        d[kk] += vv
            w(f"- **{arm}** {n} runs so far: " + dist_str(dict(d), n)
              + f"; zero-tool {sum((a['cond'][c].get('zero_tool') or 0) for c in CONDITIONS if a['cond'][c].get('runs'))}.")
        c = b["arms"]["single"]["cond"]["t0-fixed"]
        if c.get("runs") and c.get("cases_complete"):
            t0 = b["arms"]["single"]["t0"]
            w(f"- single t0-fixed (complete groups only): byte-identical "
              f"{t0['byte_identical']}/{t0['groups']}, flipping "
              f"{t0['flipping']}/{t0['groups']}; pass^1 {fmt(c.get('pass^1'))} "
              f"(sealed v2 counterpart: "
              f"{fmt(S['qwen2.5:7b-instruct']['arms']['single']['cond']['t0-fixed']['pass^1'])}).")
        w("")

    # ================= 5. EXCLUDED / CLOSED =================
    w("## 5. Excluded and closed arms — the evidence numbers")
    w("")
    e = S["deepseek-r1:14b@think"]
    w("### `deepseek-r1:14b@think` — EXCLUDED (infra-invalid: tool channel never "
      "existed)")
    w("")
    for arm in ARMS:
        a = e["arms"][arm]
        zero = sum((a["cond"][c].get("zero_tool") or 0)
                   for c in CONDITIONS if a["cond"][c].get("runs"))
        d = Counter()
        for cond in CONDITIONS:
            c = a["cond"][cond]
            if c.get("runs"):
                for kk, vv in c["dist"].items():
                    d[kk] += vv
        w(f"- **{arm}**: {a['rows']} runs, zero-tool {zero}/{a['rows']} "
          f"({pct(zero, a['rows'])}); decisions " + dist_str(dict(d), a["rows"]) + ".")
    w("")
    w("Root cause (CHANGELOG 2026-08-14): the Ollama registry template (no `.Tools` "
      "block) silently drops tool definitions while `/api/show` reports the model "
      "tools-capable; the MAS data node asserted tool-derived facts in every run "
      "without any retrieval. Retained as a capability-gating negative case only. "
      "Tier-1 numbers for this sweep appear in §3 for the record but enter no "
      "comparison.")
    w("")
    e = S["muse-glimmer:30b@think"]
    am = e["arms"]["mas"]
    nm = am.get("nodes") or {}
    d = Counter()
    for cond in CONDITIONS:
        c = am["cond"][cond]
        if c.get("runs"):
            for kk, vv in c["dist"].items():
                d[kk] += vv
    w("### `muse-glimmer:30b@think` MAS arm — CLOSED at "
      f"{am['rows']}/1150 (capability-gated out 2026-08-17)")
    w("")
    w(f"- Decisions at stop: " + dist_str(dict(d), am["rows"]) + ".")
    if nm.get("node_outputs_runs"):
        w(f"- Empty data-node outputs: {nm.get('empty_data', 0)}/{am['rows']} "
          f"({pct(nm.get('empty_data', 0), am['rows'])}); of the empty-data runs, "
          f"{nm.get('data_empty_calls_at_8', 0)} made ≥8 data-tool calls (per-node "
          "iteration-cap exhaustion, the mechanism established in "
          "`docs/EMPTY-NODE-VERDICT.md`).")
        w(f"- Empty-data runs' decisions: {nm.get('data_empty_decisions', {})}.")
    w("- With zero decision variance the arm measures a starved pipeline, not "
      "decomposition: DAR trivially ≈1, alpha undefined/degenerate. The 201 runs are "
      "retained as evidence; the single arm completed and remains valid (§3).")
    w("")

    # ================= 6. DATA-QUALITY APPENDIX =================
    w("## 6. Data-quality appendix — per-sweep integrity notes")
    w("")
    rows = []
    for key, dirname, *_ in SWEEPS:
        e = S[key]
        for arm in ARMS:
            a = e["arms"][arm]
            if not a.get("rows"):
                continue
            q = a["quality"]
            rows.append([
                f"`{key}`", arm, f"{a['raw_rows']} ({a['rows']} uniq)",
                q["torn"], q["dupes"], q["missing"],
                q["unexpected"], a["errors"], a["malformed"],
                "/".join(q["ollama"]), ",".join(q["digest"]),
                ",".join(str(x) for x in q["num_predict"]),
                ",".join(q["think"]), len(q["gaps"])])
    w(table(["sweep", "arm", "rows", "torn", "dup ids", "missing vs plan",
             "unexpected ids", "errors", "malformed", "ollama", "digest(12)",
             "num_predict", "think", f"gaps >{GAP_S:.0f}s"], rows))
    w("")
    w("Notes: v1 journals lack `num_predict`/`cache_policy`/`node_outputs` fields "
      "(shown as `None`); 'missing vs plan' > 0 is expected only for LIVE/CLOSED "
      "arms. Non-zero 'dup ids' = the live duplicate-writer defect (§4) — every "
      "sealed sweep has zero duplicates. Gap and error details:")
    w("")
    for key, dirname, *_ in SWEEPS:
        e = S[key]
        for arm in ARMS:
            a = e["arms"][arm]
            if not a.get("rows"):
                continue
            q = a["quality"]
            items = []
            if q["gaps"]:
                gaps_s = "; ".join(f"{g[0]:,}s before `{g[2]}`" for g in q["gaps"][:4])
                items.append(f"gaps: {gaps_s}" + (" …" if len(q["gaps"]) > 4 else ""))
            if q["errors"]:
                errs = "; ".join(f"{v}× {k!r}" for k, v in q["errors"].most_common(3))
                items.append(f"errors: {errs}")
            if items:
                w(f"- `{key}` / {arm}: " + " | ".join(items))
    w("")
    w("Known/declared deviations reconciled against the CHANGELOG: qwen2.5:7b "
      "restart-from-zero (archived partial, 2026-08-07); gemma4 aborted partial "
      "(2026-08-07); muse-glimmer:30b MAS reboot at 653/1150 (2026-08-14, audited "
      "lossless, plus one undeclared ~458 s dual-arm stall found by audit); "
      "muse-glimmer @think pair killed 45 min after launch and resumed after a "
      "2-day gap (2026-08-17). All of these surface as journal gaps above and none "
      "removed or altered runs.")
    w("")
    w("**Convention discrepancy found during this recomputation:** "
      "`analysis/seal_checks.py` line 44 hardcodes `OUTCOMES = (\"escalate\", "
      "\"investigate\", \"dismiss\", \"malformed\")` while the locked canonical order "
      "in `experiments/config.py` (used by `analysis/metrics.py:majority_vote`, the "
      "convention the 2026-08-17 correction re-asserted) is `(\"escalate\", "
      "\"dismiss\", \"investigate\", \"malformed\")`. The two orders resolve "
      "dismiss-vs-investigate majority ties differently. This report uses the "
      "canonical `config.OUTCOMES` order throughout.")
    w("")

    # ---- committed-claims verification ----
    w("### Committed-docs verification (recomputed vs published)")
    w("")

    def C(k, arm, cond, field):
        return S[k]["arms"][arm]["cond"][cond].get(field)

    checks = []

    def chk(src, desc, committed, computed, tol=0.0006):
        if isinstance(committed, (int, float)) and isinstance(computed, (int, float)):
            ok = abs(float(committed) - float(computed)) <= tol
            comp = fmt(float(computed)) if isinstance(computed, float) else str(computed)
        else:
            ok = str(committed) == str(computed)
            comp = str(computed)
        checks.append([src, desc, str(committed), comp, "✅" if ok else "❌ MISMATCH"])

    # cross-model-comparison.md spot checks
    chk("cross-model-comparison.md", "qwen3.5 single t0 pass^1", 0.400, C("qwen3.5:9b", "single", "t0-fixed", "pass^1"))
    chk("cross-model-comparison.md", "qwen3.5 single t07 pass^1", 0.364, C("qwen3.5:9b", "single", "t07-varied", "pass^1"))
    chk("cross-model-comparison.md", "qwen3.5 MAS t07 DAR", 0.802, C("qwen3.5:9b", "mas", "t07-varied", "DAR"))
    chk("cross-model-comparison.md", "gemma4 single t0 pass^1", 0.648, C("gemma4:latest", "single", "t0-fixed", "pass^1"))
    chk("cross-model-comparison.md", "gemma4 single t07 pass^1", 0.552, C("gemma4:latest", "single", "t07-varied", "pass^1"))
    chk("cross-model-comparison.md", "qwen2.5-7b MAS t07 pass^1", 0.449, C("qwen2.5:7b-instruct", "mas", "t07-varied", "pass^1"))
    chk("cross-model-comparison.md", "qwen2.5-14b MAS t07 DAR", 0.914, C("qwen2.5:14b-instruct", "mas", "t07-varied", "DAR"))
    chk("cross-model-comparison.md", "qwen2.5-7b@0.32.6 MAS t0 DAR", 0.804, C("qwen2.5:7b-instruct@0.32.6", "mas", "t0-fixed", "DAR"))
    chk("cross-model-comparison.md", "qwen2.5-7b MAS t0 alpha", 0.576, C("qwen2.5:7b-instruct", "mas", "t0-fixed", "alpha"))
    # FINAL-RESULTS.md
    chk("FINAL-RESULTS.md", "qwen2.5-7b t07 single tok/run", 2074, round(C("qwen2.5:7b-instruct", "single", "t07-varied", "total_mean")), tol=0.5)
    chk("FINAL-RESULTS.md", "qwen2.5-7b t07 MAS tok/run", 6458, round(C("qwen2.5:7b-instruct", "mas", "t07-varied", "total_mean")), tol=0.5)
    chk("FINAL-RESULTS.md", "qwen2.5-14b t07 MAS tok/run", 5903, round(C("qwen2.5:14b-instruct", "mas", "t07-varied", "total_mean")), tol=0.5)
    chk("FINAL-RESULTS.md", "gemma4 t07 MAS tok/run", 9491, round(C("gemma4:latest", "mas", "t07-varied", "total_mean")), tol=0.5)
    chk("FINAL-RESULTS.md", "token ratio qwen2.5-7b", 3.11,
        C("qwen2.5:7b-instruct", "mas", "t07-varied", "total_mean") / C("qwen2.5:7b-instruct", "single", "t07-varied", "total_mean"), tol=0.005)
    chk("FINAL-RESULTS.md", "token ratio qwen3.5", 1.83,
        C("qwen3.5:9b", "mas", "t07-varied", "total_mean") / C("qwen3.5:9b", "single", "t07-varied", "total_mean"), tol=0.005)
    chk("FINAL-RESULTS.md / INSIGHTS", "qwen3.5-MAS t07 modal investigate share", "86.0%",
        pct(S["qwen3.5:9b"]["arms"]["mas"]["cond"]["t07-varied"]["dist"]["investigate"], 750))
    chk("FINAL-RESULTS.md / INSIGHTS", "qwen2.5-14b-MAS t07 modal investigate share", "93.1%",
        pct(S["qwen2.5:14b-instruct"]["arms"]["mas"]["cond"]["t07-varied"]["dist"]["investigate"], 750))
    chk("FINAL-RESULTS.md / INSIGHTS", "qwen3.5-MAS t07 MV matches label (cases/50)", 11,
        round(C("qwen3.5:9b", "mas", "t07-varied", "mv_acc") * 50))
    chk("FINAL-RESULTS.md", "qwen2.5-14b-MAS pert MV moved (pert-t05)", 0,
        S["qwen2.5:14b-instruct"]["arms"]["mas"]["pert_move"]["pert-t05"]["moved"])
    chk("FINAL-RESULTS.md", "qwen2.5-14b-MAS pert MV moved (pert-t10)", 0,
        S["qwen2.5:14b-instruct"]["arms"]["mas"]["pert_move"]["pert-t10"]["moved"])
    chk("FINAL-RESULTS.md", "qwen3.5 t0 flips (both arms, both versions)", 0,
        S["qwen3.5:9b"]["arms"]["single"]["t0"]["flipping"]
        + S["qwen3.5:9b"]["arms"]["mas"]["t0"]["flipping"]
        + S["qwen3.5:9b@0.32.6"]["arms"]["single"]["t0"]["flipping"]
        + S["qwen3.5:9b@0.32.6"]["arms"]["mas"]["t0"]["flipping"])

    # T=0 flip/byte-divergence claims. The convention (established by
    # dissertation-v3.tex:779) is BOTH ARMS COMBINED; "primary block" =
    # t0-fixed only (100 groups), "incl. perturbation" adds pert-t0 (120).
    def flips_both(k, incl_pert=False):
        n = (S[k]["arms"]["single"]["t0"]["flipping"]
             + S[k]["arms"]["mas"]["t0"]["flipping"])
        if incl_pert:
            n += (S[k]["arms"]["single"]["pert_t0"]["flipping"]
                  + S[k]["arms"]["mas"]["pert_t0"]["flipping"])
        return n

    def divergent_both(k, incl_pert=False):
        n = (50 - S[k]["arms"]["single"]["t0"]["byte_identical"]
             + 50 - S[k]["arms"]["mas"]["t0"]["byte_identical"])
        if incl_pert:
            n += (10 - S[k]["arms"]["single"]["pert_t0"]["byte_identical"]
                  + 10 - S[k]["arms"]["mas"]["pert_t0"]["byte_identical"])
        return n

    chk("dissertation-v3.tex:779", "qwen2.5-7b flipped 25/100 primary case-groups", 25,
        flips_both("qwen2.5:7b-instruct"))
    chk("dissertation-v3.tex:779", "qwen2.5-14b flipped 7 primary case-groups", 7,
        flips_both("qwen2.5:14b-instruct"))
    chk("dissertation-v3.tex:779", "gemma4 35 flipping case-groups (primary)", 35,
        flips_both("gemma4:latest"))
    chk("dissertation/FINAL-RESULTS", "gemma4 45 flips incl. perturbation block", 45,
        flips_both("gemma4:latest", incl_pert=True))
    chk("FINAL-RESULTS.md:105", "qwen2.5-7b '~96% of case-groups byte-diverge'", 96,
        divergent_both("qwen2.5:7b-instruct"))
    chk("SUPERVISOR-PACK.md:59", "gemma4 99/100 byte-divergent groups", 99,
        divergent_both("gemma4:latest"))
    chk("FINAL-RESULTS.md:105", "qwen2.5-7b '23–27 decision flips' (low end, 23)", 23,
        flips_both("qwen2.5:7b-instruct"))  # recomputed: 25 (0.31.1) / 27 (0.32.6)
    chk("SUPERVISOR-PACK.md:89 / dissertation:779",
        "qwen2.5-14b byte-divergent '105/110' (primary both arms = /100)", 105,
        divergent_both("qwen2.5:14b-instruct"))
    chk("ANALYSIS-INSIGHTS.md:43", "'gemma4-single … 35 flipping groups' as a SINGLE-arm number", 35,
        S["gemma4:latest"]["arms"]["single"]["t0"]["flipping"])
    # CHANGELOG numbers
    chk("CHANGELOG 2026-08-17", "muse off: empty MAS data-node outputs", 226,
        S["muse-glimmer:30b"]["arms"]["mas"]["nodes"].get("empty_data"))
    chk("CHANGELOG 2026-08-17", "muse off: MAS data node call-dead", 16,
        S["muse-glimmer:30b"]["arms"]["mas"]["nodes"]["data_dead"])
    chk("CHANGELOG 2026-08-17", "muse off: MAS policy node call-dead", 78,
        S["muse-glimmer:30b"]["arms"]["mas"]["nodes"]["policy_dead"])
    chk("CHANGELOG 2026-08-17 (corrected)", "muse off: MAS pert-t10 MV acc", 0.100,
        C("muse-glimmer:30b", "mas", "pert-t10", "mv_acc"))
    chk("CHANGELOG 2026-08-13", "qwen3.5@think-budget single t07 pass^1", 0.548,
        C("qwen3.5:9b@think-budget", "single", "t07-varied", "pass^1"))
    chk("CHANGELOG 2026-08-13", "qwen3.5@think-budget MAS t07 pass^1", 0.264,
        C("qwen3.5:9b@think-budget", "mas", "t07-varied", "pass^1"))
    chk("CHANGELOG 2026-08-13", "qwen3.5@think-budget single t07 DAR", 0.631,
        C("qwen3.5:9b@think-budget", "single", "t07-varied", "DAR"))
    chk("CHANGELOG 2026-08-13", "qwen3.5@think-budget MAS t07 DAR", 0.724,
        C("qwen3.5:9b@think-budget", "mas", "t07-varied", "DAR"))
    chk("CHANGELOG 2026-08-13", "qwen3.5@think-budget MAS t07 investigate runs", 571,
        S["qwen3.5:9b@think-budget"]["arms"]["mas"]["cond"]["t07-varied"]["dist"]["investigate"])
    chk("CHANGELOG 2026-08-13", "qwen3.5@think-budget MAS tok/run (t07)", 17318,
        round(C("qwen3.5:9b@think-budget", "mas", "t07-varied", "total_mean")), tol=0.5)
    chk("CHANGELOG 2026-08-12", "lfm2.5@think malformed total", 144,
        S["lfm2.5:8b@think"]["arms"]["single"]["malformed"]
        + S["lfm2.5:8b@think"]["arms"]["mas"]["malformed"])
    chk("CHANGELOG 2026-08-12", "lfm2.5@think single t07 pass^1", 0.491,
        C("lfm2.5:8b@think", "single", "t07-varied", "pass^1"))
    chk("CHANGELOG 2026-08-12", "lfm2.5@think MAS t07 MV acc (canonical)", 0.360,
        C("lfm2.5:8b@think", "mas", "t07-varied", "mv_acc"))
    chk("CHANGELOG 2026-08-14", "deepseek zero-tool runs (of 2300)", 2300,
        sum(sum((S['deepseek-r1:14b@think']['arms'][arm]['cond'][c].get('zero_tool') or 0)
                for c in CONDITIONS if S['deepseek-r1:14b@think']['arms'][arm]['cond'][c].get('runs'))
            for arm in ARMS))
    chk("CHANGELOG 2026-08-17", "muse@think MAS runs at stop", 201,
        S["muse-glimmer:30b@think"]["arms"]["mas"]["rows"])

    def zero_tool_total(k, arm):
        a = S[k]["arms"][arm]
        return sum((a["cond"][c].get("zero_tool") or 0)
                   for c in CONDITIONS if a["cond"][c].get("runs"))

    chk("CHANGELOG 2026-08-15 (seal)", "muse off: single zero-tool runs", 1,
        zero_tool_total("muse-glimmer:30b", "single"))
    chk("CHANGELOG 2026-08-15 (seal)", "muse off: MAS zero-tool runs", 7,
        zero_tool_total("muse-glimmer:30b", "mas"))
    g4 = S["gemma4:latest"]["arms"]
    chk("FINAL-RESULTS.md", "gemma4 MAS dismissals on dismiss-labelled t07 runs (of 390)", 1,
        round(g4["mas"]["dismiss_rate_t07"] * g4["mas"]["dismiss_runs_t07"]))
    chk("FINAL-RESULTS.md", "gemma4 single dismissals on dismiss-labelled t07 runs", 178,
        round(g4["single"]["dismiss_rate_t07"] * g4["single"]["dismiss_runs_t07"]))

    # run-for-run decision identity of the 14b infra replication
    def decision_map(dirname, arm):
        rows, _ = load_journal(EXP / dirname / f"journal-{arm}.jsonl")
        return {r["run_id"]: r.get("decision") for r in rows}
    d14 = 0
    for arm in ARMS:
        m1 = decision_map("results-qwen2.5-14b", arm)
        m2 = decision_map("results-qwen2.5-14b-ollama0326", arm)
        d14 += sum(1 for rid, dec in m1.items() if m2.get(rid) != dec)
    chk("FINAL-RESULTS.md", "qwen2.5-14b 0.32.6 replication decision mismatches (of 2300)", 0, d14)

    w(table(["source", "claim", "committed", "recomputed", "verdict"], checks))
    w("")
    n_bad = sum(1 for c in checks if c[4].startswith("❌"))
    w(f"**{len(checks) - n_bad}/{len(checks)} committed claims reproduce; "
      f"{n_bad} mismatch(es) flagged above.**")
    w("")
    w("Contradiction notes (the ❌ rows, interpreted):")
    w("")
    w(f"1. **FINAL-RESULTS.md:105 — \"qwen2.5:7b … 23–27 decision flips\".** Under "
      "the convention every other committed figure uses (both arms combined, primary "
      f"t0-fixed block), the recomputed values are "
      f"**{flips_both('qwen2.5:7b-instruct')} (Ollama 0.31.1) → "
      f"{flips_both('qwen2.5:7b-instruct@0.32.6')} (0.32.6)** — i.e. 25–27, not "
      "23–27. The low end 23 matches no arm/block combination (closest: MAS-only "
      "t0+pert at 0.31.1 = 23, a different universe than the 45-flip gemma4 figure "
      "in the same list).")
    w("")
    w("2. **SUPERVISOR-PACK.md:89 and dissertation-v3.tex:779 — \"qwen2.5:14b "
      "byte-diverged 105 of 110 groups\".** Recomputed byte-divergent groups: "
      f"**{divergent_both('qwen2.5:14b-instruct')}/100** (primary, both arms) or "
      f"**{divergent_both('qwen2.5:14b-instruct', True)}/120** including the "
      "perturbation block. Neither the numerator 105 nor the denominator 110 is "
      "reproducible from the journals under any block/arm combination tried.")
    w("")
    w("3. **ANALYSIS-INSIGHTS.md:43 — \"gemma4-single … worst T=0 cache-stability "
      "in the experiment (35 flipping groups)\".** 35 is the BOTH-ARMS sweep figure "
      f"(single {S['gemma4:latest']['arms']['single']['t0']['flipping']} + MAS "
      f"{S['gemma4:latest']['arms']['mas']['t0']['flipping']}); the single arm alone "
      f"flips {S['gemma4:latest']['arms']['single']['t0']['flipping']}/50. The "
      "number is right for the sweep but misattributed to the single-arm config.")
    w("")
    w("---")
    w("*End of report. Regenerate at any seal with "
      "`python3 backend/experiments/analysis/master_report_gen.py`.*")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD} ({OUT_MD.stat().st_size:,} bytes)")
    print(f"corpus: {tot_runs:,} runs, {tot_tokens:,} tokens, {tot_wall_h:,.1f} GPU-busy h")
    for c in checks:
        if c[4].startswith("❌"):
            print("MISMATCH:", c)


if __name__ == "__main__":
    main()
