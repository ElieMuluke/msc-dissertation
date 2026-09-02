"""Independent audit — `qwen3.5:9b@think-budget` (results-qwen3.5-9b-thinking-budget).

Written from scratch by an auditor with no prior involvement in the sweep.
Nothing is imported from `experiments.analysis.metrics`, `experiments.harness`
or `experiments.config`: every rule (decision extraction, seed schedule,
metrics, statistics) is re-implemented here from the written specification so
that agreement with `analysis-report.md` is evidence, not tautology.

Read-only. Makes no network/LLM calls.

Usage (from backend/):
    .venv/bin/python -m experiments.analysis.independent_check_qwen35_thinking_budget
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

# --------------------------------------------------------------------------
# Locations (all absolute; nothing is written)
# --------------------------------------------------------------------------
EXPERIMENTS = Path(__file__).resolve().parents[1]
TARGET = EXPERIMENTS / "results-qwen3.5-9b-thinking-budget"
SEALED_THINKING_OFF = EXPERIMENTS / "results"          # qwen3.5:9b, think=false
SIBLING_LFM = EXPERIMENTS / "results-lfm2.5-8b-thinking"  # 2048-budget sibling
ALERTS_JSON = Path(
    "/home/eliem/Projects/dfah-repo/econometrics/benchmarks/"
    "compliance_triage/data/alerts.json"
)
PERTURBATION_JSON = EXPERIMENTS / "perturbation_cases.json"

# Locked design constants, transcribed from the PRD/config documentation.
DECISIONS = ("escalate", "dismiss", "investigate")
OUTCOMES = DECISIONS + ("malformed",)
ARMS = ("single", "mas")
MASTER_SEED = 20260805
FIXED_SEED = 42
# name, block, temperature, repeats, fixed_seed
CONDITIONS = (
    ("t0-fixed", "primary", 0.0, 5, FIXED_SEED),
    ("t07-varied", "primary", 0.7, 15, None),
    ("pert-t0", "perturbation", 0.0, 5, FIXED_SEED),
    ("pert-t05", "perturbation", 0.5, 5, None),
    ("pert-t10", "perturbation", 1.0, 5, None),
)
EXPECTED_OLLAMA = "0.32.9"
EXPECTED_NUM_PREDICT = 8192
EXPECTED_THINK = True

FAILURES: list[str] = []
NOTES: list[str] = []


def head(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def sub(title: str) -> None:
    print(f"\n-- {title}")


def ok(msg: str) -> None:
    print(f"   [OK]   {msg}")


def bad(msg: str) -> None:
    FAILURES.append(msg)
    print(f"   [FAIL] {msg}")


def note(msg: str) -> None:
    NOTES.append(msg)
    print(f"   [NOTE] {msg}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open() as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:  # pragma: no cover
                bad(f"{path.name} line {i} is not valid JSON: {exc}")
    return out


# --------------------------------------------------------------------------
# 1. My own implementation of the locked decision-extraction rule
# --------------------------------------------------------------------------
# Spec (PRD-A, harness/extraction.py docstring), re-implemented independently:
#  - only the LAST non-empty line of the output is examined;
#  - markdown emphasis chars (* _ ` #) are stripped from that line;
#  - one trailing "." or "!" after the label is tolerated;
#  - case-insensitive; the line must contain nothing else;
#  - anything else (incl. empty output) -> "malformed".
_MD = "*_`#"
_LABEL_RE = re.compile(
    r"^final\s+decision\s*:\s*(escalate|dismiss|investigate)\s*[.!]?$"
)


def my_extract(text: str | None) -> str:
    if text is None:
        return "malformed"
    stripped = text.strip()
    if not stripped:
        return "malformed"
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if not lines:
        return "malformed"
    last = "".join(ch for ch in lines[-1] if ch not in _MD).strip()
    m = _LABEL_RE.match(last.lower())
    return m.group(1) if m else "malformed"


# --------------------------------------------------------------------------
# 2. My own re-derivation of the planned run matrix + seed schedule
# --------------------------------------------------------------------------
def my_planned_runs(primary_ids: list[str], pert_ids: list[str]) -> list[dict[str, Any]]:
    """Spec: one RNG seeded with MASTER_SEED, walked condition -> case ->
    repeat; the seed is drawn once per (condition, case, repeat) and SHARED by
    both arms; fixed-seed conditions consume no draw."""
    rng = random.Random(MASTER_SEED)
    runs = []
    for name, block, temp, repeats, fixed in CONDITIONS:
        case_ids = primary_ids if block == "primary" else pert_ids
        for case_id in case_ids:
            for rep in range(repeats):
                seed = fixed if fixed is not None else rng.randrange(2**31)
                for arm in ARMS:
                    runs.append({
                        "run_id": f"{arm}:{case_id}:{name}:{rep}",
                        "arm": arm, "case_id": case_id, "block": block,
                        "condition": name, "repeat_idx": rep,
                        "seed": seed, "temperature": temp,
                    })
    return runs


# --------------------------------------------------------------------------
# 3. My own metric implementations
# --------------------------------------------------------------------------
def n_choose_k(n: int, k: int) -> int:
    return math.comb(n, k)


def my_pass_hat_k(decisions: Sequence[str], label: str, k: int) -> float:
    n = len(decisions)
    c = sum(1 for d in decisions if d == label)
    if k > n:
        raise ValueError("k > n")
    if c < k:
        return 0.0
    return n_choose_k(c, k) / n_choose_k(n, k)


def my_dar(decisions: Sequence[str]) -> float:
    pairs = list(combinations(range(len(decisions)), 2))
    return sum(decisions[i] == decisions[j] for i, j in pairs) / len(pairs)


def my_flip(decisions: Sequence[str]) -> float:
    return float(len(set(decisions)) > 1)


def my_alpha(units: Sequence[Sequence[str]]) -> float | None:
    """Krippendorff alpha, nominal, coincidence-matrix form.
    Units = cases, coders = repeats. Malformed is an ordinary category."""
    coin: Counter[tuple[str, str]] = Counter()
    for unit in units:
        m = len(unit)
        if m < 2:
            continue
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                coin[(unit[i], unit[j])] += 1.0 / (m - 1)
    marg: Counter[str] = Counter()
    for (a, _), w in coin.items():
        marg[a] += w
    n = sum(marg.values())
    if n <= 1:
        return None
    d_o = sum(w for (a, b), w in coin.items() if a != b)
    d_e = sum(marg[a] * marg[b] for a in marg for b in marg if a != b) / (n - 1)
    if d_e == 0:
        return 1.0
    return 1.0 - d_o / d_e


def my_majority(decisions: Sequence[str]) -> tuple[str, bool]:
    """Modal outcome; ties broken by CANONICAL OUTCOMES order
    (escalate > dismiss > investigate > malformed) as implemented in
    analysis/metrics.py (docs corrected 2026-08-12 to match code)."""
    cnt = Counter(decisions)
    top = max(cnt.values())
    winners = [o for o in OUTCOMES if cnt.get(o, 0) == top]
    return winners[0], len(winners) > 1


def my_majority_first_observed(decisions: Sequence[str]) -> str:
    """The superseded convention, computed only to size the difference."""
    cnt = Counter(decisions)
    top = max(cnt.values())
    for d in decisions:
        if cnt[d] == top:
            return d
    raise AssertionError


def my_entropy(decisions: Sequence[str]) -> float:
    cnt = Counter(decisions)
    tot = len(decisions)
    h = -sum((c / tot) * math.log2(c / tot) for c in cnt.values() if c)
    return h / math.log2(len(OUTCOMES))


def lcs_len(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def pairwise_mean(items: Sequence[Any], fn) -> float:
    pairs = list(combinations(range(len(items)), 2))
    return sum(fn(items[i], items[j]) for i, j in pairs) / len(pairs)


def my_tar(trajs: Sequence[Sequence[str]]) -> float:
    return pairwise_mean(trajs, lambda a, b: float(list(a) == list(b)))


def my_jaccard(trajs: Sequence[Sequence[str]]) -> float:
    def j(a, b):
        sa, sb = set(a), set(b)
        if not sa and not sb:
            return 1.0
        return len(sa & sb) / len(sa | sb)
    return pairwise_mean(trajs, j)


def my_nlcs(trajs: Sequence[Sequence[str]]) -> float:
    def f(a, b):
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return lcs_len(a, b) / max(len(a), len(b))
    return pairwise_mean(trajs, f)


def my_rouge_l(raws: Sequence[str]) -> float:
    toks = [r.lower().split() for r in raws]

    def f(a, b):
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        l = lcs_len(a, b)
        if l == 0:
            return 0.0
        p, r = l / len(a), l / len(b)
        return 2 * p * r / (p + r)
    return pairwise_mean(toks, f)


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


# --------------------------------------------------------------------------
# 4. My own statistics
# --------------------------------------------------------------------------
def my_bootstrap_ci(values: Sequence[float], seed: int, n_boot: int = 10_000):
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
    means = arr[idx].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(lo), float(hi)


def my_permutation_p(diffs: Sequence[float], seed: int, n_perm: int = 10_000) -> float:
    arr = np.asarray(diffs, dtype=float)
    observed = abs(arr.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, arr.size))
    perm = np.abs((signs * arr).mean(axis=1))
    return float((np.sum(perm >= observed - 1e-12) + 1) / (n_perm + 1))


# --------------------------------------------------------------------------
# Grouping + full condition summary
# --------------------------------------------------------------------------
class Group:
    def __init__(self) -> None:
        self.decisions: list[str] = []
        self.trajs: list[list[str]] = []
        self.raws: list[str] = []
        self.ptok: list[int] = []
        self.ctok: list[int] = []
        self.wall: list[float] = []


def group_runs(records: Iterable[dict], arm: str, condition: str,
               decision_key: str = "decision") -> dict[str, Group]:
    sel = sorted(
        (r for r in records if r["arm"] == arm and r["condition"] == condition),
        key=lambda r: (r["case_id"], r["repeat_idx"]),
    )
    out: dict[str, Group] = {}
    for r in sel:
        g = out.setdefault(r["case_id"], Group())
        g.decisions.append(r[decision_key])
        g.trajs.append(list(r.get("tool_calls") or []))
        g.raws.append(str(r.get("raw_output") or ""))
        g.ptok.append(int(r.get("prompt_tokens") or 0))
        g.ctok.append(int(r.get("completion_tokens") or 0))
        g.wall.append(float(r.get("wall_clock_s") or 0.0))
    return out


def summarise(groups: dict[str, Group], labels: dict[str, str]) -> dict[str, Any]:
    cases = sorted(groups)
    dec = [groups[c].decisions for c in cases]
    n = min(len(d) for d in dec)
    s: dict[str, Any] = {"cases": len(cases), "repeats": n}
    ks = sorted({k for k in (1, 5, 15) if k <= n} | {n})
    for k in ks:
        s[f"pass^{k}"] = mean([my_pass_hat_k(groups[c].decisions, labels[c], k)
                               for c in cases])
    s["DAR"] = mean([my_dar(d) for d in dec])
    s["krippendorff_alpha"] = my_alpha(dec)
    s["flip_rate"] = mean([my_flip(d) for d in dec])
    maj = [my_majority(groups[c].decisions) for c in cases]
    s["majority_vote_accuracy"] = mean([float(m[0] == labels[c])
                                        for m, c in zip(maj, cases)])
    s["majority_ties"] = sum(1 for m in maj if m[1])
    s["majority_vote_accuracy_first_observed"] = mean(
        [float(my_majority_first_observed(groups[c].decisions) == labels[c])
         for c in cases])
    ent = {c: my_entropy(groups[c].decisions) for c in cases}
    s["mean_entropy"] = mean(list(ent.values()))
    s["worst_entropy_cases"] = sorted(ent, key=lambda c: (-ent[c], c))[:3]
    s["per_case_entropy"] = ent
    s["TAR"] = mean([my_tar(groups[c].trajs) for c in cases])
    s["jaccard"] = mean([my_jaccard(groups[c].trajs) for c in cases])
    s["nLCS"] = mean([my_nlcs(groups[c].trajs) for c in cases])
    s["rouge_l_f1"] = mean([my_rouge_l(groups[c].raws) for c in cases])
    tot = [p + c for cid in cases
           for p, c in zip(groups[cid].ptok, groups[cid].ctok)]
    s["tokens_per_run"] = mean([float(t) for t in tot])
    s["malformed_rate"] = mean([sum(d == "malformed" for d in ds) / len(ds)
                                for ds in dec])
    s["mean_wall_clock_s"] = mean([w for c in cases for w in groups[c].wall])
    for k in ks:
        pk = s[f"pass^{k}"]
        s[f"tokens_per_pass^{k}"] = s["tokens_per_run"] / pk if pk else None
    return s


# --------------------------------------------------------------------------
# Malformed classification (Forensic A)
# --------------------------------------------------------------------------
_KEYWORD_RE = re.compile(r"\b(escalate|dismiss|investigate)\b", re.IGNORECASE)
_FD_ANY_RE = re.compile(r"final\s+decision", re.IGNORECASE)
_FD_LABELLED_RE = re.compile(
    r"final\s+decision\s*:\s*([a-z_\-]+)", re.IGNORECASE)


def classify_malformed(raw: str | None, completion_tokens: int) -> tuple[str, str]:
    """Return (class, detail). Classes:
       empty answer / verdict welded onto a prose line / wrong keyword /
       no decision / truncated / decision-line-not-last
    """
    if raw is None or not raw.strip():
        return "empty answer", "no content at all"
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    last_raw = lines[-1]
    last = "".join(ch for ch in last_raw if ch not in _MD).strip()

    m = _FD_LABELLED_RE.search(last)
    if m:
        label = m.group(1).lower()
        # a contract phrase is present on the last line but the line failed
        rest = _FD_LABELLED_RE.sub("", last).strip(" .!:*_`#-")
        if label not in DECISIONS:
            return "wrong keyword", f"label={label!r}"
        if rest:
            return ("verdict welded onto a prose line",
                    f"extra text on contract line: {rest[:80]!r}")
        return "verdict welded onto a prose line", f"unparsed: {last[:80]!r}"

    # no contract phrase on the last line
    if _FD_ANY_RE.search(raw):
        return ("decision line not last",
                f"FINAL DECISION appears earlier; last line={last_raw[:80]!r}")
    if _KEYWORD_RE.search(last):
        return ("verdict welded onto a prose line",
                f"bare verdict word in prose, no contract phrase: {last[:80]!r}")
    # Structural truncation: the text stops mid-sentence (no terminal
    # punctuation, no closing markup) and never reaches the contract line.
    if last_raw and last_raw[-1] not in ".!?:;)]\"'`>*_":
        return ("truncated",
                f"stops mid-sentence, completion_tokens={completion_tokens}; "
                f"tail={last_raw[-70:]!r}")
    return "no decision", f"last line={last_raw[:80]!r}"


# --------------------------------------------------------------------------
# Channel-integrity scan (Forensic B)
# --------------------------------------------------------------------------
CHANNEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "open <think>": re.compile(r"<\s*think\s*>", re.IGNORECASE),
    "close </think>": re.compile(r"<\s*/\s*think\s*>", re.IGNORECASE),
    "open <thinking>": re.compile(r"<\s*thinking\s*>", re.IGNORECASE),
    "close </thinking>": re.compile(r"<\s*/\s*thinking\s*>", re.IGNORECASE),
    "open <reasoning>": re.compile(r"<\s*reasoning\s*>", re.IGNORECASE),
    "close </reasoning>": re.compile(r"<\s*/\s*reasoning\s*>", re.IGNORECASE),
    "lfm ◁think▷": re.compile(r"◁\s*/?\s*think\s*▷"),
    "harmony <|channel|>": re.compile(r"<\|\s*channel\s*\|>"),
    "harmony <|start|>": re.compile(r"<\|\s*start\s*\|>"),
    "harmony <|message|>": re.compile(r"<\|\s*message\s*\|>"),
    "harmony <|end|>": re.compile(r"<\|\s*end\s*\|>"),
    "harmony analysis channel": re.compile(r"<\|channel\|>\s*analysis"),
    "sentinel <|im_start|>": re.compile(r"<\|im_start\|>"),
    "sentinel <|assistant|>": re.compile(r"<\|assistant\|>"),
    "deepseek <｜tool": re.compile(r"<｜"),
    "bracket [THINK]": re.compile(r"\[\s*/?\s*THINK(ING)?\s*\]", re.IGNORECASE),
    "markdown thought header": re.compile(
        r"^\s*#{1,6}\s*(thinking|reasoning|internal monologue)\b",
        re.IGNORECASE | re.MULTILINE),
}


def scan_channel(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [name for name, rx in CHANNEL_PATTERNS.items() if rx.search(raw)]


# ==========================================================================
# MAIN
# ==========================================================================
def main() -> None:
    head("INDEPENDENT AUDIT — results-qwen3.5-9b-thinking-budget")
    print("Auditor-written recomputation. No harness/metrics code imported.")

    # ---------------- load ------------------------------------------------
    manifest = json.loads((TARGET / "manifest.json").read_text())
    single = read_jsonl(TARGET / "journal-single.jsonl")
    mas = read_jsonl(TARGET / "journal-mas.jsonl")
    records = single + mas
    by_arm = {"single": single, "mas": mas}

    alerts = json.loads(ALERTS_JSON.read_text())["alerts"]
    perts = json.loads(PERTURBATION_JSON.read_text())["alerts"]
    labels = {c["alert_id"]: c["ground_truth"] for c in alerts}
    labels.update({c["alert_id"]: c["ground_truth"] for c in perts})
    primary_ids = [c["alert_id"] for c in alerts]
    pert_ids = [c["alert_id"] for c in perts]

    # ======================================================================
    head("TASK 1 — INTEGRITY")
    # ======================================================================
    sub("1.1 counts vs manifest")
    print(f"   manifest planned runs : {len(manifest['runs'])}")
    print(f"   manifest totals       : {manifest['totals']}")
    print(f"   journal-single lines  : {len(single)}")
    print(f"   journal-mas lines     : {len(mas)}")
    if len(manifest["runs"]) == 2300 and len(single) == 1150 and len(mas) == 1150:
        ok("2,300 journal lines = 2,300 planned runs (1,150 per arm)")
    else:
        bad("run counts do not match the plan")
    for arm in ARMS:
        wrong = [r["run_id"] for r in by_arm[arm] if r["arm"] != arm]
        if wrong:
            bad(f"{len(wrong)} records in journal-{arm} carry arm != {arm}")
    if not any(r["arm"] != a for a in ARMS for r in by_arm[a]):
        ok("every record sits in the journal file matching its arm")

    sub("1.2 duplicate run_ids")
    ids = [r["run_id"] for r in records]
    dups = [k for k, v in Counter(ids).items() if v > 1]
    if dups:
        bad(f"{len(dups)} duplicate run_ids, e.g. {dups[:5]}")
    else:
        ok(f"{len(ids)} run_ids, all unique")

    sub("1.3 per-run seed / temperature / condition / arm / case vs plan")
    plan = {r["run_id"]: r for r in manifest["runs"]}
    plan_ids = set(plan)
    journal_ids = set(ids)
    if plan_ids == journal_ids:
        ok("run_id set is exactly the manifest's plan (no extras, no gaps)")
    else:
        bad(f"missing={len(plan_ids - journal_ids)} extra={len(journal_ids - plan_ids)}")
    mism = defaultdict(list)
    for r in records:
        p = plan.get(r["run_id"])
        if not p:
            continue
        for f in ("arm", "case_id", "block", "condition", "repeat_idx",
                  "seed", "temperature"):
            if r.get(f) != p[f]:
                mism[f].append((r["run_id"], r.get(f), p[f]))
    if mism:
        for f, v in mism.items():
            bad(f"{len(v)} runs disagree with manifest on {f}, e.g. {v[:3]}")
    else:
        ok("all 2,300 runs match the manifest on arm/case/block/condition/"
           "repeat_idx/seed/temperature")

    sub("1.4 seed schedule regenerated independently from MASTER_SEED")
    mine = {r["run_id"]: r for r in my_planned_runs(primary_ids, pert_ids)}
    if set(mine) != plan_ids:
        bad("independently regenerated run matrix differs from the manifest's")
    else:
        seed_diff = [(rid, mine[rid]["seed"], plan[rid]["seed"])
                     for rid in mine if mine[rid]["seed"] != plan[rid]["seed"]]
        temp_diff = [rid for rid in mine
                     if mine[rid]["temperature"] != plan[rid]["temperature"]]
        if seed_diff:
            bad(f"{len(seed_diff)} seeds differ from my regeneration, "
                f"e.g. {seed_diff[:3]}")
        elif temp_diff:
            bad(f"{len(temp_diff)} temperatures differ from my regeneration")
        else:
            ok("2,300 seeds + temperatures regenerate byte-identically from "
               "MASTER_SEED=20260805 (arms share the per-repeat seed)")
    # paired-arm seed identity
    paired_bad = [rid for rid in plan if rid.startswith("single:")
                  and plan[rid]["seed"] != plan["mas:" + rid.split(":", 1)[1]]["seed"]]
    if paired_bad:
        bad(f"{len(paired_bad)} single/mas pairs do not share a seed")
    else:
        ok("single and mas share the seed for every (case, condition, repeat)")
    # fixed-seed conditions really fixed
    for cond, _b, _t, _r, fixed in CONDITIONS:
        if fixed is None:
            continue
        seeds = {r["seed"] for r in records if r["condition"] == cond}
        if seeds != {fixed}:
            bad(f"{cond} seeds are {sorted(seeds)[:5]}, expected {{{fixed}}}")
    ok("t0-fixed and pert-t0 use seed 42 on every run")
    for cond, _b, temp, _r, _f in CONDITIONS:
        temps = {r["temperature"] for r in records if r["condition"] == cond}
        if temps != {temp}:
            bad(f"{cond} temperatures {temps}, expected {{{temp}}}")
    ok("every condition's temperature matches the locked design")

    sub("1.5 model digest / ollama version / think / num_predict")
    digests = Counter(r.get("model_digest") for r in records)
    models = Counter(r.get("model") for r in records)
    versions = Counter(r.get("ollama_version") for r in records)
    thinks = Counter(r.get("think") for r in records)
    npred = Counter(r.get("num_predict") for r in records)
    caches = Counter(r.get("cache_policy") for r in records)
    print(f"   model          : {dict(models)}")
    print(f"   model_digest   : { {k[:16]: v for k, v in digests.items()} }")
    print(f"   ollama_version : {dict(versions)}")
    print(f"   think          : {dict(thinks)}")
    print(f"   num_predict    : {dict(npred)}")
    print(f"   cache_policy   : {dict(caches)}")
    for name, cnt, expected in (
        ("model_digest", digests, manifest["model_digest"]),
        ("ollama_version", versions, EXPECTED_OLLAMA),
        ("think", thinks, EXPECTED_THINK),
        ("num_predict", npred, EXPECTED_NUM_PREDICT),
        ("model", models, manifest["model"]),
        ("cache_policy", caches, manifest["config"]["cache_policy"]),
    ):
        if len(cnt) == 1 and next(iter(cnt)) == expected:
            ok(f"single {name} on all 2,300 runs = {expected!r}")
        else:
            bad(f"{name}: {dict(cnt)} (expected single value {expected!r})")
    if manifest["config"]["num_predict"] == EXPECTED_NUM_PREDICT and \
            manifest["config"]["think"] is True:
        ok("manifest config records think=true, num_predict=8192 (the "
           "documented single deviation from the locked 2048)")
    else:
        bad("manifest config does not record the pre-registered condition")

    sub("1.6 decision domain and journalled errors")
    dom = Counter(r.get("decision") for r in records)
    print(f"   decision values: {dict(dom)}")
    if set(dom) <= set(OUTCOMES):
        ok("every decision is in the locked domain "
           "{escalate, dismiss, investigate, malformed}")
    else:
        bad(f"out-of-domain decisions: {set(dom) - set(OUTCOMES)}")
    errs = [r for r in records if r.get("error")]
    print(f"   runs with a non-null error field: {len(errs)}")
    if errs:
        note(f"error kinds: {Counter(str(r['error'])[:60] for r in errs)}")
    nonjson = [r["run_id"] for r in records
               if not isinstance(r.get("tool_calls"), list)]
    if nonjson:
        bad(f"{len(nonjson)} runs have a non-list tool_calls")
    else:
        ok("tool_calls is a list on every run")

    sub("1.7 malformed count")
    n_malformed = dom.get("malformed", 0)
    print(f"   journalled malformed runs: {n_malformed} / {len(records)} "
          f"({n_malformed / len(records):.4f})")
    print("   report's own claim to check: 36")
    if n_malformed == 36:
        ok("malformed count matches the reported 36")
    else:
        bad(f"malformed count is {n_malformed}, report/brief claims 36")
    per = Counter((r["arm"], r["condition"]) for r in records
                  if r["decision"] == "malformed")
    for key in sorted(per):
        print(f"     {key[0]:6s} {key[1]:11s} {per[key]}")

    sub("1.8 re-extract every decision from raw_output (my own locked rule)")
    mismatches = []
    for r in records:
        mine_d = my_extract(r.get("raw_output"))
        if mine_d != r["decision"]:
            mismatches.append((r["run_id"], r["decision"], mine_d,
                               (r.get("raw_output") or "")[-120:]))
    print(f"   runs re-extracted: {len(records)}")
    print(f"   mismatches       : {len(mismatches)}")
    if mismatches:
        bad(f"{len(mismatches)} journalled decisions do not reproduce from "
            f"raw_output under the locked rule")
        for m in mismatches[:10]:
            print(f"     {m[0]}: journal={m[1]} mine={m[2]} tail={m[3]!r}")
    else:
        ok("all 2,300 journalled decisions reproduce exactly from raw_output")

    # ======================================================================
    head("TASK 2 — FORENSIC A: did the 8192 budget fix the reporting-node starvation?")
    # ======================================================================
    sub("2.1 empty output")
    empty = [r for r in records if not (r.get("raw_output") or "").strip()]
    print(f"   runs with empty/whitespace raw_output: {len(empty)} / {len(records)}")
    if empty:
        ce = Counter((r["arm"], r["condition"]) for r in empty)
        for k in sorted(ce):
            print(f"     {k[0]:6s} {k[1]:11s} {ce[k]}")
        for r in empty[:5]:
            print(f"     e.g. {r['run_id']} completion_tokens="
                  f"{r.get('completion_tokens')}")
    else:
        ok("ZERO empty answers in 2,300 runs")

    sub("2.1b root cause of every empty answer "
        "(infrastructure error vs terminal-node starvation)")
    infra, starved, other = [], [], []
    for r in empty:
        no = r.get("node_outputs")
        if r.get("error"):
            infra.append(r)
        elif isinstance(no, dict) and not (no.get("reporting") or "").strip():
            starved.append(r)
        else:
            other.append(r)
    print(f"   empty WITH a journalled error (harness/server fault): {len(infra)}")
    print(f"     {Counter((r['arm'], str(r['error'])[:48]) for r in infra)}")
    print(f"   empty with NO error, MAS `reporting` node produced NOTHING "
          f"while upstream nodes did: {len(starved)}")
    for r in starved:
        no = r["node_outputs"]
        sizes = {k: len(no.get(k) or "") for k in
                 ("orchestrator", "data", "policy_risk", "reporting")}
        print(f"     {r['run_id']}  completion_tokens={r.get('completion_tokens')} "
              f"node_output_chars={sizes}")
    print(f"   empty with NO error and no node breakdown (single arm): {len(other)}")
    for r in other[:20]:
        print(f"     {r['run_id']}  completion_tokens={r.get('completion_tokens')} "
              f"tool_calls={len(r.get('tool_calls') or [])} "
              f"agent_messages={r.get('agent_messages')}")

    sub("2.2 malformed classification")
    mal = [r for r in records if r["decision"] == "malformed"]
    classes: Counter[str] = Counter()
    by_arm_class: Counter[tuple[str, str]] = Counter()
    examples: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in mal:
        cls, detail = classify_malformed(r.get("raw_output"),
                                         int(r.get("completion_tokens") or 0))
        classes[cls] += 1
        by_arm_class[(r["arm"], cls)] += 1
        if len(examples[cls]) < 4:
            examples[cls].append((r["run_id"], detail))
    print(f"   total malformed: {len(mal)}")
    for cls, n in classes.most_common():
        print(f"     {n:4d}  {cls}")
        for rid, d in examples[cls]:
            print(f"             {rid}  {d}")
    print("\n   by arm:")
    for arm in ARMS:
        tot = sum(v for (a, _), v in by_arm_class.items() if a == arm)
        print(f"     {arm}: {tot}")
        for (a, cls), v in sorted(by_arm_class.items()):
            if a == arm:
                print(f"        {v:4d}  {cls}")

    sub("2.3 budget-cap pressure (completion_tokens vs num_predict=8192)")
    at_cap = [r for r in records
              if int(r.get("completion_tokens") or 0) >= EXPECTED_NUM_PREDICT]
    print(f"   runs at/above the 8192 generation cap: {len(at_cap)}")
    ct = [int(r.get("completion_tokens") or 0) for r in records]
    ct_sorted = sorted(ct)
    print(f"   completion_tokens  max={max(ct)}  p99={ct_sorted[int(.99*len(ct))]}"
          f"  p95={ct_sorted[int(.95*len(ct))]}  median={ct_sorted[len(ct)//2]}")
    for arm in ARMS:
        a = [int(r.get("completion_tokens") or 0) for r in by_arm[arm]]
        print(f"   {arm:6s} mean={mean([float(x) for x in a]):.1f} max={max(a)}")
    mal_ct = [int(r.get("completion_tokens") or 0) for r in mal]
    good_ct = [int(r.get("completion_tokens") or 0) for r in records
               if r["decision"] != "malformed"]
    if mal_ct:
        print(f"   malformed runs: mean completion_tokens="
              f"{mean([float(x) for x in mal_ct]):.1f} "
              f"vs well-formed {mean([float(x) for x in good_ct]):.1f}")

    sub("2.4 sibling comparison — results-lfm2.5-8b-thinking (num_predict=2048)")
    try:
        sib = (read_jsonl(SIBLING_LFM / "journal-single.jsonl")
               + read_jsonl(SIBLING_LFM / "journal-mas.jsonl"))
        sib_man = json.loads((SIBLING_LFM / "manifest.json").read_text())
        sib_np = sib_man["config"]["num_predict"]
        sib_mal = [r for r in sib if r["decision"] == "malformed"]
        sib_classes: Counter[tuple[str, str]] = Counter()
        for r in sib_mal:
            cls, _ = classify_malformed(r.get("raw_output"),
                                        int(r.get("completion_tokens") or 0))
            sib_classes[(r["arm"], cls)] += 1
        sib_empty = [r for r in sib if not (r.get("raw_output") or "").strip()]
        sib_infra = [r for r in sib_empty if r.get("error")]
        sib_starved = [r for r in sib_empty if not r.get("error")]
        print(f"   sibling empty root cause: {len(sib_infra)} with a journalled "
              f"error, {len(sib_starved)} silent (budget starvation), "
              f"arms={Counter(r['arm'] for r in sib_starved)}")
        print(f"   sibling model={sib_man['model']} num_predict={sib_np} "
              f"think={sib_man['config']['think']} runs={len(sib)}")
        print(f"   sibling malformed: {len(sib_mal)}  empty: {len(sib_empty)}")
        for k in sorted(sib_classes):
            print(f"     {k[0]:6s} {sib_classes[k]:4d}  {k[1]}")
        print("\n   side by side (malformed per 2,300 runs):")
        print(f"     {'class':42s} {'qwen@8192':>10s} {'lfm@2048':>10s}")
        allc = sorted(set(classes) | {c for _, c in sib_classes})
        for c in allc:
            sib_n = sum(v for (_, cc), v in sib_classes.items() if cc == c)
            print(f"     {c:42s} {classes.get(c, 0):10d} {sib_n:10d}")
        print(f"     {'EMPTY OUTPUT (subset of above)':42s} "
              f"{len(empty):10d} {len(sib_empty):10d}")
    except Exception as exc:  # pragma: no cover
        note(f"sibling comparison unavailable: {exc}")

    # ======================================================================
    head("TASK 3 — FORENSIC B: channel integrity across all 2,300 raw outputs")
    # ======================================================================
    hits: list[tuple[str, list[str]]] = []
    for r in records:
        h = scan_channel(r.get("raw_output"))
        if h:
            hits.append((r["run_id"], h))
    print(f"   patterns scanned: {len(CHANNEL_PATTERNS)}")
    print(f"   runs scanned    : {len(records)}")
    print(f"   runs with a reasoning-channel marker in the ANSWER channel: "
          f"{len(hits)}  ({len(hits) / len(records):.5f})")
    if hits:
        bad(f"channel contamination in {len(hits)}/{len(records)} runs")
        marker_counts = Counter(m for _, ms in hits for m in ms)
        print(f"   markers: {dict(marker_counts)}")
        rec_by_id = {r["run_id"]: r for r in records}
        for rid, ms in hits[:20]:
            raw = rec_by_id[rid].get("raw_output") or ""
            print(f"\n   OFFENDER {rid}  markers={ms}")
            print(f"     decision={rec_by_id[rid]['decision']} "
                  f"completion_tokens={rec_by_id[rid].get('completion_tokens')}")
            print(f"     head: {raw[:300]!r}")
            print(f"     tail: {raw[-200:]!r}")
    else:
        ok("ZERO reasoning-channel markers in any of the 2,300 answer channels")
    # orphan-close analysis (the lfm failure mode)
    orphan = []
    for r in records:
        raw = r.get("raw_output") or ""
        n_open = len(re.findall(r"<\s*think\s*>", raw, re.IGNORECASE))
        n_close = len(re.findall(r"<\s*/\s*think\s*>", raw, re.IGNORECASE))
        if n_close > n_open:
            orphan.append((r["run_id"], n_open, n_close))
    print(f"\n   orphan closing </think> (close > open): {len(orphan)}")
    for o in orphan[:10]:
        print(f"     {o}")

    # ======================================================================
    head("TASK 4 — INDEPENDENT RECOMPUTATION vs analysis-report.md")
    # ======================================================================
    summaries: dict[tuple[str, str], dict[str, Any]] = {}
    for arm in ARMS:
        for cond, _b, _t, _r, _f in CONDITIONS:
            g = group_runs(records, arm, cond)
            g = {c: v for c, v in g.items() if len(v.decisions) >= 2}
            summaries[(arm, cond)] = summarise(g, labels) if g else {"cases": 0}

    # Values transcribed from analysis-report.md under audit.
    REPORTED: dict[tuple[str, str], dict[str, Any]] = {
        ("single", "t0-fixed"): {
            "pass^1": 0.560, "pass^5": 0.560, "DAR": 1.000,
            "krippendorff_alpha": 1.000, "flip_rate": 0.000,
            "majority_vote_accuracy": 0.560, "mean_entropy": 0.000,
            "TAR": 1.000, "jaccard": 1.000, "nLCS": 1.000,
            "malformed_rate": 0.000, "tokens_per_run": 9091.780,
            "tokens_per_pass^1": 16235.321, "tokens_per_pass^5": 16235.321,
            "mean_wall_clock_s": 27.639, "rouge_l_f1": 1.000},
        ("single", "t07-varied"): {
            "pass^1": 0.548, "pass^5": 0.177, "pass^15": 0.020, "DAR": 0.631,
            "krippendorff_alpha": 0.413, "flip_rate": 0.940,
            "majority_vote_accuracy": 0.640, "mean_entropy": 0.411,
            "TAR": 0.096, "jaccard": 0.767, "nLCS": 0.610,
            "malformed_rate": 0.019, "tokens_per_run": 9550.208,
            "tokens_per_pass^1": 17427.387, "tokens_per_pass^5": 54085.306,
            "tokens_per_pass^15": 477510.400, "mean_wall_clock_s": 28.120,
            "rouge_l_f1": 0.194},
        ("mas", "t0-fixed"): {
            "pass^1": 0.260, "pass^5": 0.260, "DAR": 1.000,
            "krippendorff_alpha": 1.000, "flip_rate": 0.000,
            "majority_vote_accuracy": 0.260, "mean_entropy": 0.000,
            "TAR": 0.992, "jaccard": 0.997, "nLCS": 0.999,
            "malformed_rate": 0.000, "tokens_per_run": 15284.088,
            "tokens_per_pass^1": 58784.954, "tokens_per_pass^5": 58784.954,
            "mean_wall_clock_s": 87.047, "rouge_l_f1": 0.994},
        ("mas", "t07-varied"): {
            "pass^1": 0.264, "pass^5": 0.067, "pass^15": 0.000, "DAR": 0.724,
            "krippendorff_alpha": 0.277, "flip_rate": 0.880,
            "majority_vote_accuracy": 0.220, "mean_entropy": 0.308,
            "TAR": 0.100, "jaccard": 0.709, "nLCS": 0.578,
            "malformed_rate": 0.017, "tokens_per_run": 17318.036,
            "tokens_per_pass^1": 65598.621, "tokens_per_pass^5": 256946.947,
            "mean_wall_clock_s": 75.596, "rouge_l_f1": 0.229},
        ("single", "pert-t0"): {
            "pass^1": 0.600, "pass^5": 0.600, "DAR": 1.000,
            "krippendorff_alpha": 1.000, "flip_rate": 0.000,
            "mean_entropy": 0.000, "rouge_l_f1": 1.000},
        ("single", "pert-t05"): {
            "pass^1": 0.500, "pass^5": 0.100, "DAR": 0.530,
            "krippendorff_alpha": 0.305, "flip_rate": 0.800,
            "mean_entropy": 0.411, "rouge_l_f1": 0.188},
        ("single", "pert-t10"): {
            "pass^1": 0.540, "pass^5": 0.200, "DAR": 0.590,
            "krippendorff_alpha": 0.406, "flip_rate": 0.700,
            "mean_entropy": 0.378, "rouge_l_f1": 0.150},
        ("mas", "pert-t0"): {
            "pass^1": 0.200, "pass^5": 0.200, "DAR": 1.000,
            "krippendorff_alpha": 1.000, "flip_rate": 0.000,
            "mean_entropy": 0.000, "rouge_l_f1": 1.000},
        ("mas", "pert-t05"): {
            "pass^1": 0.180, "pass^5": 0.100, "DAR": 0.680,
            "krippendorff_alpha": 0.299, "flip_rate": 0.600,
            "mean_entropy": 0.281, "rouge_l_f1": 0.249},
        ("mas", "pert-t10"): {
            "pass^1": 0.120, "pass^5": 0.000, "DAR": 0.690,
            "krippendorff_alpha": 0.295, "flip_rate": 0.600,
            "mean_entropy": 0.289, "rouge_l_f1": 0.207},
    }

    TOL = 0.005
    print(f"\n{'arm':7s} {'condition':11s} {'metric':26s} "
          f"{'reported':>13s} {'recomputed':>13s} {'|diff|':>11s}  flag")
    print("-" * 96)
    n_checked = n_flagged = 0
    for key in sorted(REPORTED):
        s = summaries[key]
        for metric, rep in REPORTED[key].items():
            got = s.get(metric)
            if got is None:
                bad(f"{key} {metric}: reported {rep} but I compute nothing")
                continue
            # token/wall-clock scale metrics: compare with a relative tolerance
            # too, since the report rounds to 3dp on values in the thousands.
            d = abs(got - rep)
            scale_metric = ("tokens" in metric or "wall_clock" in metric)
            flagged = (d > TOL) and not (scale_metric and d <= 0.0011 * max(1.0, abs(rep)))
            n_checked += 1
            if flagged:
                n_flagged += 1
            print(f"{key[0]:7s} {key[1]:11s} {metric:26s} "
                  f"{rep:13.3f} {got:13.3f} {d:11.6f}  "
                  f"{'<<< FLAG' if flagged else ''}")
    print("-" * 96)
    print(f"   metrics checked: {n_checked}; flagged (>|{TOL}| abs): {n_flagged}")
    if n_flagged:
        bad(f"{n_flagged} reported metrics differ from my recomputation by >{TOL}")
    else:
        ok(f"all {n_checked} reported metrics reproduce within {TOL} absolute")

    sub("4.1 majority-vote tie-break sensitivity (convention check)")
    for key in (("single", "t0-fixed"), ("single", "t07-varied"),
                ("mas", "t0-fixed"), ("mas", "t07-varied")):
        s = summaries[key]
        print(f"   {key[0]:6s} {key[1]:11s} canonical={s['majority_vote_accuracy']:.3f} "
              f"first-observed={s['majority_vote_accuracy_first_observed']:.3f} "
              f"ties={s['majority_ties']}")

    report_text = (TARGET / "analysis-report.md").read_text()
    if re.search(r"ties break by first-observed", report_text, re.IGNORECASE):
        bad("analysis-report.md preamble still states 'Majority-vote ties break "
            "by first-observed decision'; the code (and the 2026-08-12 doc "
            "correction) uses CANONICAL OUTCOMES order. Prose only — no number "
            "in this sweep changes (see 4.1).")
    else:
        ok("report prose describes the canonical tie-break convention")

    sub("4.2 worst-entropy cases")
    for key in (("single", "t07-varied"), ("mas", "t07-varied")):
        print(f"   {key[0]:6s}: {summaries[key]['worst_entropy_cases']}")

    # ======================================================================
    head("TASK 5 — ARM-DIFFERENCE STATISTICS (single − mas, t07-varied)")
    # ======================================================================
    per_case: dict[str, dict[str, dict[str, float]]] = {}
    for arm in ARMS:
        g = group_runs(records, arm, "t07-varied")
        per_case[arm] = {
            c: {
                "pass_fraction": sum(d == labels[c] for d in v.decisions) / len(v.decisions),
                "DAR": my_dar(v.decisions),
                "entropy": my_entropy(v.decisions),
            }
            for c, v in g.items() if len(v.decisions) >= 2
        }
    shared = sorted(set(per_case["single"]) & set(per_case["mas"]))
    print(f"   paired cases: {len(shared)}")
    REPORTED_STATS = {
        "pass_fraction": (0.284, (0.172, 0.396), 0.000),
        "DAR": (-0.093, (-0.150, -0.037), 0.002),
        "entropy": (0.102, (0.044, 0.162), 0.001),
    }
    print(f"\n   {'metric':15s} {'rep.diff':>9s} {'my diff':>9s} "
          f"{'rep. CI':>18s} {'my CI (seed=1)':>18s} {'rep.p':>7s} {'my p':>7s}")
    for metric, (rd, rci, rp) in REPORTED_STATS.items():
        diffs = [per_case["single"][c][metric] - per_case["mas"][c][metric]
                 for c in shared]
        md = mean(diffs)
        lo, hi = my_bootstrap_ci(diffs, seed=1)
        p = my_permutation_p(diffs, seed=1)
        print(f"   {metric:15s} {rd:9.3f} {md:9.3f} "
              f"{f'[{rci[0]:.3f}, {rci[1]:.3f}]':>18s} "
              f"{f'[{lo:.3f}, {hi:.3f}]':>18s} {rp:7.3f} {p:7.3f}")
        if abs(md - rd) > TOL:
            bad(f"arm-diff {metric}: reported {rd}, I compute {md:.4f}")
        if abs(lo - rci[0]) > TOL or abs(hi - rci[1]) > TOL:
            bad(f"arm-diff {metric}: CI differs "
                f"(reported [{rci[0]}, {rci[1]}], mine [{lo:.3f}, {hi:.3f}])")
        if abs(p - rp) > TOL:
            bad(f"arm-diff {metric}: p differs (reported {rp}, mine {p:.4f})")
    # seed-stability: the point estimate must not depend on the RNG seed
    print("\n   seed-stability of my CI/p (seeds 1..5):")
    for metric in REPORTED_STATS:
        diffs = [per_case["single"][c][metric] - per_case["mas"][c][metric]
                 for c in shared]
        cis = [my_bootstrap_ci(diffs, seed=s) for s in range(1, 6)]
        ps = [my_permutation_p(diffs, seed=s) for s in range(1, 6)]
        print(f"     {metric:15s} CI lo {min(c[0] for c in cis):.3f}.."
              f"{max(c[0] for c in cis):.3f}  hi {min(c[1] for c in cis):.3f}.."
              f"{max(c[1] for c in cis):.3f}  p {min(ps):.4f}..{max(ps):.4f}")

    # ======================================================================
    head("TASK 6 — LABELLED CONTEXT: sealed thinking-off qwen3.5:9b (results/)")
    # ======================================================================
    sealed_man = json.loads((SEALED_THINKING_OFF / "manifest.json").read_text())
    sealed = (read_jsonl(SEALED_THINKING_OFF / "journal-single.jsonl")
              + read_jsonl(SEALED_THINKING_OFF / "journal-mas.jsonl"))
    print("   factor table (sealed thinking-off  ->  this sweep):")
    factors = [
        ("model", sealed_man["model"], manifest["model"]),
        ("model_digest", sealed_man["model_digest"][:16],
         manifest["model_digest"][:16]),
        ("think", sealed_man["config"]["think"], manifest["config"]["think"]),
        ("num_predict", sealed_man["config"]["num_predict"],
         manifest["config"]["num_predict"]),
        ("num_ctx", sealed_man["config"]["num_ctx"], manifest["config"]["num_ctx"]),
        ("ollama_version", sealed_man["ollama_version"], manifest["ollama_version"]),
        ("cache_policy", sealed_man["config"].get("cache_policy", "<absent: harness v1>"),
         manifest["config"]["cache_policy"]),
        ("master_seed", sealed_man["config"]["master_seed"],
         manifest["config"]["master_seed"]),
        ("git_sha", sealed_man.get("git_sha", "?")[:12], manifest["git_sha"][:12]),
        ("config_hash", sealed_man["config_hash"][:12], manifest["config_hash"][:12]),
        ("runs", len(sealed), len(records)),
    ]
    differing = []
    for name, a, b in factors:
        same = (a == b)
        if not same and name != "config_hash":
            differing.append(name)
        print(f"     {name:16s} {str(a):20s} -> {str(b):20s} "
              f"{'SAME' if same else 'DIFFERS'}")
    print(f"\n   factors that differ (excluding the derived config_hash): "
          f"{differing}")
    # seed schedule identity
    s_seeds = {r["run_id"]: r["seed"] for r in sealed}
    t_seeds = {r["run_id"]: r["seed"] for r in records}
    if s_seeds == t_seeds:
        ok("seed schedule is identical run-for-run to the sealed sweep")
    else:
        bad("seed schedules differ between the sealed sweep and this one")

    print("\n   Tier 1, side by side (LABELLED CONTEXT ONLY — confounded):")
    print(f"   {'arm':7s} {'condition':11s} "
          f"{'pass^1':>16s} {'DAR':>16s} {'alpha':>16s} {'flip':>16s} "
          f"{'tok/run':>16s}")
    for arm in ARMS:
        for cond in ("t0-fixed", "t07-varied"):
            g_s = group_runs(sealed, arm, cond)
            g_s = {c: v for c, v in g_s.items() if len(v.decisions) >= 2}
            ss = summarise(g_s, labels)
            ts = summaries[(arm, cond)]
            def pair(k):
                a, b = ss.get(k), ts.get(k)
                return f"{a:.3f}->{b:.3f}" if a is not None and b is not None else "-"
            print(f"   {arm:7s} {cond:11s} "
                  f"{pair('pass^1'):>16s} {pair('DAR'):>16s} "
                  f"{pair('krippendorff_alpha'):>16s} {pair('flip_rate'):>16s} "
                  f"{pair('tokens_per_run'):>16s}")
    sealed_mal = Counter(r["decision"] for r in sealed).get("malformed", 0)
    print(f"\n   malformed: sealed {sealed_mal}/2300 -> this sweep "
          f"{n_malformed}/2300")

    sub("6.1 sizing the UNDECLARED third factor (Ollama version / harness rev)")
    ctx2 = EXPERIMENTS / "results-qwen3.5-9b-ollama0326"
    if ctx2.exists():
        c2_man = json.loads((ctx2 / "manifest.json").read_text())
        c2 = (read_jsonl(ctx2 / "journal-single.jsonl")
              + read_jsonl(ctx2 / "journal-mas.jsonl"))
        print(f"   both thinking-OFF at num_predict=2048, same digest; only the "
              f"infra context differs: {sealed_man['ollama_version']} -> "
              f"{c2_man['ollama_version']}")
        print(f"   {'arm':7s} {'condition':11s} {'pass^1':>16s} {'DAR':>16s} "
              f"{'alpha':>16s} {'flip':>16s}")
        for arm in ARMS:
            for cond in ("t0-fixed", "t07-varied"):
                a = summarise({c: v for c, v in
                               group_runs(sealed, arm, cond).items()
                               if len(v.decisions) >= 2}, labels)
                b = summarise({c: v for c, v in
                               group_runs(c2, arm, cond).items()
                               if len(v.decisions) >= 2}, labels)

                def pr(k):
                    return f"{a[k]:.3f}->{b[k]:.3f}"
                print(f"   {arm:7s} {cond:11s} {pr('pass^1'):>16s} "
                      f"{pr('DAR'):>16s} {pr('krippendorff_alpha'):>16s} "
                      f"{pr('flip_rate'):>16s}")
        note("An Ollama-version-only change (0.31.1 -> 0.32.6), holding think "
             "and num_predict fixed, already moves Tier 1 by the magnitudes "
             "printed above. The thinking-off baseline in results/ therefore "
             "differs from this sweep in THREE registered factors (think, "
             "num_predict, ollama_version) plus the harness revision, not the "
             "two named in the 2026-08-12 pre-registration.")

    # ======================================================================
    head("VERDICT")
    # ======================================================================
    if FAILURES:
        print(f"   {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"     - {f}")
    else:
        print("   No check failed.")
    if NOTES:
        print(f"\n   {len(NOTES)} note(s):")
        for n in NOTES:
            print(f"     - {n}")


if __name__ == "__main__":
    main()
