"""Independent audit: metric recomputation for results-granite4.1-8b.

Pure-Python, JSONL only. No LLM calls, no GPU, no network. Read-only.
All estimators re-implemented from definitions; nothing imported from the
project's own analysis package (blindness protocol).
"""
import json
import math
import os
import random
from collections import Counter, defaultdict
from itertools import combinations

RES = "/home/el/projects/msc-dissertation/backend/experiments/results-granite4.1-8b"
LABELS = "/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json"
PERT = "/home/el/projects/msc-dissertation/backend/experiments/perturbation_cases.json"
VALID = ("escalate", "dismiss", "investigate")
random.seed(20260814)

# ---------------------------------------------------------------- loading
def load():
    rows = []
    for f in ("journal-single.jsonl", "journal-mas.jsonl"):
        with open(os.path.join(RES, f), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


LAB = {a["alert_id"]: a["ground_truth"] for a in json.load(open(LABELS))["alerts"]}
LAB.update({a["alert_id"]: a["ground_truth"] for a in json.load(open(PERT))["alerts"]})
PERT_META = {a["alert_id"]: a for a in json.load(open(PERT))["alerts"]}

# ---------------------------------------------------------------- estimators
def comb(n, k):
    return math.comb(n, k) if 0 <= k <= n else 0


def pass_hat_k(correct, n, k):
    """Unbiased P(all of k draws w/o replacement are correct)."""
    if k > n:
        return None
    return comb(correct, k) / comb(n, k)


def pairwise_agreement(vals):
    n = len(vals)
    if n < 2:
        return None
    c = Counter(vals)
    return sum(comb(v, 2) for v in c.values()) / comb(n, 2)


def norm_entropy(vals, base_k=3):
    n = len(vals)
    if n == 0:
        return None
    c = Counter(vals)
    h = -sum((v / n) * math.log(v / n) for v in c.values() if v)
    return h / math.log(base_k)


def krippendorff_nominal(units):
    """units: list of lists of nominal values (one list per unit/case)."""
    units = [u for u in units if len(u) >= 2]
    if not units:
        return None
    o = defaultdict(float)
    ncount = Counter()
    for u in units:
        m = len(u)
        c = Counter(u)
        for a in c:
            for b in c:
                if a == b:
                    pairs = c[a] * (c[a] - 1)
                else:
                    pairs = c[a] * c[b]
                o[(a, b)] += pairs / (m - 1)
        ncount.update(u)
    n = sum(ncount.values())
    Do = sum(v for (a, b), v in o.items() if a != b)
    De = sum(ncount[a] * ncount[b] for a in ncount for b in ncount if a != b) / (n - 1)
    if De == 0:
        return None  # no between-unit variation: alpha undefined (degenerate)
    return 1 - Do / De


def lcs_len(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(cur[j], prev[j + 1]))
        prev = cur
    return prev[-1]


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def majority(vals):
    c = Counter(vals)
    top = max(c.values())
    winners = sorted(k for k, v in c.items() if v == top)
    return winners[0], len(winners) > 1


# ---------------------------------------------------------------- grouping
def group(rows, arm, cond):
    g = defaultdict(list)
    for r in rows:
        if r["arm"] == arm and r["condition"] == cond:
            g[r["case_id"]].append(r)
    for k in g:
        g[k].sort(key=lambda r: r["repeat_idx"])
    return g


def cell_metrics(g):
    """g: case_id -> list of run records. Returns dict of metrics + per-case."""
    per = {}
    for cid, rs in g.items():
        dec = [r["decision"] for r in rs]
        lab = LAB.get(cid)
        n = len(dec)
        corr = sum(1 for d in dec if d == lab)
        mv, tie = majority(dec)
        seqs = [tuple(r.get("tool_calls") or []) for r in rs]
        pairs = list(combinations(range(n), 2))
        exact = (sum(1 for i, j in pairs if seqs[i] == seqs[j]) / len(pairs)) if pairs else None
        jac = (sum(jaccard(seqs[i], seqs[j]) for i, j in pairs) / len(pairs)) if pairs else None
        nlcs = None
        if pairs:
            tot = 0.0
            for i, j in pairs:
                m = max(len(seqs[i]), len(seqs[j]))
                tot += 1.0 if m == 0 else lcs_len(seqs[i], seqs[j]) / m
            nlcs = tot / len(pairs)
        per[cid] = {
            "n": n, "dec": dec, "label": lab, "correct": corr,
            "acc_mean": corr / n,
            "p1": pass_hat_k(corr, n, 1),
            "p5": pass_hat_k(corr, n, 5),
            "p15": pass_hat_k(corr, n, 15),
            "dar": pairwise_agreement(dec),
            "flip": 1.0 if len(set(dec)) > 1 else 0.0,
            "nent": norm_entropy(dec),
            "mv": mv, "mv_tie": tie, "mv_correct": 1.0 if (mv == lab and not tie) else 0.0,
            "mv_correct_tielenient": 1.0 if mv == lab else 0.0,
            "traj_exact": exact, "traj_jaccard": jac, "traj_nlcs": nlcs,
            "ctok": sum(r["completion_tokens"] for r in rs) / n,
            "ptok": sum(r["prompt_tokens"] for r in rs) / n,
            "wall": sum(r["wall_clock_s"] for r in rs) / n,
            "ncalls": sum(len(r.get("tool_calls") or []) for r in rs) / n,
        }
    return per


def agg(per, field):
    vals = [v[field] for v in per.values() if v.get(field) is not None]
    return (sum(vals) / len(vals)) if vals else None


def fmt(x, nd=4):
    return "n/a" if x is None else f"{x:.{nd}f}"


# ---------------------------------------------------------------- stats
def boot_ci(pairs, B=10000, alpha=0.05):
    """pairs: list of (mas_val, single_val) per case. Returns diff mean + CI."""
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if not pairs:
        return None
    n = len(pairs)
    obs = sum(a - b for a, b in pairs) / n
    ds = []
    for _ in range(B):
        s = [pairs[random.randrange(n)] for _ in range(n)]
        ds.append(sum(a - b for a, b in s) / n)
    ds.sort()
    return obs, ds[int(alpha / 2 * B)], ds[int((1 - alpha / 2) * B)]


def perm_test(pairs, B=10000):
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if not pairs:
        return None
    n = len(pairs)
    obs = sum(a - b for a, b in pairs) / n
    hits = 0
    for _ in range(B):
        s = sum((a - b) if random.random() < 0.5 else (b - a) for a, b in pairs) / n
        if abs(s) >= abs(obs) - 1e-15:
            hits += 1
    return obs, (hits + 1) / (B + 1)


# ---------------------------------------------------------------- main
def main():
    rows = load()
    out = []
    P = out.append

    conds = ["t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10"]
    cells = {(arm, c): cell_metrics(group(rows, arm, c))
             for arm in ("single", "mas") for c in conds}

    P("=" * 100)
    P("2. INDEPENDENTLY RECOMPUTED METRICS  (granite4.1:8b, 2300 runs)")
    P("=" * 100)

    hdr = (f"{'arm':7s} {'condition':11s} {'cases':5s} {'n':3s} "
           f"{'pass^1':>7s} {'pass^5':>7s} {'pass^15':>7s} {'DAR':>7s} {'alpha':>8s} "
           f"{'flip':>6s} {'MV-acc':>7s} {'nEnt':>6s}")
    P("\n[2.1] Reliability / accuracy")
    P(hdr)
    P("-" * len(hdr))
    for arm in ("single", "mas"):
        for c in conds:
            per = cells[(arm, c)]
            if not per:
                continue
            k = krippendorff_nominal([v["dec"] for v in per.values()])
            n = list(per.values())[0]["n"]
            P(f"{arm:7s} {c:11s} {len(per):5d} {n:3d} "
              f"{fmt(agg(per,'p1')):>7s} {fmt(agg(per,'p5')):>7s} {fmt(agg(per,'p15')):>7s} "
              f"{fmt(agg(per,'dar')):>7s} {(fmt(k) if k is not None else 'UNDEF'):>8s} "
              f"{fmt(agg(per,'flip'),3):>6s} {fmt(agg(per,'mv_correct'),3):>7s} "
              f"{fmt(agg(per,'nent'),3):>6s}")

    P("\n  (alpha = Krippendorff nominal, units=cases, observations=repeats;")
    P("   UNDEF => zero between-case variation in decisions => degenerate, alpha undefined)")
    P("  MV-acc = majority-vote accuracy, ties counted WRONG. Tie-lenient variant:")
    for arm in ("single", "mas"):
        for c in conds:
            per = cells[(arm, c)]
            if per:
                ties = sum(1 for v in per.values() if v["mv_tie"])
                P(f"    {arm:7s} {c:11s} ties={ties:2d} MV-acc(lenient)={fmt(agg(per,'mv_correct_tielenient'),3)}")

    # ------------------------------------------------------ trajectory
    P("\n[2.2] Trajectory metrics over tool-call name sequences (within-case, pairwise)")
    h2 = f"{'arm':7s} {'condition':11s} {'exact-order':>12s} {'Jaccard':>9s} {'nLCS':>8s} {'mean|calls|':>11s}"
    P(h2)
    P("-" * len(h2))
    for arm in ("single", "mas"):
        for c in conds:
            per = cells[(arm, c)]
            if per:
                P(f"{arm:7s} {c:11s} {fmt(agg(per,'traj_exact')):>12s} "
                  f"{fmt(agg(per,'traj_jaccard')):>9s} {fmt(agg(per,'traj_nlcs')):>8s} "
                  f"{fmt(agg(per,'ncalls'),2):>11s}")

    # distinct tool sequences observed
    P("\n  Distinct tool-call sequences observed per arm (whole sweep):")
    for arm in ("single", "mas"):
        seqs = Counter(tuple(r.get("tool_calls") or []) for r in rows if r["arm"] == arm)
        P(f"    {arm}: {len(seqs)} distinct; top 5:")
        for s, n in seqs.most_common(5):
            P(f"      {n:5d}  {list(s)}")

    # ------------------------------------------------------ cost
    P("\n[2.3] Tokens and wall-clock per arm (per run)")
    h3 = (f"{'arm':7s} {'condition':11s} {'prompt_tok':>11s} {'compl_tok':>10s} "
          f"{'total_tok':>10s} {'wall_s':>8s}")
    P(h3)
    P("-" * len(h3))
    for arm in ("single", "mas"):
        for c in conds:
            per = cells[(arm, c)]
            if per:
                pt, ct, w = agg(per, "ptok"), agg(per, "ctok"), agg(per, "wall")
                P(f"{arm:7s} {c:11s} {pt:11.1f} {ct:10.1f} {pt+ct:10.1f} {w:8.2f}")
    P("")
    for arm in ("single", "mas"):
        sub = [r for r in rows if r["arm"] == arm]
        P(f"  {arm}: TOTAL prompt={sum(r['prompt_tokens'] for r in sub):,} "
          f"completion={sum(r['completion_tokens'] for r in sub):,} "
          f"grand={sum(r['prompt_tokens']+r['completion_tokens'] for r in sub):,} "
          f"wall={sum(r['wall_clock_s'] for r in sub)/3600:.2f} h "
          f"mean_wall={sum(r['wall_clock_s'] for r in sub)/len(sub):.2f} s")
    s_tot = sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows if r["arm"] == "single")
    m_tot = sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows if r["arm"] == "mas")
    P(f"  MAS/single token ratio = {m_tot/s_tot:.2f}x ; "
      f"wall ratio = {sum(r['wall_clock_s'] for r in rows if r['arm']=='mas')/sum(r['wall_clock_s'] for r in rows if r['arm']=='single'):.2f}x")

    # ------------------------------------------------------ tokens / pass^k
    P("\n[2.4] Cost of reliability: mean total tokens per run divided by pass^k")
    P("      (t07-varied, primary block; INF => pass^k = 0, no finite token price)")
    h4 = f"{'arm':7s} {'k':>3s} {'pass^k':>8s} {'tok/run':>9s} {'tok/pass^k':>12s}"
    P(h4)
    P("-" * len(h4))
    for arm in ("single", "mas"):
        per = cells[(arm, "t07-varied")]
        tok = agg(per, "ptok") + agg(per, "ctok")
        for k, f in ((1, "p1"), (5, "p5"), (15, "p15")):
            pk = agg(per, f)
            val = "INF" if not pk else f"{tok/pk:,.0f}"
            P(f"{arm:7s} {k:3d} {fmt(pk):>8s} {tok:9.1f} {val:>12s}")
    P("\n      same, t0-fixed (k=1,5 only):")
    for arm in ("single", "mas"):
        per = cells[(arm, "t0-fixed")]
        tok = agg(per, "ptok") + agg(per, "ctok")
        for k, f in ((1, "p1"), (5, "p5")):
            pk = agg(per, f)
            val = "INF" if not pk else f"{tok/pk:,.0f}"
            P(f"{arm:7s} {k:3d} {fmt(pk):>8s} {tok:9.1f} {val:>12s}")

    # ------------------------------------------------------ arm difference stats
    P("\n[2.5] Arm difference (MAS - single), paired over cases")
    P("      bootstrap 10,000 resamples over cases; paired permutation 10,000 relabelings")
    h5 = f"{'condition':11s} {'metric':16s} {'diff':>9s} {'CI95 low':>10s} {'CI95 high':>10s} {'perm p':>9s}"
    P(h5)
    P("-" * len(h5))
    for c in ["t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10"]:
        ps, pm = cells[("single", c)], cells[("mas", c)]
        cases = sorted(set(ps) & set(pm))
        for metric, label in (("p1", "pass^1"), ("dar", "DAR"), ("flip", "flip-rate"),
                              ("nent", "norm-entropy"), ("mv_correct", "MV-accuracy"),
                              ("acc_mean", "mean-accuracy"), ("traj_exact", "traj-exact")):
            pairs = [(pm[cid][metric], ps[cid][metric]) for cid in cases]
            b = boot_ci(pairs)
            t = perm_test(pairs)
            if b and t:
                P(f"{c:11s} {label:16s} {b[0]:9.4f} {b[1]:10.4f} {b[2]:10.4f} {t[1]:9.4f}")
        P("")

    # ------------------------------------------------------ T=0 determinism
    P("\n" + "=" * 100)
    P("3. T=0 FIXED-SEED BEHAVIOUR (seed=42, temperature=0)")
    P("=" * 100)
    for c in ("t0-fixed", "pert-t0"):
        P(f"\n[3.x] condition={c}")
        for arm in ("single", "mas"):
            g = group(rows, arm, c)
            byte_id = dec_id = 0
            flippers = []
            tool_id = 0
            tok_id = 0
            for cid, rs in sorted(g.items()):
                raws = [r["raw_output"] for r in rs]
                decs = [r["decision"] for r in rs]
                tools = [tuple(r.get("tool_calls") or []) for r in rs]
                toks = [r["completion_tokens"] for r in rs]
                if len(set(raws)) == 1:
                    byte_id += 1
                if len(set(decs)) == 1:
                    dec_id += 1
                else:
                    flippers.append((cid, dict(Counter(decs))))
                if len(set(tools)) == 1:
                    tool_id += 1
                if len(set(toks)) == 1:
                    tok_id += 1
            n = len(g)
            P(f"  {arm:7s} n_cases={n:3d} | byte-identical {byte_id}/{n} ({byte_id/n:.1%})"
              f" | decision-identical {dec_id}/{n} ({dec_id/n:.1%})"
              f" | tool-seq-identical {tool_id}/{n} | completion_tokens-identical {tok_id}/{n}")
            if flippers:
                P(f"    decision-flipping cases ({len(flippers)}):")
                for cid, d in flippers:
                    P(f"      {cid}: {d}")
        # ollama version split check
        vs = set(r["ollama_version"] for r in rows if r["condition"] == c)
        P(f"  ollama_version(s) present in this condition: {vs} -> single-version, no per-version split needed")

    # byte-divergence detail: where does it first differ?
    P("\n  Byte-level divergence detail for t0-fixed (first differing character index):")
    for arm in ("single", "mas"):
        g = group(rows, arm, "t0-fixed")
        diffs = []
        for cid, rs in sorted(g.items()):
            raws = [r["raw_output"] for r in rs]
            if len(set(raws)) == 1:
                continue
            base = raws[0]
            firsts = []
            for other in raws[1:]:
                if other == base:
                    continue
                i = 0
                while i < min(len(base), len(other)) and base[i] == other[i]:
                    i += 1
                firsts.append(i)
            diffs.append((cid, min(firsts), len(base)))
        P(f"    {arm}: {len(diffs)} non-identical case-groups; "
          f"median first-divergence index = "
          f"{sorted(d[1] for d in diffs)[len(diffs)//2] if diffs else 'n/a'}; "
          f"earliest = {min((d[1] for d in diffs), default='n/a')}")
        for d in sorted(diffs, key=lambda x: x[1])[:5]:
            P(f"      {d[0]}: diverges at char {d[1]} of {d[2]}")

    # ------------------------------------------------------ degeneracy
    P("\n" + "=" * 100)
    P("4. DEGENERACY CHECK")
    P("=" * 100)
    P("\n[4.1] Raw decision distribution vs label distribution")
    for blk, cases in (("primary", [c for c in LAB if c.startswith("TXN")]),
                       ("perturbation", [c for c in LAB if c.startswith("PERT")])):
        labd = Counter(LAB[c] for c in cases)
        tot = sum(labd.values())
        P(f"\n  {blk} labels (n={tot} cases): "
          + ", ".join(f"{k}={labd[k]} ({labd[k]/tot:.1%})" for k in VALID))
        for arm in ("single", "mas"):
            sub = [r for r in rows if r["arm"] == arm and
                   (r["block"] == blk)]
            d = Counter(r["decision"] for r in sub)
            n = len(sub)
            P(f"    {arm:7s} runs n={n:5d}: "
              + ", ".join(f"{k}={d[k]} ({d[k]/n:.1%})" for k in VALID))
    P("\n[4.2] Per-condition decision distribution")
    for arm in ("single", "mas"):
        for c in conds:
            sub = [r for r in rows if r["arm"] == arm and r["condition"] == c]
            d = Counter(r["decision"] for r in sub)
            n = len(sub)
            P(f"  {arm:7s} {c:11s} n={n:4d}: "
              + ", ".join(f"{k}={d[k]/n:6.1%}" for k in VALID))

    P("\n[4.3] Baselines: accuracy of constant predictors vs observed majority-vote accuracy")
    prim = [c for c in LAB if c.startswith("TXN")]
    labd = Counter(LAB[c] for c in prim)
    for v in VALID:
        P(f"  constant-'{v}' baseline accuracy on primary block = {labd[v]/len(prim):.3f}")
    for arm in ("single", "mas"):
        for c in ("t0-fixed", "t07-varied"):
            per = cells[(arm, c)]
            P(f"  observed {arm:7s} {c:11s} MV-acc={fmt(agg(per,'mv_correct'),3)} "
              f"mean-acc={fmt(agg(per,'acc_mean'),3)}")

    P("\n[4.4] How many distinct majority-vote decisions does each arm produce across the 50 primary cases?")
    for arm in ("single", "mas"):
        for c in ("t0-fixed", "t07-varied"):
            per = cells[(arm, c)]
            mvd = Counter(v["mv"] for v in per.values())
            P(f"  {arm:7s} {c:11s} MV distribution over 50 cases: {dict(mvd)}")

    P("\n[4.5] Per-label recall (t07-varied, majority vote) - is any class ever predicted?")
    for arm in ("single", "mas"):
        per = cells[(arm, "t07-varied")]
        P(f"  {arm}:")
        for v in VALID:
            cs = [cid for cid in per if per[cid]["label"] == v and cid.startswith("TXN")]
            hit = sum(1 for cid in cs if per[cid]["mv"] == v)
            P(f"    label={v:12s} n={len(cs):2d} MV-correct={hit:2d} recall={hit/len(cs) if cs else 0:.3f}")

    P("\n[4.6] Perturbation responsiveness: does the model change its answer when the")
    P("      decision-relevant input is edited? (base case vs its perturbed variant, T=0)")
    for arm in ("single", "mas"):
        pb = group(rows, arm, "t0-fixed")
        pp = group(rows, arm, "pert-t0")
        moved = same = 0
        detail = []
        for pid, meta in sorted(PERT_META.items()):
            base = meta["base_alert_id"]
            if base not in pb or pid not in pp:
                continue
            bmv = majority([r["decision"] for r in pb[base]])[0]
            pmv = majority([r["decision"] for r in pp[pid]])[0]
            hit = pmv == LAB[pid]
            if bmv != pmv:
                moved += 1
            else:
                same += 1
            detail.append((pid, base, meta["flip"], bmv, pmv, LAB[pid], hit))
        P(f"  {arm}: MV changed on {moved}/{moved+same} perturbations; "
          f"MV matched the perturbed label on {sum(1 for d in detail if d[6])}/{len(detail)}")
        for d in detail:
            P(f"    {d[0]} (from {d[1]}) intended {d[2]:26s} | base_MV={d[3]:11s} "
              f"pert_MV={d[4]:11s} target={d[5]:11s} {'HIT' if d[6] else 'miss'}")

    print("\n".join(out))


if __name__ == "__main__":
    main()
