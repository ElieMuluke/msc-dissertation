"""Independent audit: ROUGE-L appendix recomputation + raw_output artefact demo.

Reproduces the committed ROUGE-L numbers from `raw_output`, then recomputes them
for the MAS arm over the FULL node trace, to quantify how much of the committed
MAS figure is an artefact of journaling only the reporting node's text.

Pure-Python, read-only, no LLM/GPU/network.
"""
import json
import os
from collections import defaultdict
from itertools import combinations

RES = "/home/eliem/Projects/ai/msc-dissertation/backend/experiments/results-granite4.1-8b"
NODE_ORDER = ("orchestrator", "data", "policy_risk", "reporting")


def lcs(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(cur[j], prev[j + 1]))
        prev = cur
    return prev[-1]


def rouge_l_f1(a, b):
    ta, tb = a.lower().split(), b.lower().split()
    if not ta or not tb:
        return 0.0
    l = lcs(ta, tb)
    if l == 0:
        return 0.0
    p, r = l / len(tb), l / len(ta)
    return 2 * p * r / (p + r)


def load():
    rows = []
    for f in ("journal-single.jsonl", "journal-mas.jsonl"):
        with open(os.path.join(RES, f), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def full_trace(r):
    if r["arm"] == "single" or not r.get("node_outputs"):
        return r["raw_output"] or ""
    no = r["node_outputs"]
    return "\n".join(str(no.get(k) or "") for k in NODE_ORDER)


def mean_pairwise(g, getter):
    vals = []
    for cid, rs in g.items():
        pairs = list(combinations(rs, 2))
        if not pairs:
            continue
        vals.append(sum(rouge_l_f1(getter(a), getter(b)) for a, b in pairs) / len(pairs))
    return sum(vals) / len(vals) if vals else None


def main():
    rows = load()
    conds = ["t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10"]
    print(f"{'arm':7s} {'condition':11s} {'ROUGE-L(raw_output)':>20s} {'ROUGE-L(full trace)':>20s} {'delta':>8s}")
    print("-" * 72)
    for arm in ("single", "mas"):
        for c in conds:
            g = defaultdict(list)
            for r in rows:
                if r["arm"] == arm and r["condition"] == c:
                    g[r["case_id"]].append(r)
            a = mean_pairwise(g, lambda r: r["raw_output"] or "")
            b = mean_pairwise(g, full_trace)
            print(f"{arm:7s} {c:11s} {a:20.3f} {b:20.3f} {b-a:8.3f}")

    print("\nMAS raw_output = node_outputs['reporting'] verbatim; the other three")
    print("nodes' text (~1000 completion tokens/run) is excluded from the committed")
    print("ROUGE-L appendix figure for this model.")

    # how many distinct reporting-node strings exist at all?
    from collections import Counter
    rep = Counter((r["node_outputs"] or {}).get("reporting", "")
                  for r in rows if r["arm"] == "mas")
    print(f"\nDistinct MAS reporting-node strings across 1150 runs: {len(rep)}")
    for s, n in rep.most_common(6):
        print(f"  {n:5d}  {s[:70]!r}")


if __name__ == "__main__":
    main()
