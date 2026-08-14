"""Tool-call-channel census across every sweep with journals (12 dirs).

Read-only over journal JSONL files. No LLM calls, no GPU, no ollama CLI.
Tolerates torn last lines (muse-glimmer is in-flight; its numbers are
partial). Writes a JSON summary to the scratchpad path given on argv[1]
(default: ./toolchannel_census.json).

Run from backend/:
    ./.venv/bin/python experiments/analysis/eval_toolchannel_census.py [out.json]
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXP = Path("experiments")

SWEEPS = [
    "results",
    "results-deepseek-r1-14b-thinking",
    "results-gemma4",
    "results-granite4.1-8b",
    "results-lfm2.5-8b-thinking",
    "results-muse-glimmer-30b",
    "results-qwen2.5-14b",
    "results-qwen2.5-14b-ollama0326",
    "results-qwen2.5-7b",
    "results-qwen2.5-7b-ollama0326",
    "results-qwen3.5-9b-ollama0326",
    "results-qwen3.5-9b-thinking-budget",
]

TOOLSET = {
    "search_precedents",
    "get_customer_profile",
    "check_sanctions_list",
    "calculate_risk_score",
}
# MAS_TOOL_PARTITION (experiments/config.py): data node owns the three
# lookup tools, policy_risk owns calculate_risk_score, orchestrator and
# reporting own none — so tool NAME identifies the calling NODE exactly.
DATA_TOOLS = {"search_precedents", "get_customer_profile", "check_sanctions_list"}
POLICY_TOOLS = {"calculate_risk_score"}

CONDITIONS = ("t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10")

# --- attempted-but-unparsed tool-call syntax (the deepseek-audit hunt) ------
TOOL_NAME_RE = "|".join(sorted(TOOLSET))
PATTERNS = {
    "json_name_field": re.compile(
        r'[{,]\s*"(?:name|tool|function|tool_name)"\s*:\s*"(?:%s)"' % TOOL_NAME_RE
    ),
    "code_fence_call": re.compile(
        r"```(?:json|python|tool_code|tool)?[^`]{0,400}?(?:%s)" % TOOL_NAME_RE, re.S
    ),
    "xmlish_tool_tag": re.compile(
        r"<(?:tool_call|tool|function_call|invoke|functioncall|\|tool_call\|)\b", re.I
    ),
    "bare_call_syntax": re.compile(r"\b(?:%s)\s*\(" % TOOL_NAME_RE),
    "special_token_call": re.compile(
        r"<\|(?:tool_call|tool_calls_begin|tool_call_begin|python_tag)\|>", re.I
    ),
}

REFUSAL_RE = re.compile(
    r"\b(?:I (?:cannot|can't|am unable|won't)|as an AI|I'm sorry|cannot assist|"
    r"unable to (?:comply|help|assist|access))\b",
    re.I,
)

# --- fabrication screen: tool-derived facts asserted without any tool call --
FAB_PATTERNS = {
    "sanctions_result": re.compile(
        r"(?:not? (?:a )?(?:on|listed|found|match(?:ed)?).{0,40}sanction|"
        r"sanction[^.\n]{0,60}(?:no match|not listed|clear(?:ed)?|negative|"
        r"match score|hit|0\.0)|cleared sanctions)",
        re.I,
    ),
    "risk_score_number": re.compile(
        r"risk[ _-]?score[^.\n]{0,40}?\d+(?:\.\d+)?", re.I
    ),
    "customer_history": re.compile(
        r"(?:KYC[^.\n]{0,40}(?:complete|incomplete|verified)|"
        r"relationship[^.\n]{0,30}(?:years?|\d)|"
        r"(?:\d+|five|three|ten)[ -]years?[^.\n]{0,30}(?:relationship|customer|history)|"
        r"transaction history[^.\n]{0,50}(?:regular|consistent|prior|no prior))",
        re.I,
    ),
    "precedent_case_id": re.compile(r"CASE-\d{4}-\d{3,5}", re.I),
}


def load_jsonl(p: Path) -> tuple[list[dict], int]:
    rows, torn = [], 0
    if not p.exists():
        return rows, torn
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                torn += 1
    return rows, torn


def tool_names(tc) -> list[str]:
    names = []
    for t in tc or []:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict):
            names.append(t.get("name") or t.get("tool") or json.dumps(t, sort_keys=True))
        else:
            names.append(str(t))
    return names


def texts_of(r) -> str:
    """All free text of a run: raw_output + node_outputs values."""
    parts = [r.get("raw_output") or ""]
    no = r.get("node_outputs")
    if isinstance(no, dict):
        parts += [v for v in no.values() if isinstance(v, str)]
    return "\n".join(parts)


def dist(xs: list[int]) -> dict:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "min": min(xs),
        "median": statistics.median(xs),
        "mean": round(statistics.mean(xs), 2),
        "max": max(xs),
    }


def classify_zero(r) -> str:
    """Why did this run make zero tool calls?"""
    if r.get("error"):
        return "error:" + (r["error"].split(":")[0])
    raw = (r.get("raw_output") or "").strip()
    if not raw:
        return "empty_raw_output"
    np_ = r.get("num_predict") or 2048
    if (r.get("completion_tokens") or 0) >= np_ - 8:
        return "truncation_at_num_predict"
    txt = texts_of(r)
    for pname, pat in PATTERNS.items():
        if pat.search(txt):
            return f"attempted_unparsed:{pname}"
    if REFUSAL_RE.search(raw):
        return "refusal"
    if r.get("decision") in ("escalate", "dismiss", "investigate"):
        return "early_final_answer"
    return "no_decision_no_attempt"


out: dict = {}

for sweep in SWEEPS:
    res = EXP / sweep
    sweep_out: dict = {}
    for arm in ("single", "mas"):
        rows, torn = load_jsonl(res / f"journal-{arm}.jsonl")
        if not rows:
            continue
        a: dict = {
            "n_runs": len(rows),
            "torn_lines": torn,
            "model": Counter(r.get("model") for r in rows).most_common(1)[0][0],
            "ollama_version": dict(Counter(r.get("ollama_version") for r in rows)),
            "think": dict(Counter(str(r.get("think")) for r in rows)),
            "num_predict": dict(Counter(r.get("num_predict", "pre-v2(2048)") for r in rows)),
        }
        # ---- per-condition tool stats
        by_cond: dict = {}
        for cond in CONDITIONS:
            sub = [r for r in rows if r["condition"] == cond]
            if not sub:
                continue
            counts = [len(tool_names(r.get("tool_calls"))) for r in sub]
            names = Counter(n for r in sub for n in tool_names(r.get("tool_calls")))
            by_cond[cond] = {
                "runs": len(sub),
                "zero_tool_runs": sum(1 for c in counts if c == 0),
                "calls_per_run": dist(counts),
                "tool_name_counts": dict(names),
                "unexpected_tool_names": sorted(set(names) - TOOLSET),
                "missing_tool_names": sorted(TOOLSET - set(names)),
            }
        a["by_condition"] = by_cond
        counts_all = [len(tool_names(r.get("tool_calls"))) for r in rows]
        a["zero_tool_runs"] = sum(1 for c in counts_all if c == 0)
        a["calls_per_run"] = dist(counts_all)
        a["tool_name_counts"] = dict(
            Counter(n for r in rows for n in tool_names(r.get("tool_calls")))
        )
        a["unexpected_tool_names"] = sorted(set(a["tool_name_counts"]) - TOOLSET)

        # ---- zero-tool classification
        zeros = [r for r in rows if not tool_names(r.get("tool_calls"))]
        a["zero_classification"] = dict(
            Counter(classify_zero(r) for r in zeros).most_common()
        )
        a["zero_by_condition"] = dict(
            Counter(r["condition"] for r in zeros).most_common()
        )
        a["zero_by_case"] = dict(Counter(r["case_id"] for r in zeros).most_common())
        a["zero_by_cond_case"] = dict(
            Counter(f"{r['condition']}|{r['case_id']}" for r in zeros).most_common(15)
        )
        a["zero_examples"] = [
            {
                "run_id": r["run_id"],
                "class": classify_zero(r),
                "completion_tokens": r.get("completion_tokens"),
                "decision": r.get("decision"),
                "error": r.get("error"),
                "raw_head": (r.get("raw_output") or "")[:220],
            }
            for r in zeros[:6]
        ]

        # ---- attempted-unparsed syntax anywhere (incl. runs WITH tool calls:
        #      partial channel loss — model emitted extra unparsed attempts)
        attempted = Counter()
        attempted_runs = 0
        for r in rows:
            txt = texts_of(r)
            hit = False
            for pname, pat in PATTERNS.items():
                m = pat.search(txt)
                if m:
                    attempted[pname] += 1
                    hit = True
            if hit:
                attempted_runs += 1
        a["attempted_syntax_runs_any"] = attempted_runs
        a["attempted_syntax_by_pattern"] = dict(attempted)

        # ---- fabrication screen on zero-tool runs
        fab = {"screened": len(zeros), "asserting_runs": 0, "by_kind": Counter()}
        fab_examples = []
        for r in zeros:
            txt = texts_of(r)
            kinds = [k for k, pat in FAB_PATTERNS.items() if pat.search(txt)]
            if kinds:
                fab["asserting_runs"] += 1
                fab["by_kind"].update(kinds)
                if len(fab_examples) < 4:
                    fab_examples.append(
                        {"run_id": r["run_id"], "kinds": kinds,
                         "head": (r.get("raw_output") or "")[:200]}
                    )
        fab["by_kind"] = dict(fab["by_kind"])
        fab["examples"] = fab_examples
        a["fabrication_zero_tool"] = fab

        # ---- MAS node-level (tool name -> node, exact by partition)
        if arm == "mas":
            node = {}
            for cond in CONDITIONS:
                sub = [r for r in rows if r["condition"] == cond]
                if not sub:
                    continue
                data_c = [
                    sum(1 for n in tool_names(r.get("tool_calls")) if n in DATA_TOOLS)
                    for r in sub
                ]
                pol_c = [
                    sum(1 for n in tool_names(r.get("tool_calls")) if n in POLICY_TOOLS)
                    for r in sub
                ]
                node[cond] = {
                    "runs": len(sub),
                    "data_node_zero": sum(1 for c in data_c if c == 0),
                    "policy_node_zero": sum(1 for c in pol_c if c == 0),
                    "data_calls_per_run": dist(data_c),
                    "policy_calls_per_run": dist(pol_c),
                }
            # runs where arm total >0 but one node is silently dead
            silent_data = [
                r for r in rows
                if tool_names(r.get("tool_calls"))
                and not any(n in DATA_TOOLS for n in tool_names(r.get("tool_calls")))
            ]
            silent_pol = [
                r for r in rows
                if tool_names(r.get("tool_calls"))
                and not any(n in POLICY_TOOLS for n in tool_names(r.get("tool_calls")))
            ]
            node["silent_dead"] = {
                "data_node_dead_but_run_has_tools": len(silent_data),
                "policy_node_dead_but_run_has_tools": len(silent_pol),
                "policy_dead_by_condition": dict(
                    Counter(r["condition"] for r in silent_pol).most_common()
                ),
                "policy_dead_by_case": dict(
                    Counter(r["case_id"] for r in silent_pol).most_common(12)
                ),
                "data_dead_by_condition": dict(
                    Counter(r["condition"] for r in silent_data).most_common()
                ),
                "data_dead_examples": [
                    {"run_id": r["run_id"], "tools": tool_names(r.get("tool_calls"))}
                    for r in silent_data[:5]
                ],
            }
            # node_outputs presence check (harness v2 journals only)
            with_no = [r for r in rows if isinstance(r.get("node_outputs"), dict)]
            if with_no:
                empt = Counter()
                for r in with_no:
                    for k, v in r["node_outputs"].items():
                        if not (isinstance(v, str) and v.strip()):
                            empt[k] += 1
                node["node_outputs"] = {
                    "runs_with_node_outputs": len(with_no),
                    "empty_node_output_counts": dict(empt),
                    "node_keys": dict(
                        Counter(k for r in with_no for k in r["node_outputs"])
                    ),
                }
            a["node_level"] = node

        sweep_out[arm] = a
    out[sweep] = sweep_out

# ---- cross-version pairs ---------------------------------------------------
def arm_fingerprint(sweep, arm):
    s = out.get(sweep, {}).get(arm)
    if not s:
        return None
    return {
        "n": s["n_runs"],
        "zero": s["zero_tool_runs"],
        "mean_calls": s["calls_per_run"].get("mean"),
        "median_calls": s["calls_per_run"].get("median"),
        "names": s["tool_name_counts"],
        "ollama": s["ollama_version"],
    }


out["_cross_version"] = {
    "qwen2.5-7b": {
        "0.31.1": {a: arm_fingerprint("results-qwen2.5-7b", a) for a in ("single", "mas")},
        "0.32.6": {a: arm_fingerprint("results-qwen2.5-7b-ollama0326", a) for a in ("single", "mas")},
    },
    "qwen2.5-14b": {
        "0.31.1": {a: arm_fingerprint("results-qwen2.5-14b", a) for a in ("single", "mas")},
        "0.32.6": {a: arm_fingerprint("results-qwen2.5-14b-ollama0326", a) for a in ("single", "mas")},
    },
    "qwen3.5-9b": {
        "pilot(results)": {a: arm_fingerprint("results", a) for a in ("single", "mas")},
        "0.32.6": {a: arm_fingerprint("results-qwen3.5-9b-ollama0326", a) for a in ("single", "mas")},
        "thinking-budget": {a: arm_fingerprint("results-qwen3.5-9b-thinking-budget", a) for a in ("single", "mas")},
    },
}

dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("toolchannel_census.json")
dest.write_text(json.dumps(out, indent=1, default=str))
print(f"written {dest}")
