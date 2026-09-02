"""Independent metric recomputation for results-muse-glimmer-30b (SECTIONS 3-6).

Blind recomputation: manifest + journals + labels only. Own implementations of
pass^k, DAR, Krippendorff alpha (nominal), entropy, LCS, bootstrap, permutation.

Run from backend/:  .venv/bin/python experiments/analysis/eval_museglimmer_metrics.py
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

RES = Path("experiments/results-muse-glimmer-30b")
ALERTS = Path(
    "/home/eliem/Projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json"
)
PERT = Path("experiments/perturbation_cases.json")
ARMS = ["single", "mas"]
CONDS = ["t0-fixed", "t07-varied", "pert-t0", "pert-t05", "pert-t10"]
OUTCOMES = ["escalate", "dismiss", "investigate", "malformed"]
ENT_NORM = math.log2(len(OUTCOMES))

DATA_TOOLS = {"check_sanctions_list", "get_customer_profile", "search_precedents"}
POLICY_TOOLS = {"calculate_risk_score"}

RNG_SEED = 20260817
B_BOOT = 10000
N_PERM = 20000


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n-- {t}")


# ------------------------------------------------------------------ helpers


def tool_names(tc):
    """tool_calls entries may be str OR dict."""
    out = []
    for t in tc or []:
        if isinstance(t, str):
            out.append(t)
        elif isinstance(t, dict):
            n = t.get("name") or t.get("tool") or t.get("function")
            if isinstance(n, dict):
                n = n.get("name")
            out.append(str(n) if n is not None else "<unnamed>")
        else:
            out.append(f"<{type(t).__name__}>")
    return out


def comb(n, k):
    return math.comb(n, k) if 0 <= k <= n else 0


def pass_at_k(per_case, k):
    """per_case = [(n_repeats, n_correct)] -> mean over cases of C(c,k)/C(n,k)."""
    vals = []
    for n, c in per_case:
        if k > n:
            return None
        vals.append(comb(c, k) / comb(n, k))
    return sum(vals) / len(vals) if vals else None


def dar(labels):
    """Decision agreement rate = fraction of agreeing unordered pairs."""
    if len(labels) < 2:
        return 1.0
    prs = list(combinations(labels, 2))
    return sum(a == b for a, b in prs) / len(prs)


def krippendorff_alpha_nominal(units):
    units = [u for u in units if len(u) >= 2]
    if not units:
        return float("nan")
    n_total = sum(len(u) for u in units)
    glob = Counter()
    do = 0.0
    for u in units:
        m = len(u)
        cnt = Counter(u)
        glob.update(cnt)
        cross = m * m - sum(v * v for v in cnt.values())
        do += cross / (m - 1)
    do /= n_total
    cross_g = n_total * n_total - sum(v * v for v in glob.values())
    de = cross_g / (n_total * (n_total - 1))
    if de == 0:
        return float("nan")
    return 1.0 - do / de


def norm_entropy(labels):
    n = len(labels)
    if n == 0:
        return 0.0
    cnt = Counter(labels)
    h = -sum((v / n) * math.log2(v / n) for v in cnt.values() if v)
    return h / ENT_NORM


def majority(labels):
    """Modal label; deterministic tie-break by fixed OUTCOMES order."""
    cnt = Counter(labels)
    top = max(cnt.values())
    winners = [o for o in OUTCOMES if cnt.get(o, 0) == top]
    return winners[0], len(winners) > 1


def lcs_len(a, b):
    if not a or not b:
        return 0
    if len(a) > len(b):
        a, b = b, a
    prev = [0] * (len(a) + 1)
    for y in b:
        cur = [0] * (len(a) + 1)
        for i, x in enumerate(a, 1):
            cur[i] = prev[i - 1] + 1 if x == y else max(prev[i], cur[i - 1])
        prev = cur
    return prev[-1]


def nlcs(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return lcs_len(a, b) / max(len(a), len(b))


def jaccard(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


# ------------------------------------------------------------------- load

manifest = json.load(open(RES / "manifest.json", encoding="utf-8"))
J = {
    a: [json.loads(l) for l in open(RES / f"journal-{a}.jsonl", encoding="utf-8") if l.strip()]
    for a in ARMS
}
alerts = json.load(open(ALERTS, encoding="utf-8"))["alerts"]
perts = json.load(open(PERT, encoding="utf-8"))["alerts"]
LABEL = {a["alert_id"]: a["ground_truth"] for a in alerts}
LABEL.update({p["alert_id"]: p["ground_truth"] for p in perts})
PRIMARY = [a["alert_id"] for a in alerts]
PERT_IDS = [p["alert_id"] for p in perts]
COND_BLOCK = {c["name"]: c["block"] for c in manifest["config"]["conditions"]}
COND_REPEATS = {c["name"]: c["repeats"] for c in manifest["config"]["conditions"]}

# group: (arm, cond, case) -> [records sorted by repeat_idx]
G = defaultdict(list)
for a in ARMS:
    for r in J[a]:
        G[(a, r["condition"], r["case_id"])].append(r)
for k in G:
    G[k].sort(key=lambda r: r["repeat_idx"])


def cases_for(cond):
    return PRIMARY if COND_BLOCK[cond] == "primary" else PERT_IDS


# ============================================================= SECTION 3
hdr("SECTION 3 - RECOMPUTED METRICS")

MET = {}
for a in ARMS:
    for c in CONDS:
        cs = cases_for(c)
        per_case_pk, dars, ents, alph_units, flips, maj_hits, maj_ties = [], [], [], [], [], [], []
        decs_all = []
        for cid in cs:
            recs = G[(a, c, cid)]
            d = [r["decision"] for r in recs]
            decs_all.extend(d)
            gt = LABEL[cid]
            per_case_pk.append((len(d), sum(x == gt for x in d)))
            dars.append(dar(d))
            ents.append(norm_entropy(d))
            alph_units.append(d)
            flips.append(len(set(d)) > 1)
            mv, tie = majority(d)
            maj_hits.append(mv == gt)
            maj_ties.append(tie)
        n_rep = COND_REPEATS[c]
        MET[(a, c)] = {
            "n_cases": len(cs),
            "n_repeats": n_rep,
            "pass^1": pass_at_k(per_case_pk, 1),
            "pass^5": pass_at_k(per_case_pk, 5),
            "pass^15": pass_at_k(per_case_pk, 15),
            "DAR": mean(dars),
            "alpha": krippendorff_alpha_nominal(alph_units),
            "flip_rate": sum(flips) / len(flips),
            "maj_acc": sum(maj_hits) / len(maj_hits),
            "maj_ties": sum(maj_ties),
            "entropy": mean(ents),
            "dist": Counter(decs_all),
            "n_runs": len(decs_all),
        }

sub("3.1 headline metric table (per arm x condition)")
print(f"{'arm':<7}{'condition':<12}{'n':>5}{'rep':>4}{'pass^1':>8}{'pass^5':>8}"
      f"{'pass^15':>9}{'DAR':>8}{'alpha':>8}{'flip':>7}{'majacc':>8}{'ent':>7}")
for a in ARMS:
    for c in CONDS:
        m = MET[(a, c)]
        p15 = f"{m['pass^15']:.4f}" if m["pass^15"] is not None else "  n/a"
        print(f"{a:<7}{c:<12}{m['n_cases']:>5}{m['n_repeats']:>4}"
              f"{m['pass^1']:>8.4f}{m['pass^5']:>8.4f}{p15:>9}"
              f"{m['DAR']:>8.4f}{m['alpha']:>8.4f}{m['flip_rate']:>7.3f}"
              f"{m['maj_acc']:>8.4f}{m['entropy']:>7.3f}")

sub("3.2 pooled per-arm (primary block = t0-fixed + t07-varied; all conditions)")
for a in ARMS:
    for scope, conds in [("primary", ["t0-fixed", "t07-varied"]),
                         ("perturbation", ["pert-t0", "pert-t05", "pert-t10"]),
                         ("all", CONDS)]:
        units, hits, tot = [], 0, 0
        for c in conds:
            for cid in cases_for(c):
                d = [r["decision"] for r in G[(a, c, cid)]]
                units.append(d)
                hits += sum(x == LABEL[cid] for x in d)
                tot += len(d)
        print(f"  {a:<7}{scope:<14} runs={tot:>5} acc(pass^1)={hits / tot:.4f} "
              f"alpha={krippendorff_alpha_nominal(units):.4f} "
              f"DAR={mean([dar(u) for u in units]):.4f} "
              f"flip={sum(len(set(u)) > 1 for u in units) / len(units):.3f}")

sub("3.3 tokens and wall-clock per arm")
TOK = {}
for a in ARMS:
    pt = [r["prompt_tokens"] for r in J[a]]
    ct = [r["completion_tokens"] for r in J[a]]
    w = [r["wall_clock_s"] for r in J[a]]
    TOK[a] = {
        "prompt_mean": mean(pt), "compl_mean": mean(ct),
        "total_mean": mean([x + y for x, y in zip(pt, ct)]),
        "prompt_sum": sum(pt), "compl_sum": sum(ct), "total_sum": sum(pt) + sum(ct),
        "wall_mean": mean(w), "wall_sum": sum(w), "wall_median": statistics.median(w),
    }
    t = TOK[a]
    print(f"  {a:<7} prompt_mean={t['prompt_mean']:>9.1f} compl_mean={t['compl_mean']:>8.1f} "
          f"total_mean={t['total_mean']:>9.1f} total_sum={t['total_sum']:>10,} "
          f"wall_mean={t['wall_mean']:>7.2f}s wall_sum={t['wall_sum'] / 3600:>6.2f}h")
print(f"  ratio mas/single: tokens={TOK['mas']['total_mean'] / TOK['single']['total_mean']:.3f}x "
      f"wall={TOK['mas']['wall_mean'] / TOK['single']['wall_mean']:.3f}x")

sub("3.4 tokens per unit of pass^k  (mean total tokens per run / pass^k), primary block")
for a in ARMS:
    tm = TOK[a]["total_mean"]
    for c in ["t0-fixed", "t07-varied"]:
        m = MET[(a, c)]
        row = f"  {a:<7}{c:<12} tok/run={tm:>9.1f}"
        for k in (1, 5, 15):
            v = m[f"pass^{k}"]
            row += f"  tok/pass^{k}=" + (f"{tm / v:>10.1f}" if v else "       inf" if v == 0 else "       n/a")
        print(row)

sub("3.5 trajectory metrics over tool-call NAME sequences (within-group pairwise means)")
TRAJ = {}
for a in ARMS:
    for c in CONDS:
        eo, jc, nl, seqlens, empty = [], [], [], [], 0
        for cid in cases_for(c):
            recs = G[(a, c, cid)]
            seqs = [tool_names(r.get("tool_calls")) for r in recs]
            seqlens.extend(len(s) for s in seqs)
            empty += sum(1 for s in seqs if not s)
            prs = list(combinations(range(len(seqs)), 2))
            eo.append(mean([1.0 if seqs[i] == seqs[j] else 0.0 for i, j in prs]))
            jc.append(mean([jaccard(seqs[i], seqs[j]) for i, j in prs]))
            nl.append(mean([nlcs(seqs[i], seqs[j]) for i, j in prs]))
        TRAJ[(a, c)] = (mean(eo), mean(jc), mean(nl), mean(seqlens), empty)
print(f"{'arm':<7}{'condition':<12}{'exact-order':>13}{'jaccard':>10}{'nLCS':>9}"
      f"{'mean|seq|':>11}{'empty':>7}")
for a in ARMS:
    for c in CONDS:
        e, j, n, sl, em = TRAJ[(a, c)]
        print(f"{a:<7}{c:<12}{e:>13.4f}{j:>10.4f}{n:>9.4f}{sl:>11.2f}{em:>7}")

sub("3.6 arm-difference statistics on per-case accuracy (paired over cases)")
random.seed(RNG_SEED)


def per_case_acc(arm, conds):
    out = {}
    for c in conds:
        for cid in cases_for(c):
            d = [r["decision"] for r in G[(arm, c, cid)]]
            out.setdefault(cid, []).extend(x == LABEL[cid] for x in d)
    return {cid: sum(v) / len(v) for cid, v in out.items()}


for scope, conds, ids in [
    ("primary", ["t0-fixed", "t07-varied"], PRIMARY),
    ("perturbation", ["pert-t0", "pert-t05", "pert-t10"], PERT_IDS),
]:
    s = per_case_acc("single", conds)
    m = per_case_acc("mas", conds)
    diffs = [m[c] - s[c] for c in ids]
    obs = mean(diffs)
    boots = []
    n = len(ids)
    for _ in range(B_BOOT):
        samp = [diffs[random.randrange(n)] for _ in range(n)]
        boots.append(sum(samp) / n)
    boots.sort()
    lo, hi = boots[int(0.025 * B_BOOT)], boots[int(0.975 * B_BOOT) - 1]
    # paired permutation: flip sign of each case's difference
    cnt = 0
    for _ in range(N_PERM):
        st = sum(d if random.random() < 0.5 else -d for d in diffs) / n
        if abs(st) >= abs(obs) - 1e-12:
            cnt += 1
    p = (cnt + 1) / (N_PERM + 1)
    print(f"  {scope:<13} mean acc single={mean(list(s.values())):.4f} "
          f"mas={mean(list(m.values())):.4f}  diff(mas-single)={obs:+.4f}")
    print(f"                95% bootstrap CI over cases = [{lo:+.4f}, {hi:+.4f}]  "
          f"paired permutation p={p:.4f}  (n_cases={n})")
    # also on DAR
    def per_case_dar(arm):
        out = {}
        for cid in ids:
            vals = [dar([r["decision"] for r in G[(arm, c, cid)]]) for c in conds]
            out[cid] = mean(vals)
        return out
    sd, md = per_case_dar("single"), per_case_dar("mas")
    dd = [md[c] - sd[c] for c in ids]
    o2 = mean(dd)
    bo = sorted(sum(dd[random.randrange(n)] for _ in range(n)) / n for _ in range(B_BOOT))
    c2 = sum(1 for _ in range(N_PERM)
             if abs(sum(d if random.random() < 0.5 else -d for d in dd) / n) >= abs(o2) - 1e-12)
    print(f"                DAR single={mean(list(sd.values())):.4f} mas={mean(list(md.values())):.4f} "
          f"diff={o2:+.4f} CI=[{bo[int(.025 * B_BOOT)]:+.4f}, {bo[int(.975 * B_BOOT) - 1]:+.4f}] "
          f"p={(c2 + 1) / (N_PERM + 1):.4f}")

# ============================================================= SECTION 4
hdr("SECTION 4 - T=0 FIXED-SEED DETERMINISM")

for cond in ["t0-fixed", "pert-t0"]:
    sub(f"4.x condition {cond} (temperature 0.0, seed 42, {COND_REPEATS[cond]} repeats)")
    for a in ARMS:
        byte_id, dec_id, flip_groups, distinct_bytes = 0, 0, [], []
        for cid in cases_for(cond):
            recs = G[(a, cond, cid)]
            raws = [r.get("raw_output") for r in recs]
            decs = [r["decision"] for r in recs]
            nb = len(set(raws))
            distinct_bytes.append(nb)
            byte_id += nb == 1
            dec_id += len(set(decs)) == 1
            if len(set(decs)) > 1:
                flip_groups.append((cid, Counter(decs)))
        n = len(cases_for(cond))
        print(f"  {a:<7} byte-identical groups {byte_id}/{n} ({byte_id / n:.1%})   "
              f"decision-identical groups {dec_id}/{n} ({dec_id / n:.1%})")
        print(f"          mean distinct raw_output per group = {mean(distinct_bytes):.2f} "
              f"(max possible {COND_REPEATS[cond]}); distribution="
              f"{dict(sorted(Counter(distinct_bytes).items()))}")
        if flip_groups:
            print(f"          flipping groups ({len(flip_groups)}):")
            for cid, cnt in flip_groups:
                print(f"            {cid}: {dict(cnt)}  gt={LABEL[cid]}")

    sub(f"4.y first-repeat cache artefact test for {cond} (drop repeat_idx 0)")
    for a in ARMS:
        for tag, keep in [("all repeats", None), ("excl. repeat 0", 0)]:
            units, byte_id, dec_id = [], 0, 0
            for cid in cases_for(cond):
                recs = [r for r in G[(a, cond, cid)] if keep is None or r["repeat_idx"] != keep]
                units.append([r["decision"] for r in recs])
                byte_id += len(set(r.get("raw_output") for r in recs)) == 1
                dec_id += len(set(r["decision"] for r in recs)) == 1
            n = len(units)
            print(f"  {a:<7}{tag:<16} n_rep={len(units[0])} DAR={mean([dar(u) for u in units]):.4f} "
                  f"alpha={krippendorff_alpha_nominal(units):.4f} "
                  f"byte-id={byte_id}/{n} dec-id={dec_id}/{n}")
        # is repeat 0 systematically the odd one out?
        odd0, oddk = 0, 0
        for cid in cases_for(cond):
            recs = G[(a, cond, cid)]
            raws = [r.get("raw_output") for r in recs]
            cnt = Counter(raws)
            if len(cnt) < 2:
                continue
            modal = cnt.most_common(1)[0][0]
            if raws[0] != modal:
                odd0 += 1
            for i in range(1, len(raws)):
                if raws[i] != modal:
                    oddk += 1
        print(f"  {a:<7} groups where repeat0 differs from modal output: {odd0}; "
              f"non-zero repeats differing from modal: {oddk}")
        # per-repeat-index deviation rate (fair comparison)
        dev = Counter()
        tot = Counter()
        for cid in cases_for(cond):
            recs = G[(a, cond, cid)]
            raws = [r.get("raw_output") for r in recs]
            cnt = Counter(raws)
            modal = cnt.most_common(1)[0][0]
            for i, rr in enumerate(raws):
                tot[i] += 1
                dev[i] += rr != modal
        print(f"  {a:<7} per-repeat byte-deviation-from-modal rate: "
              + " ".join(f"r{i}={dev[i]}/{tot[i]}" for i in sorted(tot)))

sub("4.z wall-clock by repeat index at t0-fixed (cache warm-up signature)")
for a in ARMS:
    for cond in ["t0-fixed", "pert-t0"]:
        by = defaultdict(list)
        for cid in cases_for(cond):
            for r in G[(a, cond, cid)]:
                by[r["repeat_idx"]].append(r["wall_clock_s"])
        print(f"  {a:<7}{cond:<10} " + " ".join(
            f"r{i}={mean(by[i]):.1f}s" for i in sorted(by)))

# ============================================================= SECTION 5
hdr("SECTION 5 - DEGENERACY")

sub("5.1 label priors")
pp = Counter(LABEL[c] for c in PRIMARY)
qq = Counter(LABEL[c] for c in PERT_IDS)
print(f"  primary (n=50): {dict(pp)}  -> best constant baseline = "
      f"{pp.most_common(1)[0][0]} at {pp.most_common(1)[0][1] / 50:.4f}")
print(f"  perturbation (n=10): {dict(qq)} -> best constant baseline = "
      f"{qq.most_common(1)[0][0]} at {qq.most_common(1)[0][1] / 10:.4f}")

sub("5.2 decision distribution per arm x condition, modal rate, and degeneracy verdict")
print(f"{'arm':<7}{'condition':<12}{'n':>6}  {'escalate':>9}{'dismiss':>9}"
      f"{'investigate':>12}{'malformed':>10}  {'modal':<12}{'modal_rate':>11}")
DEG = {}
for a in ARMS:
    for c in CONDS:
        m = MET[(a, c)]
        d = m["dist"]
        n = m["n_runs"]
        modal, mrate = d.most_common(1)[0][0], d.most_common(1)[0][1] / n
        DEG[(a, c)] = (modal, mrate)
        print(f"{a:<7}{c:<12}{n:>6}  {d.get('escalate', 0):>9}{d.get('dismiss', 0):>9}"
              f"{d.get('investigate', 0):>12}{d.get('malformed', 0):>10}  "
              f"{modal:<12}{mrate:>11.4f}")

sub("5.3 majority-vote accuracy vs best constant-answer baseline (per arm x condition)")
print(f"{'arm':<7}{'condition':<12}{'maj_acc':>9}{'const_base':>12}{'delta':>9}"
      f"{'ties':>6}  {'verdict'}")
for a in ARMS:
    for c in CONDS:
        m = MET[(a, c)]
        cs = cases_for(c)
        pri = Counter(LABEL[x] for x in cs)
        base = pri.most_common(1)[0][1] / len(cs)
        # also: accuracy of the arm's own modal answer used as a constant
        modal = DEG[(a, c)][0]
        own = sum(LABEL[x] == modal for x in cs) / len(cs)
        delta = m["maj_acc"] - base
        v = "DEGENERATE (<= constant baseline)" if m["maj_acc"] <= base + 1e-12 else "beats baseline"
        print(f"{a:<7}{c:<12}{m['maj_acc']:>9.4f}{base:>12.4f}{delta:>+9.4f}"
              f"{m['maj_ties']:>6}  {v}  [own-modal-as-constant={own:.4f}]")

sub("5.4 strict degeneracy screen: modal rate >= 0.90 AND maj_acc <= constant baseline")
n_deg = 0
for a in ARMS:
    for c in CONDS:
        m = MET[(a, c)]
        modal, mrate = DEG[(a, c)]
        base = Counter(LABEL[x] for x in cases_for(c)).most_common(1)[0][1] / len(cases_for(c))
        crit1 = mrate >= 0.90
        crit2 = m["maj_acc"] <= base + 1e-12
        flag = crit1 or crit2
        n_deg += flag
        print(f"  {a:<7}{c:<12} modal={modal:<12} rate={mrate:.4f} "
              f"(>=0.90? {crit1})  maj_acc={m['maj_acc']:.4f} vs base={base:.4f} "
              f"(<=base? {crit2})  -> {'DEGENERATE' if flag else 'not degenerate'}")
print(f"  cells flagged degenerate by this screen: {n_deg}/10")

sub("5.5 per-case decision variety (is the arm reading the case at all?)")
for a in ARMS:
    for c in CONDS:
        cs = cases_for(c)
        modal_per_case = []
        for cid in cs:
            d = [r["decision"] for r in G[(a, c, cid)]]
            modal_per_case.append(majority(d)[0])
        u = Counter(modal_per_case)
        print(f"  {a:<7}{c:<12} distinct per-case majority answers: {dict(u)} "
              f"(cases={len(cs)})")

sub("5.6 perturbation sensitivity: does the arm flip when the case flips?")
for a in ARMS:
    for c in ["pert-t0", "pert-t05", "pert-t10"]:
        moved, total = 0, 0
        for p in perts:
            pid, bid = p["alert_id"], p["base_alert_id"]
            base_cond = "t0-fixed" if c == "pert-t0" else "t07-varied"
            bd = majority([r["decision"] for r in G[(a, base_cond, bid)]])[0]
            pd = majority([r["decision"] for r in G[(a, c, pid)]])[0]
            total += 1
            moved += bd != pd
        print(f"  {a:<7}{c:<12} majority answer changed on {moved}/{total} perturbed pairs "
              f"(ground truth changed on {sum(1 for p in perts if LABEL[p['alert_id']] != LABEL[p['base_alert_id']])}/10)")

# ============================================================= SECTION 6
hdr("SECTION 6 - TOOL CHANNEL")

sub("6.1 global tool-name census per arm")
for a in ARMS:
    c = Counter(t for r in J[a] for t in tool_names(r.get("tool_calls")))
    print(f"  {a:<7} total calls={sum(c.values()):>6}  {dict(c.most_common())}")
    unknown = {k: v for k, v in c.items() if k not in DATA_TOOLS | POLICY_TOOLS}
    print(f"          names outside declared partition: {unknown}")

sub("6.2 per-node liveness (a run is 'dead' for a node if it made 0 calls to that node's tools)")
DEAD = {}
for a in ARMS:
    for node, tools in [("data", DATA_TOOLS), ("policy_risk", POLICY_TOOLS)]:
        dead = [r for r in J[a] if not (set(tool_names(r.get("tool_calls"))) & tools)]
        DEAD[(a, node)] = dead
        print(f"  {a:<7}{node:<12} dead {len(dead)}/{len(J[a])} runs ({len(dead) / len(J[a]):.2%})")

sub("6.3 zero-tool runs (no calls at all)")
for a in ARMS:
    z = [r for r in J[a] if not tool_names(r.get("tool_calls"))]
    print(f"  {a:<7} runs with zero tool calls: {len(z)}/{len(J[a])}")
    for r in z[:8]:
        print(f"      {r['run_id']} dec={r['decision']} err={r.get('error') is not None} "
              f"ctok={r['completion_tokens']} len(raw)={len(r.get('raw_output') or '')}")

sub("6.4 WHY are dead-node runs dead? classification (MAS)")


def classify(r, node):
    """Evidence-based classification of a run with no call to `node`'s tools."""
    raw = r.get("raw_output") or ""
    no = r.get("node_outputs") or {}
    ntxt = no.get(node) or ""
    reasons = []
    if r.get("error"):
        reasons.append("harness_error")
    if not raw:
        reasons.append("empty_final_output")
    if not ntxt:
        reasons.append("empty_node_output")
    # truncation proxies
    if r["completion_tokens"] >= r["num_predict"] * 4:
        reasons.append("high_total_completion")
    if ntxt and len(ntxt) > 6000:
        reasons.append("long_node_output")
    low = (ntxt or raw).lower()
    if re.search(r"\b(cannot|can't|unable to|i do not have|no access|not available|"
                 r"refus|decline)\b", low):
        reasons.append("refusal_language")
    if re.search(r"\b(no tool|without tool|tool.{0,20}(unavailable|not available|failed))\b", low):
        reasons.append("tool_unavailable_language")
    if not reasons:
        reasons.append("clean_output_no_call")
    return tuple(sorted(reasons))


