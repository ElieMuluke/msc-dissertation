"""Independent audit: data integrity for results-granite4.1-8b.

Pure-Python, JSONL only. No LLM calls, no GPU, no network.
Writes nothing; prints a report to stdout.
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

RES = "/home/eliem/Projects/ai/msc-dissertation/backend/experiments/results-granite4.1-8b"
LABELS = "/home/eliem/Projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json"
PERT = "/home/eliem/Projects/ai/msc-dissertation/backend/experiments/perturbation_cases.json"


def load_jsonl(p):
    rows, bad = [], []
    with open(p, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as e:  # noqa
                bad.append((i, str(e)))
    return rows, bad


def parse_ts(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def main():
    out = []
    P = out.append

    man = json.load(open(os.path.join(RES, "manifest.json")))
    man2 = json.load(open(os.path.join(RES, "manifest-ollama0326.json")))

    P("=" * 78)
    P("1. DATA INTEGRITY")
    P("=" * 78)

    # -- manifest comparison ------------------------------------------------
    P("\n[1.0] Two-manifest comparison")
    for k in sorted(set(man) | set(man2)):
        if k == "runs":
            continue
        a, b = man.get(k), man2.get(k)
        if a != b:
            P(f"  DIFFER {k}: manifest.json={json.dumps(a)[:80]} | ollama0326={json.dumps(b)[:80]}")
    P(f"  runs plan identical: {man['runs'] == man2['runs']} (n={len(man['runs'])})")
    P(f"  config_hash identical: {man['config_hash'] == man2['config_hash']}")

    # -- journals -----------------------------------------------------------
    rs, bad_s = load_jsonl(os.path.join(RES, "journal-single.jsonl"))
    rm, bad_m = load_jsonl(os.path.join(RES, "journal-mas.jsonl"))
    rows = rs + rm
    P("\n[1.1] Journal counts")
    P(f"  journal-single.jsonl : {len(rs)} rows, {len(bad_s)} unparseable")
    P(f"  journal-mas.jsonl    : {len(rm)} rows, {len(bad_m)} unparseable")
    P(f"  total                : {len(rows)}")
    P(f"  manifest totals      : {man['totals']} (sum={sum(man['totals'].values())})")
    P(f"  progress.json        : {json.load(open(os.path.join(RES,'progress.json')))['done']}")

    # arm purity of files
    P(f"  arms in journal-single: {Counter(r['arm'] for r in rs)}")
    P(f"  arms in journal-mas   : {Counter(r['arm'] for r in rm)}")

    # -- run keys -----------------------------------------------------------
    def key(r):
        return (r["arm"], r["case_id"], r["condition"], r["repeat_idx"])

    jkeys = Counter(key(r) for r in rows)
    mkeys = Counter((r["arm"], r["case_id"], r["condition"], r["repeat_idx"]) for r in man["runs"])
    dups = {k: v for k, v in jkeys.items() if v > 1}
    missing = set(mkeys) - set(jkeys)
    extra = set(jkeys) - set(mkeys)
    P("\n[1.2] Run-key coverage vs manifest (arm, case_id, condition, repeat_idx)")
    P(f"  manifest unique keys : {len(mkeys)} (dups in manifest: {sum(1 for v in mkeys.values() if v>1)})")
    P(f"  journal unique keys  : {len(jkeys)}")
    P(f"  duplicate keys       : {len(dups)}")
    if dups:
        P(f"    examples: {list(dups.items())[:5]}")
    P(f"  missing (planned, not run): {len(missing)}")
    if missing:
        P(f"    examples: {sorted(missing)[:5]}")
    P(f"  extra (run, not planned)  : {len(extra)}")
    if extra:
        P(f"    examples: {sorted(extra)[:5]}")

    # run_id uniqueness
    rid = Counter(r["run_id"] for r in rows)
    P(f"  duplicate run_id     : {sum(1 for v in rid.values() if v>1)}")

    # -- plan conformance ---------------------------------------------------
    plan = {(r["arm"], r["case_id"], r["condition"], r["repeat_idx"]): r for r in man["runs"]}
    mism = defaultdict(list)
    for r in rows:
        p = plan.get(key(r))
        if p is None:
            continue
        for f in ("seed", "temperature", "block"):
            if r.get(f) != p.get(f):
                mism[f].append((r["run_id"], r.get(f), p.get(f)))
    P("\n[1.3] Per-run conformance to pre-generated plan")
    for f in ("seed", "temperature", "block"):
        P(f"  {f}: {len(mism[f])} mismatches" + (f" e.g. {mism[f][:3]}" if mism[f] else ""))

    # condition->temperature contract from config
    cond_cfg = {c["name"]: c for c in man["config"]["conditions"]}
    bad_temp = [r["run_id"] for r in rows
                if abs(r["temperature"] - cond_cfg[r["condition"]]["temperature"]) > 1e-9]
    bad_seed = []
    for r in rows:
        c = cond_cfg[r["condition"]]
        if c["fixed_seed"] is not None and r["seed"] != c["fixed_seed"]:
            bad_seed.append(r["run_id"])
    P(f"  temperature vs condition contract: {len(bad_temp)} violations")
    P(f"  fixed_seed vs condition contract : {len(bad_seed)} violations")

    # varied-seed conditions: are seeds actually distinct per (case,repeat)?
    P("\n[1.4] Seed behaviour per condition")
    for cond in sorted(cond_cfg):
        sub = [r for r in rows if r["condition"] == cond]
        seeds = Counter(r["seed"] for r in sub)
        P(f"  {cond:12s} n={len(sub):5d} distinct_seeds={len(seeds):5d} "
          f"fixed_seed_cfg={cond_cfg[cond]['fixed_seed']} "
          f"sample={sorted(seeds)[:4]}")

    # per (arm,case,condition) do repeats share a seed?
    P("\n[1.4b] Within (arm,case,condition): seeds shared across repeats?")
    for cond in sorted(cond_cfg):
        groups = defaultdict(set)
        for r in rows:
            if r["condition"] == cond:
                groups[(r["arm"], r["case_id"])].add(r["seed"])
        sizes = Counter(len(v) for v in groups.values())
        P(f"  {cond:12s} distinct-seeds-per-group histogram: {dict(sizes)}")

    # -- environment uniformity --------------------------------------------
    P("\n[1.5] Environment uniformity")
    for f in ("model", "model_digest", "ollama_version", "num_predict", "think", "cache_policy"):
        c = Counter(json.dumps(r.get(f)) for r in rows)
        P(f"  {f}: {dict(c)}" if len(c) <= 6 else f"  {f}: {len(c)} distinct")
    # split by arm
    P("  ollama_version by arm:")
    for arm in ("single", "mas"):
        P(f"    {arm}: {dict(Counter(r['ollama_version'] for r in rows if r['arm']==arm))}")
    P(f"  manifest.json ollama_version = {man['ollama_version']}; "
      f"manifest-ollama0326 = {man2['ollama_version']}")
    jv = set(r["ollama_version"] for r in rows)
    P(f"  journals correspond to: {'manifest.json' if jv == {man['ollama_version']} else 'AMBIGUOUS/SPLIT'} (journal versions={jv})")
    P(f"  model_digest matches manifest: "
      f"{all(r['model_digest']==man['model_digest'] for r in rows)}")

    # env sub-dict
    gpus = Counter(json.dumps(r.get("env", {}).get("gpu_name")) for r in rows)
    drv = Counter(json.dumps(r.get("env", {}).get("gpu_driver")) for r in rows)
    P(f"  env.gpu_name: {dict(gpus)}")
    P(f"  env.gpu_driver: {dict(drv)}")
    hl = Counter(r.get("env", {}).get("host_load_high") for r in rows)
    P(f"  env.host_load_high: {dict(hl)}")

    # -- decision domain / errors -------------------------------------------
    P("\n[1.6] Decision value domain & error accounting")
    P(f"  decision values: {dict(Counter(json.dumps(r.get('decision')) for r in rows))}")
    errs = [r for r in rows if r.get("error")]
    P(f"  rows with non-null error: {len(errs)}")
    if errs:
        P(f"    {dict(Counter(str(r['error'])[:60] for r in errs))}")
    nulldec = [r for r in rows if r.get("decision") is None]
    P(f"  rows with null decision: {len(nulldec)}")
    empty_raw = [r for r in rows if not (r.get("raw_output") or "").strip()]
    P(f"  rows with empty raw_output: {len(empty_raw)}")
    # does raw_output actually end with the contracted final line?
    def tail_ok(r):
        ro = (r.get("raw_output") or "").strip()
        return ro.lower().rsplit("\n", 1)[-1].startswith("final decision:")
    P(f"  rows whose raw_output last line is 'FINAL DECISION: ...': "
      f"{sum(1 for r in rows if tail_ok(r))}/{len(rows)}")
    # decision consistency with the parsed tail
    def tail_dec(r):
        ro = (r.get("raw_output") or "").strip().lower()
        i = ro.rfind("final decision:")
        if i < 0:
            return None
        t = ro[i + len("final decision:"):].strip().strip("*_ .`").split()
        return t[0].strip("*_.`") if t else None
    mismatch = [(r["run_id"], r["decision"], tail_dec(r)) for r in rows
                if tail_dec(r) is not None and tail_dec(r) != r["decision"]]
    P(f"  parsed-tail vs recorded decision mismatches: {len(mismatch)}")
    for m in mismatch[:8]:
        P(f"    {m}")
    notail = [r["run_id"] for r in rows if tail_dec(r) is None]
    P(f"  rows with NO parseable 'FINAL DECISION' anywhere: {len(notail)}")
    for r in notail[:5]:
        P(f"    {r}")

    # tool_calls / node_outputs presence
    P("\n[1.7] Structural fields")
    for arm in ("single", "mas"):
        sub = [r for r in rows if r["arm"] == arm]
        P(f"  {arm}: node_outputs non-null {sum(1 for r in sub if r.get('node_outputs') is not None)}/{len(sub)}; "
          f"tool_calls empty {sum(1 for r in sub if not r.get('tool_calls'))}/{len(sub)}; "
          f"mean agent_messages {sum(r.get('agent_messages') or 0 for r in sub)/len(sub):.2f}")
    zero_tok = [r["run_id"] for r in rows if not r.get("completion_tokens")]
    P(f"  rows with zero/absent completion_tokens: {len(zero_tok)}")

    # -- timeline -----------------------------------------------------------
    P("\n[1.8] Timeline / gaps > 10 min")
    for name, sub in (("single", rs), ("mas", rm)):
        ts = sorted([parse_ts(r["started_at"]) for r in sub if r.get("started_at")])
        P(f"  {name}: {ts[0].isoformat()} -> {ts[-1].isoformat()} "
          f"span {(ts[-1]-ts[0]).total_seconds()/3600:.2f} h")
        gaps = []
        for a, b in zip(ts, ts[1:]):
            d = (b - a).total_seconds()
            if d > 600:
                gaps.append((a.isoformat(), b.isoformat(), round(d / 60, 1)))
        P(f"    gaps > 10 min: {len(gaps)}")
        for g in gaps:
            P(f"      {g[0]} -> {g[1]}  ({g[2]} min)")
        # monotonicity of journal write order
        raw = [parse_ts(r["started_at"]) for r in sub if r.get("started_at")]
        nonmono = sum(1 for a, b in zip(raw, raw[1:]) if b < a)
        P(f"    non-monotonic started_at steps in file order: {nonmono}")

    # overlap between arms in time (were they run concurrently?)
    tss = [parse_ts(r["started_at"]) for r in rs]
    tsm = [parse_ts(r["started_at"]) for r in rm]
    P(f"  single window: {min(tss)} .. {max(tss)}")
    P(f"  mas    window: {min(tsm)} .. {max(tsm)}")
    P(f"  arms overlap in wall-clock time: {min(tss) < max(tsm) and min(tsm) < max(tss)}")

    # -- coverage vs benchmark ---------------------------------------------
    labels = {a["alert_id"]: a["ground_truth"]
              for a in json.load(open(LABELS))["alerts"]}
    pert = {a["alert_id"]: a["ground_truth"]
            for a in json.load(open(PERT))["alerts"]}
    P("\n[1.9] Case coverage vs benchmark files")
    prim = set(r["case_id"] for r in rows if r["block"] == "primary")
    pertc = set(r["case_id"] for r in rows if r["block"] == "perturbation")
    P(f"  primary cases in journals: {len(prim)}; labels file: {len(labels)}; "
      f"unlabelled: {sorted(prim - set(labels))}")
    P(f"  perturbation cases: {len(pertc)}; file: {len(pert)}; "
      f"unlabelled: {sorted(pertc - set(pert))}")
    P(f"  label distribution (primary): {dict(Counter(labels.values()))}")
    P(f"  label distribution (pert):    {dict(Counter(pert.values()))}")

    # per condition x arm counts
    P("\n[1.10] Cell counts (arm x condition)")
    cc = Counter((r["arm"], r["condition"]) for r in rows)
    for k in sorted(cc):
        exp = len(prim if cond_cfg[k[1]]["block"] == "primary" else pertc) * cond_cfg[k[1]]["repeats"]
        P(f"  {k}: {cc[k]} (expected {exp}) {'OK' if cc[k]==exp else 'MISMATCH'}")

    print("\n".join(out))


if __name__ == "__main__":
    main()
