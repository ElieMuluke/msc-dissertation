"""Tool-channel deep dives following eval_toolchannel_census.py.

1. qwen2.5-14b 0.31.1 vs 0.32.6: are the journals genuinely distinct runs
   (fields differ) or byte-identical outputs (reproducibility vs copy)?
2. Node-level fabrication: MAS runs whose policy_risk node made zero
   calculate_risk_score calls — does its node_output assert a numeric risk
   score anyway? Same for data-node-dead runs asserting evidence.
3. Hallucinated/typo tool names: where and how often.
4. Error texts for zero-tool error runs.
5. Case concentration of zero-tool and node-dead pockets.
6. qwen2.5-7b MAS looping (>50 calls/run) by version and condition.

Read-only. Run from backend/:
    ./.venv/bin/python experiments/analysis/eval_toolchannel_deepdive.py [out.json]
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXP = Path("experiments")
DATA_TOOLS = {"search_precedents", "get_customer_profile", "check_sanctions_list"}
TOOLSET = DATA_TOOLS | {"calculate_risk_score"}


def load(sweep, arm):
    rows = []
    p = EXP / sweep / f"journal-{arm}.jsonl"
    if not p.exists():
        return rows
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


out: dict = {}

# --- 1. qwen2.5 14b (and 7b) cross-version identity ------------------------
for size in ("14b", "7b"):
    cmp: dict = {}
    for arm in ("single", "mas"):
        a = {r["run_id"]: r for r in load(f"results-qwen2.5-{size}", arm)}
        b = {r["run_id"]: r for r in load(f"results-qwen2.5-{size}-ollama0326", arm)}
        shared = sorted(set(a) & set(b))
        same_raw = sum(1 for k in shared if a[k]["raw_output"] == b[k]["raw_output"])
        same_tools = sum(1 for k in shared if a[k]["tool_calls"] == b[k]["tool_calls"])
        same_started = sum(1 for k in shared if a[k]["started_at"] == b[k]["started_at"])
        cmp[arm] = {
            "shared_run_ids": len(shared),
            "identical_raw_output": same_raw,
            "identical_tool_call_seq": same_tools,
            "identical_started_at_timestamp": same_started,
            "ollama_version_a": dict(Counter(r["ollama_version"] for r in a.values())),
            "ollama_version_b": dict(Counter(r["ollama_version"] for r in b.values())),
            "digest_a": dict(Counter(r["model_digest"][:12] for r in a.values())),
            "digest_b": dict(Counter(r["model_digest"][:12] for r in b.values())),
            "wall_clock_median_a": statistics.median(r["wall_clock_s"] for r in a.values()),
            "wall_clock_median_b": statistics.median(r["wall_clock_s"] for r in b.values()),
        }
        # example divergent run (if any)
        div = [k for k in shared if a[k]["raw_output"] != b[k]["raw_output"]]
        cmp[arm]["n_divergent_raw"] = len(div)
        cmp[arm]["divergent_by_condition"] = dict(
            Counter(a[k]["condition"] for k in div).most_common()
        )
    out[f"qwen2.5-{size}_version_identity"] = cmp

# --- 2. node-level fabrication in node-dead MAS runs ------------------------
RISK_NUM_RE = re.compile(r"risk[ _-]?score[^.\n]{0,60}?(\d+(?:\.\d+)?)", re.I)
EVIDENCE_RE = re.compile(
    r"(?:not? (?:on|listed|found).{0,40}sanction|sanction[^.\n]{0,60}(?:no match|"
    r"not listed|clear|0\.0|match score)|KYC[^.\n]{0,40}(?:complete|incomplete)|"
    r"relationship[^.\n]{0,30}years?|CASE-\d{4}-\d{3,5})",
    re.I,
)

node_fab = {}
for sweep in (
    "results-lfm2.5-8b-thinking",
    "results-qwen3.5-9b-thinking-budget",
    "results-muse-glimmer-30b",
    "results",
    "results-qwen3.5-9b-ollama0326",
    "results-gemma4",
    "results-qwen2.5-14b",
    "results-granite4.1-8b",
):
    rows = load(sweep, "mas")
    pol_dead = [
        r for r in rows
        if "calculate_risk_score" not in (r.get("tool_calls") or [])
    ]
    data_dead = [
        r for r in rows
        if not any(t in DATA_TOOLS for t in (r.get("tool_calls") or []))
    ]
    def node_txt(r, key):
        no = r.get("node_outputs")
        if isinstance(no, dict):
            v = no.get(key)
            return v if isinstance(v, str) else ""
        return ""
    have_no = any(isinstance(r.get("node_outputs"), dict) for r in rows)
    pf = {
        "policy_dead_runs": len(pol_dead),
        "data_dead_runs": len(data_dead),
        "has_node_outputs": have_no,
    }
    if have_no:
        pol_fab = [
            r for r in pol_dead
            if RISK_NUM_RE.search(node_txt(r, "policy_risk") or r.get("raw_output") or "")
        ]
        data_fab = [
            r for r in data_dead
            if EVIDENCE_RE.search(node_txt(r, "data"))
        ]
        pf["policy_dead_asserting_numeric_risk_score"] = len(pol_fab)
        pf["policy_dead_by_case_top"] = dict(
            Counter(r["case_id"] for r in pol_dead).most_common(8)
        )
        pf["data_dead_asserting_evidence"] = len(data_fab)
        pf["data_dead_by_case_top"] = dict(
            Counter(r["case_id"] for r in data_dead).most_common(8)
        )
        pf["examples_policy_fab"] = [
            {
                "run_id": r["run_id"],
                "policy_head": (node_txt(r, "policy_risk") or "")[:260],
            }
            for r in pol_fab[:3]
        ]
        pf["examples_data_fab"] = [
            {"run_id": r["run_id"], "data_head": node_txt(r, "data")[:260]}
            for r in data_fab[:3]
        ]
    else:
        # journals without node_outputs: screen raw_output for a numeric score
        pf["policy_dead_asserting_numeric_risk_score_rawonly"] = sum(
            1 for r in pol_dead if RISK_NUM_RE.search(r.get("raw_output") or "")
        )
        pf["policy_dead_by_case_top"] = dict(
            Counter(r["case_id"] for r in pol_dead).most_common(8)
        )
    node_fab[sweep] = pf
out["node_fabrication"] = node_fab

# --- 3. hallucinated / typo tool names --------------------------------------
hall = {}
for sweep in (
    "results-lfm2.5-8b-thinking",
    "results-qwen3.5-9b-thinking-budget",
):
    for arm in ("single", "mas"):
        rows = load(sweep, arm)
        bad = Counter()
        bad_runs = []
        for r in rows:
            u = [t for t in (r.get("tool_calls") or []) if t not in TOOLSET]
            if u:
                bad.update(u)
                bad_runs.append(r["run_id"])
        if bad:
            hall[f"{sweep}|{arm}"] = {
                "names": dict(bad),
                "n_runs": len(bad_runs),
                "example_runs": bad_runs[:5],
                "by_condition": dict(
                    Counter(
                        r["condition"] for r in rows
                        if any(t not in TOOLSET for t in (r.get("tool_calls") or []))
                    )
                ),
            }
out["hallucinated_tool_names"] = hall

# --- 4. error texts on zero-tool error runs ---------------------------------
errs = {}
for sweep in ("results-qwen3.5-9b-thinking-budget", "results-muse-glimmer-30b"):
    for arm in ("single", "mas"):
        rows = load(sweep, arm)
        e = [r for r in rows if r.get("error") and not (r.get("tool_calls") or [])]
        if e:
            errs[f"{sweep}|{arm}"] = {
                "n": len(e),
                "error_values": dict(Counter(r["error"][:140] for r in e).most_common(5)),
                "by_condition": dict(Counter(r["condition"] for r in e)),
                "by_case": dict(Counter(r["case_id"] for r in e).most_common(8)),
            }
out["zero_tool_errors"] = errs

# --- 5. case concentration of zero-tool pockets -----------------------------
conc = {}
for sweep, arm in (
    ("results-lfm2.5-8b-thinking", "single"),
    ("results-lfm2.5-8b-thinking", "mas"),
    ("results-qwen3.5-9b-thinking-budget", "mas"),
    ("results-gemma4", "single"),
    ("results", "mas"),
    ("results-qwen3.5-9b-ollama0326", "mas"),
):
    rows = load(sweep, arm)
    zeros = [r for r in rows if not (r.get("tool_calls") or [])]
    conc[f"{sweep}|{arm}"] = {
        "n_zero": len(zeros),
        "distinct_cases": len({r["case_id"] for r in zeros}),
        "by_case": dict(Counter(r["case_id"] for r in zeros).most_common()),
        "by_condition": dict(Counter(r["condition"] for r in zeros).most_common()),
        "decisions": dict(Counter(str(r.get("decision")) for r in zeros)),
    }
out["zero_tool_case_concentration"] = conc

# --- 6. qwen2.5-7b MAS looping ----------------------------------------------
loops = {}
for sweep in ("results-qwen2.5-7b", "results-qwen2.5-7b-ollama0326",
              "results-qwen2.5-14b", "results-qwen2.5-14b-ollama0326"):
    rows = load(sweep, "mas")
    big = [r for r in rows if len(r.get("tool_calls") or []) > 50]
    loops[sweep] = {
        "runs_gt50_calls": len(big),
        "max_calls": max(len(r.get("tool_calls") or []) for r in rows),
        "by_condition": dict(Counter(r["condition"] for r in big).most_common()),
        "by_case": dict(Counter(r["case_id"] for r in big).most_common(6)),
        "top_runs": sorted(
            (
                {"run_id": r["run_id"], "n_calls": len(r["tool_calls"]),
                 "dominant_tool": Counter(r["tool_calls"]).most_common(1)[0]}
                for r in big
            ),
            key=lambda x: -x["n_calls"],
        )[:5],
    }
out["mas_tool_looping"] = loops

dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("toolchannel_deepdive.json")
dest.write_text(json.dumps(out, indent=1, default=str))
print(f"written {dest}")