for a in ARMS:
    for node in ["data", "policy_risk"]:
        dead = DEAD[(a, node)]
        if not dead:
            continue
        cls = Counter(classify(r, node) for r in dead)
        print(f"\n  {a} / {node}: {len(dead)} dead runs")
        for k, v in cls.most_common():
            print(f"      {v:>4}  {'+'.join(k)}")
        # node output stats for dead runs
        if a == "mas":
            lens = [len((r.get("node_outputs") or {}).get(node) or "") for r in dead]
            print(f"      node '{node}' output length on dead runs: "
                  f"min={min(lens)} median={statistics.median(lens):.0f} max={max(lens)} "
                  f"zero-length={sum(1 for x in lens if x == 0)}/{len(lens)}")
            alive = [r for r in J[a] if r not in dead]
            lens2 = [len((r.get("node_outputs") or {}).get(node) or "") for r in alive]
            print(f"      node '{node}' output length on LIVE runs:  "
                  f"min={min(lens2)} median={statistics.median(lens2):.0f} max={max(lens2)} "
                  f"zero-length={sum(1 for x in lens2 if x == 0)}/{len(lens2)}")
            print(f"      completion_tokens dead median="
                  f"{statistics.median([r['completion_tokens'] for r in dead]):.0f} "
                  f"live median={statistics.median([r['completion_tokens'] for r in alive]):.0f}")
            print(f"      agent_messages dead median="
                  f"{statistics.median([r.get('agent_messages') or 0 for r in dead]):.0f} "
                  f"live median={statistics.median([r.get('agent_messages') or 0 for r in alive]):.0f}")
            # sample tails
            for r in dead[:3]:
                t = (r.get("node_outputs") or {}).get(node) or ""
                print(f"      SAMPLE {r['run_id']} node[{node}] len={len(t)} "
                      f"tail={t[-220:]!r}")

