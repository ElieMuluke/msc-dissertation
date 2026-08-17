"""Independent integrity audit of results-muse-glimmer-30b (SECTION 1 + 2).

Written blind: derived only from manifest.json, the two journals, and the
benchmark/perturbation label files. Pure Python, no network, no LLM, no GPU.

Run from backend/:  .venv/bin/python experiments/analysis/eval_museglimmer_integrity.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

RES = Path("experiments/results-muse-glimmer-30b")
ALERTS = Path(
    "/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json"
)
PERT = Path("experiments/perturbation_cases.json")
ARMS = ["single", "mas"]

OK, BAD = [], []


def ok(msg):
    OK.append(msg)
    print(f"  [OK]   {msg}")


def bad(msg):
    BAD.append(msg)
    print(f"  [FAIL] {msg}")


def info(msg):
    print(f"  .      {msg}")


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n-- {t}")


# ---------------------------------------------------------------- loading


def read_journal(p: Path) -> list[dict]:
    out = []
    with open(p, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                bad(f"{p.name}:{i} JSON decode error: {e}")
    return out


def parse_ts(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# --------------------------------------------- own decision extraction (PRD-A)

_CONTRACT = re.compile(
    r"\AFINAL\s+DECISION\s*:\s*(escalate|dismiss|investigate)\s*[.!]?\Z", re.IGNORECASE
)


def my_extract(text):
    if not text:
        return "malformed"
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return "malformed"
    last = re.sub(r"[*_`#]", "", lines[-1]).strip()
    m = _CONTRACT.match(last)
    return m.group(1).lower() if m else "malformed"


def tool_names(tc):
    """tool_calls entries may be str OR dict -- normalise to list[str]."""
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


def main():
    manifest = json.load(open(RES / "manifest.json", encoding="utf-8"))
    journals = {a: read_journal(RES / f"journal-{a}.jsonl") for a in ARMS}
    alerts = json.load(open(ALERTS, encoding="utf-8"))["alerts"]
    perts = json.load(open(PERT, encoding="utf-8"))["alerts"]
    primary_ids = [a["alert_id"] for a in alerts]
    pert_ids = [a["alert_id"] for a in perts]

    hdr("SECTION 1 - DATA INTEGRITY")

    sub("1.1 journal line counts vs manifest totals")
    for a in ARMS:
        got, want = len(journals[a]), manifest["totals"][a]
        (ok if got == want else bad)(
            f"journal-{a}.jsonl records={got} manifest totals={want}"
        )
    tot = sum(len(journals[a]) for a in ARMS)
    (ok if tot == len(manifest["runs"]) else bad)(
        f"total records={tot} manifest runs={len(manifest['runs'])}"
    )

    sub("1.2 plan coverage: duplicate / missing run keys")
    plan = {}
    for r in manifest["runs"]:
        key = (r["arm"], r["case_id"], r["condition"], r["repeat_idx"])
        if key in plan:
            bad(f"manifest itself has duplicate plan key {key}")
        plan[key] = r

    seen = Counter()
    jrec = {}
    for a in ARMS:
        for r in journals[a]:
            key = (r["arm"], r["case_id"], r["condition"], r["repeat_idx"])
            seen[key] += 1
            jrec.setdefault(key, []).append(r)
    dups = {k: v for k, v in seen.items() if v > 1}
    (ok if not dups else bad)(f"duplicate run keys in journals: {len(dups)}")
    for k, v in list(dups.items())[:10]:
        info(f"dup {k} x{v}")
    missing = set(plan) - set(seen)
    extra = set(seen) - set(plan)
    (ok if not missing else bad)(f"plan keys missing from journals: {len(missing)}")
    for k in list(missing)[:10]:
        info(f"missing {k}")
    (ok if not extra else bad)(f"journal keys not in plan: {len(extra)}")
    for k in list(extra)[:10]:
        info(f"extra {k}")

    sub("1.3 run_id string consistency with key tuple")
    n_badid = 0
    for a in ARMS:
        for r in journals[a]:
            want = f"{r['arm']}:{r['case_id']}:{r['condition']}:{r['repeat_idx']}"
            if r["run_id"] != want:
                n_badid += 1
                if n_badid <= 5:
                    info(f"run_id mismatch: {r['run_id']} != {want}")
    (ok if n_badid == 0 else bad)(f"run_id != composed key: {n_badid}")

    sub("1.4 per-run seed / temperature / condition / block vs pre-generated plan")
    mism = Counter()
    examples = defaultdict(list)
    for key, recs in jrec.items():
        p = plan.get(key)
        if p is None:
            continue
        r = recs[0]
        for field in ("seed", "temperature", "block", "condition", "case_id", "arm"):
            if r.get(field) != p.get(field):
                mism[field] += 1
                if len(examples[field]) < 5:
                    examples[field].append(
                        f"{key} journal={r.get(field)!r} plan={p.get(field)!r}"
                    )
    if not mism:
        ok("all 2300 runs match plan on seed/temperature/block/condition/case_id/arm")
    else:
        for f, n in mism.items():
            bad(f"{f} mismatches vs plan: {n}")
            for e in examples[f]:
                info(e)

    sub("1.5 condition semantics (t=0 conditions must use fixed seed 42)")
    condcfg = {c["name"]: c for c in manifest["config"]["conditions"]}
    for cname, c in condcfg.items():
        rs = [r for a in ARMS for r in journals[a] if r["condition"] == cname]
        temps = set(r["temperature"] for r in rs)
        seeds = set(r["seed"] for r in rs)
        reps = set(r["repeat_idx"] for r in rs)
        exp_reps = set(range(c["repeats"]))
        tag = f"{cname}: n={len(rs)} temps={sorted(temps)} repeats={sorted(reps)}"
        if temps == {c["temperature"]} and reps == exp_reps:
            ok(tag)
        else:
            bad(tag + f" (expected temp={c['temperature']} repeats={sorted(exp_reps)})")
        if c["fixed_seed"] is not None:
            (ok if seeds == {c["fixed_seed"]} else bad)(
                f"{cname}: fixed_seed -> distinct seeds={len(seeds)} "
                f"(expect exactly {{{c['fixed_seed']}}}) got={sorted(seeds)[:5]}"
            )
        else:
            (ok if len(seeds) > 1 else bad)(
                f"{cname}: varied seed -> distinct seeds={len(seeds)} of {len(rs)} runs"
            )

    sub("1.5b varied-seed uniqueness per (arm,case,condition)")
    for cname, c in condcfg.items():
        if c["fixed_seed"] is not None:
            continue
        collide = 0
        groups = defaultdict(list)
        for a in ARMS:
            for r in journals[a]:
                if r["condition"] == cname:
                    groups[(r["arm"], r["case_id"])].append(r["seed"])
        for g, ss in groups.items():
            if len(set(ss)) != len(ss):
                collide += 1
        (ok if collide == 0 else bad)(
            f"{cname}: groups with repeated seed within case: {collide}/{len(groups)}"
        )
        # cross-arm seed pairing: does mas reuse single's seeds for same case/rep?
        pairs = 0
        same = 0
        for cid in primary_ids + pert_ids:
            s = {
                r["repeat_idx"]: r["seed"]
                for r in journals["single"]
                if r["case_id"] == cid and r["condition"] == cname
            }
            m = {
                r["repeat_idx"]: r["seed"]
                for r in journals["mas"]
                if r["case_id"] == cid and r["condition"] == cname
            }
            for k in set(s) & set(m):
                pairs += 1
                same += s[k] == m[k]
        if pairs:
            info(f"{cname}: cross-arm identical seed for same (case,repeat): {same}/{pairs}")

    sub("1.6 uniformity of environment fields")
    for field in ("model", "model_digest", "ollama_version", "think", "num_predict",
                  "cache_policy"):
        vals = Counter(r.get(field) for a in ARMS for r in journals[a])
        if len(vals) == 1:
            v = next(iter(vals))
            manv = manifest.get(field, manifest["config"].get(field, "<n/a>"))
            agree = "" if manv == "<n/a>" else f" (manifest={manv!r}, match={manv == v})"
            ok(f"{field}: uniform = {v!r}{agree}")
        else:
            bad(f"{field}: NOT uniform -> {dict(vals)}")

    sub("1.6b env block (gpu/driver/load) variability")
    for sk in ("gpu_name", "gpu_driver"):
        vals = Counter((r.get("env") or {}).get(sk) for a in ARMS for r in journals[a])
        (ok if len(vals) == 1 else bad)(f"env.{sk}: {dict(vals)}")
    hi = sum(1 for a in ARMS for r in journals[a]
             if (r.get("env") or {}).get("host_load_high"))
    info(f"env.host_load_high true in {hi}/2300 runs")
    vram = [(r.get("env") or {}).get("gpu_vram_used_mb") for a in ARMS
            for r in journals[a] if (r.get("env") or {}).get("gpu_vram_used_mb")]
    if vram:
        info(f"env.gpu_vram_used_mb min={min(vram)} max={max(vram)} distinct={len(set(vram))}")

    sub("1.7 decision domain + independent re-extraction from raw_output")
    OUTCOMES = {"escalate", "dismiss", "investigate", "malformed"}
    for a in ARMS:
        dom = Counter(r["decision"] for r in journals[a])
        outside = {k: v for k, v in dom.items() if k not in OUTCOMES}
        (ok if not outside else bad)(f"{a}: decision domain {dict(dom)}")
        redis = 0
        exemplars = []
        for r in journals[a]:
            mine = my_extract(r.get("raw_output"))
            if mine != r["decision"]:
                redis += 1
                if len(exemplars) < 6:
                    exemplars.append((r["run_id"], r["decision"], mine))
        (ok if redis == 0 else bad)(
            f"{a}: journal decision vs my independent PRD-A re-extraction: "
            f"{redis}/{len(journals[a])} disagree"
        )
        for e in exemplars:
            info(f"  re-extract diff: {e[0]} journal={e[1]} mine={e[2]}")

    sub("1.8 error / malformed accounting")
    for a in ARMS:
        errs = [r for r in journals[a] if r.get("error")]
        info(f"{a}: runs with non-null error = {len(errs)}")
        for r in errs:
            print(f"      run_id={r['run_id']}")
            print(f"        error       = {r['error']!r}")
            print(f"        decision    = {r['decision']!r}")
            print(f"        wall_clock_s= {r['wall_clock_s']}")
            print(f"        prompt_tok={r['prompt_tokens']} compl_tok={r['completion_tokens']}")
            print(f"        agent_messages={r.get('agent_messages')}")
            print(f"        tool_calls  = {tool_names(r.get('tool_calls'))}")
            ro = r.get("raw_output")
            print(f"        raw_output len={len(ro) if ro else 0}")
            if ro:
                print(f"        raw_output tail = {ro[-300:]!r}")
            no = r.get("node_outputs")
            if no:
                print(f"        node_outputs keys={list(no.keys())} "
                      f"lens={ {k: (len(v) if isinstance(v, str) else v) for k, v in no.items()} }")
            print(f"        started_at={r['started_at']} seed={r['seed']} temp={r['temperature']}")
        malf = [r for r in journals[a] if r["decision"] == "malformed"]
        info(f"{a}: malformed decisions = {len(malf)}")
        for r in malf[:10]:
            ro = r.get("raw_output") or ""
            info(f"  malformed {r['run_id']} err={r.get('error')!r} len={len(ro)} "
                 f"tail={ro[-120:]!r}")
        # truncation proxy
        trunc = [r for r in journals[a] if r.get("completion_tokens", 0) >= r.get("num_predict", 10**9)]
        info(f"{a}: completion_tokens >= num_predict (per-call cap proxy) = {len(trunc)}")

    sub("1.9 null / missing field census")
    for a in ARMS:
        nulls = Counter()
        for r in journals[a]:
            for k, v in r.items():
                if v is None:
                    nulls[k] += 1
        info(f"{a}: null fields -> {dict(nulls)}")

    sub("1.10 timestamp ordering and gaps > 10 min")
    gapinfo = {}
    for a in ARMS:
        recs = list(journals[a])
        ts = [parse_ts(r["started_at"]) for r in recs]
        nonmono = sum(1 for i in range(1, len(ts)) if ts[i] < ts[i - 1])
        info(f"{a}: file order non-monotone started_at steps = {nonmono}")
        info(f"{a}: first={recs[0]['started_at']} last={recs[-1]['started_at']}")
        gaps = []
        for i in range(1, len(recs)):
            d = (ts[i] - ts[i - 1]).total_seconds()
            # expected gap ~ previous run's wall clock
            excess = d - (recs[i - 1].get("wall_clock_s") or 0)
            if d > 600:
                gaps.append((i, d, excess, recs[i - 1], recs[i]))
        gapinfo[a] = gaps
        (ok if not gaps else bad)(f"{a}: inter-run started_at gaps > 600 s: {len(gaps)}")
        for i, d, exc, prev, cur in gaps:
            print(f"      GAP idx {i - 1}->{i}  {d:.0f}s (excess over prior wall_clock {exc:.0f}s)")
            print(f"        before: {prev['run_id']}  started_at={prev['started_at']} "
                  f"wall={prev['wall_clock_s']}")
            print(f"        after : {cur['run_id']}   started_at={cur['started_at']} "
                  f"wall={cur['wall_clock_s']}")
        # top 5 gaps regardless of threshold
        allg = sorted(
            ((ts[i] - ts[i - 1]).total_seconds(), i) for i in range(1, len(recs))
        )[-5:]
        info(f"{a}: 5 largest inter-run gaps (s) = {[round(g, 1) for g, _ in allg]}")

    sub("1.11 wall-clock sanity vs progress.json")
    prog = json.load(open(RES / "progress.json", encoding="utf-8"))
    for a in ARMS:
        w = [r["wall_clock_s"] for r in journals[a] if r.get("wall_clock_s") is not None]
        mean = sum(w) / len(w)
        pm = prog["arms"][a]["mean_wall_clock_s"]
        (ok if abs(mean - pm) < 0.05 else bad)(
            f"{a}: mean wall_clock_s recomputed={mean:.3f} progress.json={pm}"
        )
        info(f"{a}: min={min(w):.2f} max={max(w):.2f} sum={sum(w) / 3600:.2f} h")
        last = max(r["started_at"] for r in journals[a])
        (ok if last == prog["arms"][a]["last_run_at"] else bad)(
            f"{a}: max started_at={last} progress.last_run_at={prog['arms'][a]['last_run_at']}"
        )

    # ------------------------------------------------ SECTION 2: DEVIATIONS
    hdr("SECTION 2 - DECLARED DEVIATIONS (reboot resume + data recovery)")

    for a in ARMS:
        gaps = gapinfo[a]
        if not gaps:
            info(f"{a}: no >10min gap -> no visible interruption in this journal")
            continue
        for i, d, exc, prev, cur in gaps:
            sub(f"{a}: boundary at journal index {i} (0-based), gap {d:.0f}s")
            print(f"    LAST PRE-GAP RUN : {prev['run_id']} (journal index {i - 1}, "
                  f"1-based position {i})")
            print(f"    FIRST POST-GAP RUN: {cur['run_id']} (journal index {i}, "
                  f"1-based position {i + 1})")
            # position in plan
            arm_plan = [r for r in manifest["runs"] if r["arm"] == a]
            plan_ids = [r["run_id"] for r in arm_plan]
            try:
                pi_prev = plan_ids.index(prev["run_id"])
                pi_cur = plan_ids.index(cur["run_id"])
                (ok if pi_cur == pi_prev + 1 else bad)(
                    f"plan adjacency: prev is plan #{pi_prev + 1}/{len(plan_ids)}, "
                    f"next is plan #{pi_cur + 1} -> contiguous={pi_cur == pi_prev + 1}"
                )
            except ValueError:
                bad("boundary run_id not found in plan")
            # journal order == plan order for this arm?
            jids = [r["run_id"] for r in journals[a]]
            (ok if jids == plan_ids else bad)(
                f"{a}: journal record order identical to manifest plan order"
            )
            if jids != plan_ids:
                diff = [k for k in range(min(len(jids), len(plan_ids)))
                        if jids[k] != plan_ids[k]]
                info(f"first order divergence at index {diff[0] if diff else 'n/a'}")

            # duplicates in a +-25 window
            win = journals[a][max(0, i - 25): i + 25]
            wk = Counter((r["case_id"], r["condition"], r["repeat_idx"]) for r in win)
            wd = {k: v for k, v in wk.items() if v > 1}
            (ok if not wd else bad)(f"duplicate keys within +/-25 runs of boundary: {len(wd)}")

            # seeds around boundary still plan-matching
            sm = 0
            for r in win:
                key = (r["arm"], r["case_id"], r["condition"], r["repeat_idx"])
                if plan[key]["seed"] != r["seed"] or plan[key]["temperature"] != r["temperature"]:
                    sm += 1
            (ok if sm == 0 else bad)(f"seed/temp mismatches within boundary window: {sm}")

            # env change across boundary
            for sk in ("gpu_driver", "gpu_name", "gpu_vram_used_mb"):
                info(f"env.{sk}: before={(prev.get('env') or {}).get(sk)} "
                     f"after={(cur.get('env') or {}).get(sk)}")
            for sk in ("ollama_version", "model_digest", "num_predict", "think"):
                same = prev.get(sk) == cur.get(sk)
                (ok if same else bad)(f"{sk} unchanged across boundary: {same} "
                                      f"({prev.get(sk)!r} -> {cur.get(sk)!r})")

            # cold-cache behaviour: compare post-gap run to its siblings
            sub("cold-cache boundary check: first post-resume run vs its sibling repeats")
            sibs = [r for r in journals[a]
                    if r["case_id"] == cur["case_id"] and r["condition"] == cur["condition"]]
            sibs.sort(key=lambda r: r["repeat_idx"])
            for r in sibs:
                mark = "  <== first post-resume" if r["run_id"] == cur["run_id"] else ""
                print(f"      rep{r['repeat_idx']} dec={r['decision']:<12} "
                      f"wall={r['wall_clock_s']:>8.2f} ptok={r['prompt_tokens']:>6} "
                      f"ctok={r['completion_tokens']:>5} "
                      f"len(raw)={len(r.get('raw_output') or ''):>6} "
                      f"tools={len(tool_names(r.get('tool_calls')))}{mark}")
            byteset = Counter(r.get("raw_output") for r in sibs)
            info(f"distinct raw_output among {len(sibs)} siblings: {len(byteset)}")
            # is the post-resume run byte-identical to any sibling?
            others = [r for r in sibs if r["run_id"] != cur["run_id"]]
            ident = sum(1 for r in others if r.get("raw_output") == cur.get("raw_output"))
            info(f"post-resume run byte-identical to {ident}/{len(others)} siblings")

            # aggregate cold-start effect: wall clock of run i vs local median
            import statistics
            w_all = [r["wall_clock_s"] for r in journals[a]]
            med = statistics.median(w_all)
            info(f"post-resume wall_clock={cur['wall_clock_s']:.2f} vs arm median={med:.2f} "
                 f"(ratio {cur['wall_clock_s'] / med:.2f}x)")
            nb = journals[a][i: i + 10]
            info("next 10 post-resume wall_clock_s: "
                 + str([round(r["wall_clock_s"], 1) for r in nb]))
            pb = journals[a][max(0, i - 10): i]
            info("prior 10 pre-gap  wall_clock_s: "
                 + str([round(r["wall_clock_s"], 1) for r in pb]))

    sub("2.x MAS progress position of the declared 653/1150 checkpoint")
    m = journals["mas"]
    for idx in (651, 652, 653, 654):
        if 0 <= idx < len(m):
            r = m[idx]
            info(f"mas journal 1-based #{idx + 1}: {r['run_id']} started_at={r['started_at']}")

    sub("2.y date histogram of started_at per arm (recovery/reboot visibility)")
    for a in ARMS:
        c = Counter(r["started_at"][:13] for r in journals[a])
        for k in sorted(c):
            print(f"      {a} {k}h  n={c[k]}")

    hdr("SUMMARY")
    print(f"  OK checks   : {len(OK)}")
    print(f"  FAIL checks : {len(BAD)}")
    for b in BAD:
        print(f"    - {b}")


if __name__ == "__main__":
    main()
