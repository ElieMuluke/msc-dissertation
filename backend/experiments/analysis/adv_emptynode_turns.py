"""Adversarial empty-node probe 2: turn accounting from journals (read-only).

Discriminates the two candidate mechanisms for an empty node output, using
only journalled aggregates:

- CAP-HIT: the node looped tool calls until max_iterations=8; the final
  permitted AIMessage was a tool-call message; the loop ended returning that
  message's (empty) text. Signature: ~8 node-attributed tool calls.
- EMPTY-ANSWER-TURN: the node's final turn had NO tool calls and empty
  content (thinking-channel / budget exhaustion). Signature: ~0 node tool
  calls (or few), and for thinking models high completion_tokens.

Tool attribution is exact because MAS_TOOL_PARTITION is disjoint:
data = {search_precedents, get_customer_profile, check_sanctions_list},
policy_risk = {calculate_risk_score}; orchestrator/reporting have no tools.

Also recomputes per-node empty rates EXCLUDING error rows (to check the
claimed 0/0.5/8.3/0.7 qwen numbers) and node-empty co-occurrence.

Run: cd backend && .venv/bin/python -m experiments.analysis.adv_emptynode_turns
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from experiments.config import EXPERIMENTS_DIR, MAS_TOOL_PARTITION

DIRS = {
    "lfm2.5-8b@think": "results-lfm2.5-8b-thinking",
    "muse-glimmer-30b (think off)": "results-muse-glimmer-30b",
    "muse-glimmer-30b @think": "results-muse-glimmer-30b-thinking",
    "qwen3.5-9b @think-budget": "results-qwen3.5-9b-thinking-budget",
}
NODES = ("orchestrator", "data", "policy_risk", "reporting")
NODE_TOOLS = {n: set(ts) for n, ts in MAS_TOOL_PARTITION.items()}


def load(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                break
    return rows


def is_empty(t: str | None) -> bool:
    return not (t or "").strip()


def node_tool_count(row: dict, node: str) -> int:
    return sum(1 for c in (row.get("tool_calls") or []) if c in NODE_TOOLS[node])


def main() -> None:
    for name, dirname in DIRS.items():
        rows = load(EXPERIMENTS_DIR / dirname / "journal-mas.jsonl")
        ok = [r for r in rows if not r.get("error") and r.get("node_outputs")]
        errs = len(rows) - len(ok)
        print("=" * 78)
        print(f"{name}  n={len(rows)}  (error/no-node_outputs rows excluded: {errs})")
        rates = "/".join(
            f"{100*sum(is_empty(r['node_outputs'].get(nd)) for r in ok)/len(ok):.1f}%"
            for nd in NODES
        )
        print(f"  empty rates excl. errors (orch/data/risk/rep): {rates}")
        # co-occurrence of empty nodes within a run
        combos = Counter(
            tuple(nd for nd in NODES if is_empty(r["node_outputs"].get(nd)))
            for r in ok
        )
        combos.pop((), None)
        if combos:
            print(f"  empty-node combos: {dict(combos)}")
        for node in ("data", "policy_risk"):
            empt = [r for r in ok if is_empty(r["node_outputs"].get(node))]
            rest = [r for r in ok if not is_empty(r["node_outputs"].get(node))]
            if not empt:
                continue
            dist_e = Counter(node_tool_count(r, node) for r in empt)
            dist_r = Counter(node_tool_count(r, node) for r in rest)
            cap8 = sum(v for k, v in dist_e.items() if k >= 8)
            zero = dist_e.get(0, 0)
            print(f"  [{node}] empty runs: {len(empt)}")
            print(f"     node-tool-call dist (empty): {dict(sorted(dist_e.items()))}")
            print(f"     -> >=8 calls (cap-hit signature): {cap8}/{len(empt)}"
                  f"   0 calls (empty-answer-turn signature): {zero}/{len(empt)}")
            print(f"     node-tool-call dist (non-empty), top:"
                  f" {dict(sorted(dist_r.items()))}")
            # non-empty runs that ALSO hit >=8 (cap-hit but still produced text?)
            cap_ne = [r for r in rest if node_tool_count(r, node) >= 8]
            print(f"     non-empty runs with >=8 {node}-tool calls: {len(cap_ne)}")
            for r in cap_ne[:3]:
                head = r["node_outputs"][node].strip().replace("\n", " ")[:110]
                print(f"       e.g. [{r['run_id']}] {head!r}")
            toks_e = sum(r.get("completion_tokens") or 0 for r in empt) / len(empt)
            toks_r = (sum(r.get("completion_tokens") or 0 for r in rest) / len(rest)
                      if rest else 0)
            print(f"     mean run completion_tokens: empty={toks_e:.0f}"
                  f" rest={toks_r:.0f}")


if __name__ == "__main__":
    main()