sub("6.5 MAS node_outputs emptiness census (all runs, all nodes)")
for node in ["orchestrator", "data", "policy_risk", "reporting"]:
    lens = [len((r.get("node_outputs") or {}).get(node) or "") for r in J["mas"]]
    print(f"  node {node:<14} empty={sum(1 for x in lens if x == 0):>5}/1150 "
          f"median_len={statistics.median(lens):>7.0f} max={max(lens):>7}")

sub("6.6 does node deadness predict the decision?")
for node in ["data", "policy_risk"]:
    dead = set(id(r) for r in DEAD[("mas", node)])
    dd = Counter(r["decision"] for r in J["mas"] if id(r) in dead)
    ld = Counter(r["decision"] for r in J["mas"] if id(r) not in dead)
    print(f"  {node:<12} dead-run decisions={dict(dd)}")
    print(f"  {'':<12} live-run decisions={dict(ld)}")
    ndead = sum(dd.values())
    nlive = sum(ld.values())
    accd = sum(1 for r in J["mas"] if id(r) in dead and r["decision"] == LABEL[r["case_id"]])
    accl = sum(1 for r in J["mas"] if id(r) not in dead and r["decision"] == LABEL[r["case_id"]])
    print(f"  {'':<12} accuracy dead={accd / ndead:.4f} (n={ndead})  "
          f"live={accl / nlive:.4f} (n={nlive})")

sub("6.7 single-arm tool usage per run (for contrast)")
for a in ARMS:
    ncalls = [len(tool_names(r.get("tool_calls"))) for r in J[a]]
    print(f"  {a:<7} calls/run mean={mean(ncalls):.2f} median={statistics.median(ncalls):.0f} "
          f"min={min(ncalls)} max={max(ncalls)} distribution={dict(sorted(Counter(ncalls).items()))}")

sub("6.8 tool-call sequences: most common trajectories")
for a in ARMS:
    seqs = Counter(tuple(tool_names(r.get("tool_calls"))) for r in J[a])
    print(f"  {a}: distinct sequences={len(seqs)}")
    for s, n in seqs.most_common(4):
        print(f"      n={n:<5} {list(s)}")

print("\nDONE")
