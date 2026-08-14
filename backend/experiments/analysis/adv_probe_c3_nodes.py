"""Adversarial probe 3 — node-death forensics (C3) + deepseek recount (C1/C4).

Read-only over journals. Attacks the claim that MAS policy_risk node death
(lfm2.5@think 470/1150, qwen3.5@think-budget 167/1150, muse-glimmer 37/529)
is model behaviour rather than harness truncation / starvation.

Discriminator: a policy_risk node starved by num_predict mid-deliberation
emits EMPTY content (the qwen3.5@think gate-failure signature); a node that
DECLINED emits a substantive risk assessment without calling the tool.
Also: completion-token distributions dead vs alive, ceiling clustering,
agent_messages, and an independent recount of deepseek attempted-tool syntax
with patterns written fresh (not copied from the census).

Run from backend/ with PYTHONPATH=.:
  ./.venv/bin/python experiments/analysis/adv_probe_c3_nodes.py
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path

EXP = Path("experiments")
POLICY_TOOL = "calculate_risk_score"
DATA_TOOLS = {"search_precedents", "get_customer_profile", "check_sanctions_list"}

SWEEPS = {
    "results-lfm2.5-8b-thinking": 2048,
    "results-qwen3.5-9b-thinking-budget": 8192,
    "results-muse-glimmer-30b": 2048,
}


def load(sweep: str, arm: str) -> list[dict]:
    rows = []
    p = EXP / sweep / f"journal-{arm}.jsonl"
    if not p.exists():
        return rows
    for line in p.open():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # torn tail (muse in-flight)
    return rows


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def dist(xs):
    if not xs:
        return {}
    return {"n": len(xs), "min": min(xs), "p25": pct(xs, .25),
            "med": statistics.median(xs), "p75": pct(xs, .75),
            "p95": pct(xs, .95), "max": max(xs),
            "mean": round(statistics.mean(xs), 1)}


NUM_SCORE_RE = re.compile(r"(?:risk|overall)[ _-]?score[^\n.]{0,50}?\d", re.I)

print("=" * 78)
for sweep, np_ in SWEEPS.items():
    rows = [r for r in load(sweep, "mas") if not r.get("error")]
    dead = [r for r in rows
            if POLICY_TOOL not in (r.get("tool_calls") or [])]
    alive = [r for r in rows if POLICY_TOOL in (r.get("tool_calls") or [])]
    print(f"\n### {sweep} (mas, num_predict={np_}) — rows={len(rows)} "
          f"policy-dead={len(dead)} alive={len(alive)}")
    # node_outputs emptiness among dead
    with_no = [r for r in dead if isinstance(r.get("node_outputs"), dict)]
    empty_pol = [r for r in with_no
                 if not (r["node_outputs"].get("policy_risk") or "").strip()]
    lens = [len((r["node_outputs"].get("policy_risk") or "")) for r in with_no]
    print(f"  dead runs with node_outputs: {len(with_no)}; "
          f"EMPTY policy_risk text: {len(empty_pol)}")
    print(f"  policy_risk text length in dead runs: {dist(lens)}")
    scored = [r for r in with_no
              if NUM_SCORE_RE.search(r["node_outputs"].get("policy_risk") or "")]
    print(f"  dead runs asserting a numeric risk score: {len(scored)}")
    # completion tokens dead vs alive
    print(f"  completion_tokens dead : {dist([r['completion_tokens'] for r in dead])}")
    print(f"  completion_tokens alive: {dist([r['completion_tokens'] for r in alive])}")
    # agent_messages: 4 == every node answered on its first call (no tool loops at all)
    print(f"  agent_messages dead : {dict(Counter(r['agent_messages'] for r in dead).most_common(6))}")
    print(f"  agent_messages alive: {dict(Counter(r['agent_messages'] for r in alive).most_common(6))}")
    # condition + determinism structure
    print(f"  dead by condition: {dict(Counter(r['condition'] for r in dead).most_common())}")
    t0 = [r for r in dead if r["condition"] in ("t0-fixed", "pert-t0")]
    per_case = Counter(r["case_id"] for r in t0)
    print(f"  dead at T=0: {len(t0)} over {len(per_case)} cases; "
          f"cases dead in ALL 5 repeats: "
          f"{sum(1 for c, n in per_case.items() if n == 5)}")
    # does the policy node attempt tool syntax in its text? (fresh patterns)
    attempt = [r for r in with_no if re.search(
        r"calculate_risk_score|\"factors\"\s*:|<tool|```json",
        r["node_outputs"].get("policy_risk") or "", re.I)]
    print(f"  dead runs whose policy text shows tool-attempt syntax: {len(attempt)}")

# ---- deepseek independent recount ------------------------------------------
print("\n" + "=" * 78)
FRESH_PATTERNS = {
    "fn_json": re.compile(
        r'"(?:name|tool|function|action)"\s*:\s*"?(?:search_precedents|'
        r'get_customer_profile|check_sanctions_list|calculate_risk_score)', re.I),
    "call_paren": re.compile(
        r"\b(?:search_precedents|get_customer_profile|check_sanctions_list|"
        r"calculate_risk_score)\s*\(", re.I),
    "tool_word_mention": re.compile(
        r"search_precedents|get_customer_profile|check_sanctions_list|"
        r"calculate_risk_score", re.I),
    "generic_want_tool": re.compile(
        r"(?:I (?:would|will|need to|should) (?:use|call|invoke|run) "
        r"(?:a |the )?tool|access to (?:a |the )?(?:tool|database|sanction))", re.I),
    "xml_call": re.compile(r"<(?:tool_call|function_call|invoke)\b", re.I),
}
for arm in ("single", "mas"):
    rows = load("results-deepseek-r1-14b-thinking", arm)
    hits = Counter()
    hit_runs = set()
    for r in rows:
        txt = (r.get("raw_output") or "")
        no = r.get("node_outputs")
        if isinstance(no, dict):
            txt += "\n" + "\n".join(v for v in no.values() if isinstance(v, str))
        for name, pat in FRESH_PATTERNS.items():
            if pat.search(txt):
                hits[name] += 1
                hit_runs.add(r["run_id"])
    ceiling = sum(1 for r in rows if r["completion_tokens"] >= 2048 - 8) if arm == "single" else None
    print(f"deepseek {arm}: runs={len(rows)} tool-syntax/mention hits={dict(hits)} "
          f"runs_any={len(hit_runs)}")
    # single-arm per-call ceiling check (single = 1 model call per run)
    if arm == "single":
        ct = [r["completion_tokens"] for r in rows]
        print(f"  single completion_tokens: {dist(ct)}; at ceiling(>=2040): {ceiling}")
    else:
        ct = [r["completion_tokens"] for r in rows]
        print(f"  mas completion_tokens: {dist(ct)}; "
              f">= 4x2040 (all-4-nodes-truncated signature): "
              f"{sum(1 for c in ct if c >= 4 * 2040)}")
        am = Counter(r["agent_messages"] for r in rows)
        print(f"  mas agent_messages: {dict(am.most_common())}")
