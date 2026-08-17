"""Adversarial empty-node probe 1: journal census (read-only).

Verifies, from the journals themselves:
- per-node empty-output rates in MAS journals (claimed numbers under attack);
- single-arm empty-output rates and whether every empty single output is
  scored `malformed` (C3);
- whether MAS runs with an empty node carry any `error` and what decision
  they produce (C3);
- muse-glimmer thinking-off t07-varied pass^1: single vs MAS intact/severed
  (C4), plus a "useless intact output" census (whitespace / refusal / tiny);
- downstream behaviour in empty-data runs: do policy_risk / reporting
  fabricate sanctions/profile evidence that no tool produced?
- correlations of empty-node with condition, temperature, repeat index,
  completion_tokens, and per-node-attributable tool calls.

Read-only; tolerates a torn final line in the live journal.
Run: cd backend && .venv/bin/python -m experiments.analysis.adv_emptynode_journal
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from experiments.config import EXPERIMENTS_DIR, MAS_TOOL_PARTITION
from experiments.harness.dfah_data import (
    ground_truth,
    load_perturbation_cases,
    load_primary_cases,
)

DIRS = {
    "granite4.1-8b": "results-granite4.1-8b",
    "deepseek-r1-14b@think": "results-deepseek-r1-14b-thinking",
    "lfm2.5-8b@think": "results-lfm2.5-8b-thinking",
    "muse-glimmer-30b (think off)": "results-muse-glimmer-30b",
    "muse-glimmer-30b @think": "results-muse-glimmer-30b-thinking",
    "qwen3.5-9b @think-budget": "results-qwen3.5-9b-thinking-budget",
}

NODES = ("orchestrator", "data", "policy_risk", "reporting")

DATA_TOOLS = set(MAS_TOOL_PARTITION["data"])
RISK_TOOLS = set(MAS_TOOL_PARTITION["policy_risk"])

REFUSAL_RE = re.compile(
    r"(cannot|can't|unable to|not able to|no (tools|access)|as an ai|i apologi)",
    re.IGNORECASE,
)
# Claims about data-tool evidence that only the data node's tools can ground.
FABRICATION_RE = re.compile(
    r"(no sanctions|not sanctioned|sanctions? (screening|check|list).{0,40}"
    r"(clear|negative|no match|not)|match score|customer profile|kyc status|"
    r"precedent(s)? (search|found)|risk level:)",
    re.IGNORECASE,
)


def load_journal(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # torn final line of a live journal — tolerate, count as partial
                break
    return rows


def is_empty(text: str | None) -> bool:
    return not (text or "").strip()


def labels() -> dict[str, str]:
    gt = ground_truth(load_primary_cases())
    gt.update(ground_truth(load_perturbation_cases()))
    return gt


def pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.1f}%" if d else "n/a"


def main() -> None:
    gt = labels()

    print("=" * 78)
    print("A. PER-NODE EMPTY RATES (MAS journals) — verify claimed numbers")
    print("=" * 78)
    for name, dirname in DIRS.items():
        rows = load_journal(EXPERIMENTS_DIR / dirname / "journal-mas.jsonl")
        if not rows:
            print(f"{name:34s}  NO MAS JOURNAL")
            continue
        n = len(rows)
        counts = {
            node: sum(is_empty((r.get("node_outputs") or {}).get(node)) for r in rows)
            for node in NODES
        }
        missing_no = sum(1 for r in rows if not r.get("node_outputs"))
        errs = sum(1 for r in rows if r.get("error"))
        rates = "/".join(pct(counts[nd], n) for nd in NODES)
        print(
            f"{name:34s} n={n:4d}  orch/data/risk/rep = {rates}"
            f"  (rows w/o node_outputs: {missing_no}, errors: {errs})"
        )

    print()
    print("=" * 78)
    print("B. SINGLE ARM: empty whole-output rate, and its fate (C3)")
    print("=" * 78)
    for name, dirname in DIRS.items():
        rows = load_journal(EXPERIMENTS_DIR / dirname / "journal-single.jsonl")
        if not rows:
            print(f"{name:34s}  NO SINGLE JOURNAL")
            continue
        n = len(rows)
        empty = [r for r in rows if is_empty(r.get("raw_output"))]
        fates = Counter(r.get("decision") for r in empty)
        nonmal = [r["run_id"] for r in empty if r.get("decision") != "malformed"]
        # also: malformed that are NOT empty (other malformation modes)
        mal_nonempty = sum(
            1 for r in rows
            if r.get("decision") == "malformed" and not is_empty(r.get("raw_output"))
        )
        live = " [LIVE/PARTIAL]" if "muse-glimmer-30b @think" in name else ""
        print(
            f"{name:34s} n={n:4d}  empty={len(empty)} ({pct(len(empty), n)})"
            f"  fates={dict(fates)}  non-malformed-empties={nonmal}"
            f"  malformed-but-nonempty={mal_nonempty}{live}"
        )

    print()
    print("=" * 78)
    print("C. MAS RUNS WITH AN EMPTY NODE: error field, decision, reporting fate (C3)")
    print("=" * 78)
    for name, dirname in DIRS.items():
        rows = load_journal(EXPERIMENTS_DIR / dirname / "journal-mas.jsonl")
        if not rows:
            continue
        affected = [
            r for r in rows
            if any(is_empty((r.get("node_outputs") or {}).get(nd)) for nd in NODES)
        ]
        if not affected:
            print(f"{name:34s}  no empty-node runs")
            continue
        errs = sum(1 for r in affected if r.get("error"))
        decs = Counter(r.get("decision") for r in affected)
        # empty node != reporting -> does the run still yield a parseable decision?
        nonrep = [
            r for r in affected
            if not is_empty((r.get("node_outputs") or {}).get("reporting"))
        ]
        nonrep_ok = Counter(r.get("decision") for r in nonrep)
        print(
            f"{name:34s} affected={len(affected)}  with-error={errs}"
            f"  decisions={dict(decs)}"
        )
        print(f"{'':34s}   of those w/ NON-empty reporting: {dict(nonrep_ok)}")

    print()
    print("=" * 78)
    print("D. EMPTY-DATA RUNS: what do downstream nodes do?")
    print("=" * 78)
    for name, dirname in DIRS.items():
        rows = load_journal(EXPERIMENTS_DIR / dirname / "journal-mas.jsonl")
        empty_data = [
            r for r in rows if is_empty((r.get("node_outputs") or {}).get("data"))
        ]
        if not empty_data:
            continue
        fab = refuse = flag = 0
        no_data_tools = 0
        for r in empty_data:
            calls = r.get("tool_calls") or []
            used_data_tools = any(c in DATA_TOOLS for c in calls)
            if not used_data_tools:
                no_data_tools += 1
            down = " ".join(
                (r.get("node_outputs") or {}).get(nd) or ""
                for nd in ("policy_risk", "reporting")
            )
            if REFUSAL_RE.search(down):
                refuse += 1
            if re.search(r"(no evidence|missing (evidence|data)|no data)", down, re.I):
                flag += 1
            if not used_data_tools and FABRICATION_RE.search(down):
                fab += 1
        print(
            f"{name:34s} empty-data={len(empty_data)}"
            f"  no-data-tool-calls-in-run={no_data_tools}"
            f"  downstream-cites-data-evidence-w/o-any-data-tool-call={fab}"
            f"  refusal-language={refuse}  flags-missing-data={flag}"
        )

    print()
    print("=" * 78)
    print("E. C4: muse-glimmer think-off t07-varied — single vs MAS intact/severed")
    print("=" * 78)
    for name, dirname in [
        ("muse-glimmer-30b (think off)", "results-muse-glimmer-30b"),
        ("granite4.1-8b", "results-granite4.1-8b"),
    ]:
        s_rows = [
            r for r in load_journal(EXPERIMENTS_DIR / dirname / "journal-single.jsonl")
            if r.get("condition") == "t07-varied"
        ]
        m_rows = [
            r for r in load_journal(EXPERIMENTS_DIR / dirname / "journal-mas.jsonl")
            if r.get("condition") == "t07-varied"
        ]
        def acc(rows: list[dict]) -> str:
            if not rows:
                return "n/a"
            ok = sum(1 for r in rows if r.get("decision") == gt.get(r["case_id"]))
            return f"{ok / len(rows):.3f} (n={len(rows)})"
        intact = [r for r in m_rows
                  if not is_empty((r.get("node_outputs") or {}).get("data"))]
        severed = [r for r in m_rows
                   if is_empty((r.get("node_outputs") or {}).get("data"))]
        print(f"{name}: single pass^1={acc(s_rows)}  MAS-all={acc(m_rows)}"
              f"  MAS-intact={acc(intact)}  MAS-severed={acc(severed)}")

    print()
    print("--- E2. 'useless intact' census: muse-glimmer think-off t07 intact data outputs")
    m_rows = [
        r for r in load_journal(
            EXPERIMENTS_DIR / "results-muse-glimmer-30b/journal-mas.jsonl")
        if r.get("condition") == "t07-varied"
        and not is_empty((r.get("node_outputs") or {}).get("data"))
    ]
    lens = sorted(len((r["node_outputs"]["data"]).strip()) for r in m_rows)
    tiny = [r for r in m_rows if len(r["node_outputs"]["data"].strip()) < 80]
    refusals = [r for r in m_rows if REFUSAL_RE.search(r["node_outputs"]["data"])]
    no_tool = [
        r for r in m_rows
        if not any(c in DATA_TOOLS for c in (r.get("tool_calls") or []))
    ]
    def q(p: float) -> int:
        return lens[int(p * (len(lens) - 1))] if lens else 0
    print(f"n_intact={len(m_rows)}  data-output len min/p10/p50/p90/max ="
          f" {q(0)}/{q(.1)}/{q(.5)}/{q(.9)}/{q(1)}")
    print(f"tiny(<80 chars)={len(tiny)}  refusal-language={len(refusals)}"
          f"  runs-with-zero-data-tool-calls={len(no_tool)}")
    for r in tiny[:5]:
        print(f"  tiny sample [{r['run_id']}]: {r['node_outputs']['data'][:120]!r}")
    for r in refusals[:3]:
        print(f"  refusal sample [{r['run_id']}]: {r['node_outputs']['data'][:160]!r}")

    print()
    print("=" * 78)
    print("F. CORRELATES OF EMPTY NODE (per model, per worst node)")
    print("=" * 78)
    for name, dirname in DIRS.items():
        rows = load_journal(EXPERIMENTS_DIR / dirname / "journal-mas.jsonl")
        if not rows:
            continue
        # pick worst node for this model
        counts = {
            nd: sum(is_empty((r.get("node_outputs") or {}).get(nd)) for r in rows)
            for nd in NODES
        }
        node = max(counts, key=counts.get)
        if counts[node] == 0:
            continue
        empt = [r for r in rows if is_empty((r.get("node_outputs") or {}).get(node))]
        rest = [r for r in rows if not is_empty((r.get("node_outputs") or {}).get(node))]
        def mean(rs, key):
            vals = [r.get(key) or 0 for r in rs]
            return sum(vals) / len(vals) if vals else 0.0
        by_cond_e = Counter(r["condition"] for r in empt)
        by_cond_n = Counter(r["condition"] for r in rows)
        cond_rates = {c: f"{100*by_cond_e.get(c,0)/n0:.0f}%"
                      for c, n0 in sorted(by_cond_n.items())}
        tools = DATA_TOOLS if node == "data" else (
            RISK_TOOLS if node == "policy_risk" else set())
        def toolmean(rs):
            return (sum(sum(1 for c in (r.get("tool_calls") or []) if c in tools)
                        for r in rs) / len(rs)) if rs else 0.0
        by_temp_e = Counter(r["temperature"] for r in empt)
        by_temp_n = Counter(r["temperature"] for r in rows)
        temp_rates = {t: f"{100*by_temp_e.get(t,0)/n0:.0f}%"
                      for t, n0 in sorted(by_temp_n.items())}
        print(f"{name} — worst node: {node} ({counts[node]}/{len(rows)})")
        print(f"   empty-rate by condition: {cond_rates}")
        print(f"   empty-rate by temperature: {temp_rates}")
        print(f"   mean completion_tokens: empty={mean(empt,'completion_tokens'):.0f}"
              f" vs rest={mean(rest,'completion_tokens'):.0f}")
        print(f"   mean agent_messages:    empty={mean(empt,'agent_messages'):.1f}"
              f" vs rest={mean(rest,'agent_messages'):.1f}")
        print(f"   mean {node}-tool calls/run: empty={toolmean(empt):.2f}"
              f" vs rest={toolmean(rest):.2f}")
        by_rep_e = Counter(r["repeat_idx"] for r in empt)
        print(f"   empty by repeat_idx: {dict(sorted(by_rep_e.items()))}")


if __name__ == "__main__":
    main()
