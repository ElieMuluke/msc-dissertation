#!/usr/bin/env python
"""Independent audit of the lfm2.5:8b@think PRD-A repeatability sweep.

Auditor with no prior involvement in this sweep. Every check below is written
from scratch against the raw journals, the manifest, the ground-truth label
files and the pre-registered design documents. Nothing from the project's
analysis pipeline (analysis/metrics.py, analysis/report.py, analysis/stats.py)
is imported or executed; the prior audit scripts in this directory were read
for the JOURNAL SCHEMA only.

Metric definitions were taken from the pre-registered sources, not from code:
  * docs/PRD-A-experiment.md            (tier hierarchy, journal schema)
  * docs/METRICS-PROVENANCE.md          (formula for every metric)
  * results-lfm2.5-8b-thinking/analysis-report.md (the two documented
    reporting conventions, restated below)
  * experiments/CHANGELOG.md 2026-08-11 (evening/night) and 2026-08-12
    (overnight)                         (thinking-on track design and the
    INVERTED gate criterion audited in section 2)

Conventions applied throughout (as documented in the report under audit):
  * 'malformed' is an outcome category, present in every metric; it never
    matches a ground-truth label, but malformed==malformed counts as
    AGREEMENT in DAR / Krippendorff alpha / entropy (category equality);
  * majority-vote ties break in favour of the first-observed decision.

Sweep-specific context:
  * THINKING-ON track: wire think=true, Ollama 0.32.9, model lfm2.5:8b.
  * The pre-registered gate criterion is INVERTED for this track: reasoning
    must arrive on a SEPARATE channel and the scored answer content must be
    free of inline reasoning markup. Section 2 tests that on all 2,300 runs.
  * The report under audit claims 144 malformed runs.
  * lfm2.5:8b has NO thinking-off counterpart by construction, so every
    comparison against the sealed corpus is CROSS-MODEL and confounded.

Sections
  1. INTEGRITY        counts vs manifest, duplicate/missing keys, per-run
                      field conformance, independent seed-schedule
                      regeneration, single digest / single ollama version,
                      think==true everywhere, decision domain, decision
                      re-extraction from raw_output, malformed accounting.
  2. FORENSICS        thinking-channel contamination scan over all 2,300
                      raw_output values (plus MAS node_outputs), and a
                      cause-by-cause + (arm, condition) breakdown of the
                      malformed runs with a generation-cap correlation test.
  3. METRICS          independent recomputation of every table in
                      analysis-report.md; flag |diff| > 0.005 (relative
                      0.1% for token-scale quantities).
  4. STATS            arm-difference table (single - mas, t07-varied):
                      per-case paired mean, percentile bootstrap 95% CI over
                      cases, paired sign-flip permutation p, worst-entropy
                      cases.
  5. CROSS-MODEL      Tier 1 of this sweep beside Tier 1 recomputed from the
                      raw journals of the four sealed thinking-OFF sweeps.
                      Labelled CROSS-MODEL and therefore confounded.

Run:
  cd backend && .venv/bin/python experiments/analysis/independent_check_lfm25_thinking.py
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

EXP = Path("/home/el/projects/msc-dissertation/backend/experiments")
RES = EXP / "results-lfm2.5-8b-thinking"
ALERTS = Path(
    "/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json"
)
PERT = EXP / "perturbation_cases.json"

DECISIONS = ("escalate", "dismiss", "investigate")
OUTCOMES = DECISIONS + ("malformed",)
DOMAIN = set(OUTCOMES)
ENT_NORM = math.log2(4.0)  # 4 outcome categories including malformed

EXPECTED_MODEL = "lfm2.5:8b"
EXPECTED_OLLAMA = "0.32.9"
EXPECTED_MALFORMED = 144  # claimed by analysis-report.md
MASTER_SEED = 20260805
FIXED_SEED = 42
ARMS = ("single", "mas")

TOL = 0.005  # absolute tolerance, as instructed
TOL_REL = 0.001  # relative tolerance for token / wall-clock scale numbers

# The pre-registered condition plan (PRD-A; identical to the sealed corpus).
PLAN = [
    # name, block, temperature, repeats, fixed_seed
    ("t0-fixed", "primary", 0.0, 5, FIXED_SEED),
    ("t07-varied", "primary", 0.7, 15, None),
    ("pert-t0", "perturbation", 0.0, 5, FIXED_SEED),
    ("pert-t05", "perturbation", 0.5, 5, None),
    ("pert-t10", "perturbation", 1.0, 5, None),
]

FAILURES: list[str] = []
NOTES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"  [FAIL] {msg}")


def note(msg: str) -> None:
    NOTES.append(msg)
    print(f"  [NOTE] {msg}")


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def hdr(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def sub(title: str) -> None:
    print()
    print(f"-- {title}")


# --------------------------------------------------------------- io helpers


def read_journal(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                fail(f"{path.name} line {i}: unparseable JSON ({exc})")
    return rows


def read_labels() -> dict[str, str]:
    lab: dict[str, str] = {}
    for a in json.load(open(ALERTS, encoding="utf-8"))["alerts"]:
        lab[a["alert_id"]] = a["ground_truth"]
    for a in json.load(open(PERT, encoding="utf-8"))["alerts"]:
        lab[a["alert_id"]] = a["ground_truth"]
    return lab


def case_order() -> tuple[list[str], list[str]]:
    """Case id order as it appears in the two source files (file order)."""
    primary = [a["alert_id"] for a in json.load(open(ALERTS, encoding="utf-8"))["alerts"]]
    pert = [a["alert_id"] for a in json.load(open(PERT, encoding="utf-8"))["alerts"]]
    return primary, pert


# ------------------------------------------------- own decision extraction
# Re-implementation of the locked PRD-A rule from its prose specification
# (harness/extraction.py docstring), written independently:
#   only the LAST non-empty line is examined; markdown emphasis chars
#   (* _ ` #) are stripped from it; one trailing '.' or '!' tolerated;
#   case-insensitive; the line must contain nothing else. Anything else is
#   'malformed'.

_CONTRACT = re.compile(
    r"\AFINAL\s+DECISION\s*:\s*(escalate|dismiss|investigate)\s*[.!]?\Z", re.IGNORECASE
)


def my_extract(text: str | None) -> str:
    if not text:
        return "malformed"
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return "malformed"
    last = re.sub(r"[*_`#]", "", lines[-1]).strip()
    m = _CONTRACT.match(last)
    return m.group(1).lower() if m else "malformed"


# ------------------------------------------------------------ own LCS / ROUGE


def lcs_len(a: list, b: list) -> int:
    """Classic O(n*m) DP longest-common-subsequence length, own code."""
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


def rouge_l_f1(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    l = lcs_len(a, b)
    if l == 0:
        return 0.0
    p = l / len(a)
    r = l / len(b)
    return 2 * p * r / (p + r)


# ---------------------------------------------------------------- metrics


def comb(n: int, k: int) -> float:
    return math.comb(n, k) if 0 <= k <= n else 0.0


def pass_at_k(per_case: list[tuple[int, int]], k: int) -> float | None:
    """per_case = [(n_repeats, n_label_agreeing)]; C(c,k)/C(n,k), mean over cases."""
    vals = []
    for n, c in per_case:
        if k > n:
            return None
        vals.append(comb(c, k) / comb(n, k))
    return sum(vals) / len(vals) if vals else None


def pairwise_agreement(labels: list[str]) -> float:
    """Fraction of agreeing unordered pairs (category equality, malformed included)."""
    n = len(labels)
    if n < 2:
        return 1.0
    cnt = Counter(labels)
    same = sum(v * (v - 1) // 2 for v in cnt.values())
    return same / (n * (n - 1) // 2)


def norm_entropy(labels: list[str]) -> float:
    n = len(labels)
    if n == 0:
        return 0.0
    cnt = Counter(labels)
    h = -sum((v / n) * math.log2(v / n) for v in cnt.values() if v)
    return h / ENT_NORM


def krippendorff_alpha_nominal(units: list[list[str]]) -> float:
    """Nominal-level Krippendorff alpha, standard coincidence formulation.

    Do = (1/n) * sum_u [ 1/(m_u - 1) * sum_{c != k} n_uc * n_uk ]
    De = (1/(n*(n-1))) * sum_{c != k} n_c * n_k
    alpha = 1 - Do/De        with n = total number of values.
    """
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
        # sum_{c != k} n_c n_k  ==  m^2 - sum_c n_c^2
        cross = m * m - sum(v * v for v in cnt.values())
        do += cross / (m - 1)
    do /= n_total
    cross_g = n_total * n_total - sum(v * v for v in glob.values())
    de = cross_g / (n_total * (n_total - 1))
    if de == 0:
        return float("nan")
    return 1.0 - do / de


def majority(labels: list[str]) -> str:
    """Modal outcome; ties break by first-observed decision."""
    cnt = Counter(labels)
    top = max(cnt.values())
    for lab in labels:  # first-observed order
        if cnt[lab] == top:
            return lab
    return labels[0]


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def nlcs(a: list, b: list) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return lcs_len(a, b) / max(len(a), len(b))


# ------------------------------------------------------------- 1. INTEGRITY

hdr("SECTION 1 - INTEGRITY")

manifest = json.load(open(RES / "manifest.json", encoding="utf-8"))
journals = {arm: read_journal(RES / f"journal-{arm}.jsonl") for arm in ARMS}
labels = read_labels()
primary_ids, pert_ids = case_order()

sub("1.1 line counts vs manifest totals")
for arm in ARMS:
    got, want = len(journals[arm]), manifest["totals"][arm]
    (ok if got == want else fail)(f"journal-{arm}.jsonl lines={got} manifest totals={want}")
total_rows = sum(len(journals[a]) for a in ARMS)
(ok if total_rows == 2300 else fail)(f"total journal rows = {total_rows} (planned 2300)")
(ok if len(manifest["runs"]) == 2300 else fail)(
    f"manifest.runs entries = {len(manifest['runs'])} (planned 2300)"
)
prog = json.load(open(RES / "progress.json", encoding="utf-8"))
(ok if prog["done"] == prog["total"] == 2300 else fail)(
    f"progress.json done={prog['done']}/{prog['total']}"
)

sub("1.2 duplicate / missing run keys")
plan_by_id = {r["run_id"]: r for r in manifest["runs"]}
all_rows = [r for arm in ARMS for r in journals[arm]]
seen = Counter(r["run_id"] for r in all_rows)
dups = {k: v for k, v in seen.items() if v > 1}
(ok if not dups else fail)(f"duplicate run_ids: {len(dups)}" + (f" -> {list(dups)[:5]}" if dups else ""))
missing = sorted(set(plan_by_id) - set(seen))
extra = sorted(set(seen) - set(plan_by_id))
(ok if not missing else fail)(f"planned runs missing from journals: {len(missing)}")
(ok if not extra else fail)(f"journal runs absent from manifest: {len(extra)}")

sub("1.3 independent regeneration of the manifest seed schedule")
# Seeds are derived from MASTER_SEED alone, consumed per (condition, case,
# repeat) and SHARED by both arms (harness/manifest.py prose). Regenerated
# here from the pre-registered constants without importing the harness.
rng = random.Random(MASTER_SEED)
regen: dict[str, dict] = {}
for name, block, temp, repeats, fixed in PLAN:
    ids = primary_ids if block == "primary" else pert_ids
    for case_id in ids:
        for ridx in range(repeats):
            seed = fixed if fixed is not None else rng.randrange(2**31)
            for arm in ARMS:
                regen[f"{arm}:{case_id}:{name}:{ridx}"] = {
                    "arm": arm,
                    "case_id": case_id,
                    "block": block,
                    "condition": name,
                    "repeat_idx": ridx,
                    "seed": seed,
                    "temperature": temp,
                }
(ok if len(regen) == 2300 else fail)(f"regenerated plan size = {len(regen)}")
seed_mismatch = [
    rid
    for rid, r in plan_by_id.items()
    if rid not in regen or regen[rid]["seed"] != r["seed"]
]
(ok if not seed_mismatch else fail)(
    f"manifest seeds vs independently regenerated schedule: {len(seed_mismatch)} mismatches"
)
field_mismatch = [
    rid
    for rid, r in plan_by_id.items()
    if rid in regen
    and any(regen[rid][k] != r[k] for k in ("arm", "case_id", "block", "condition", "repeat_idx", "temperature"))
]
(ok if not field_mismatch else fail)(
    f"manifest plan fields vs regenerated schedule: {len(field_mismatch)} mismatches"
)
# arms share the same seed for a given (condition, case, repeat)
shared_bad = [
    rid
    for rid in plan_by_id
    if rid.startswith("single:")
    and plan_by_id[rid]["seed"] != plan_by_id.get("mas:" + rid.split(":", 1)[1], {}).get("seed")
]
(ok if not shared_bad else fail)(f"single/mas seed sharing violations: {len(shared_bad)}")

sub("1.4 per-run field conformance (journal vs manifest plan)")
bad_fields = Counter()
examples: dict[str, str] = {}
for r in all_rows:
    p = plan_by_id.get(r["run_id"])
    if p is None:
        continue
    for k in ("arm", "case_id", "block", "condition", "repeat_idx", "seed", "temperature"):
        if r.get(k) != p[k]:
            bad_fields[k] += 1
            examples.setdefault(k, r["run_id"])
    # run_id must be self-consistent with its own fields
    if r["run_id"] != f"{r['arm']}:{r['case_id']}:{r['condition']}:{r['repeat_idx']}":
        bad_fields["run_id_composition"] += 1
        examples.setdefault("run_id_composition", r["run_id"])
if bad_fields:
    for k, v in bad_fields.items():
        fail(f"field '{k}': {v} mismatches (e.g. {examples[k]})")
else:
    ok("all 2300 rows match the manifest on arm/case/block/condition/repeat/seed/temperature")
# each journal file holds only its own arm
for arm in ARMS:
    wrong = sum(1 for r in journals[arm] if r["arm"] != arm)
    (ok if wrong == 0 else fail)(f"journal-{arm}.jsonl rows with arm != {arm}: {wrong}")

sub("1.5 model / digest / ollama version / think")
digests = Counter(r["model_digest"] for r in all_rows)
models = Counter(r["model"] for r in all_rows)
versions = Counter(r["ollama_version"] for r in all_rows)
thinks = Counter(repr(r.get("think")) for r in all_rows)
(ok if len(digests) == 1 else fail)(f"distinct model_digest values: {len(digests)} -> {dict(digests)}")
(ok if list(digests) == [manifest["model_digest"]] else fail)(
    "journal digest == manifest digest"
)
(ok if list(models) == [EXPECTED_MODEL] else fail)(f"models: {dict(models)}")
(ok if list(versions) == [EXPECTED_OLLAMA] else fail)(f"ollama_version: {dict(versions)}")
(ok if manifest["ollama_version"] == EXPECTED_OLLAMA else fail)(
    f"manifest ollama_version = {manifest['ollama_version']}"
)
n_think_true = sum(1 for r in all_rows if r.get("think") is True)
(ok if n_think_true == 2300 else fail)(
    f"think is True on {n_think_true}/2300 rows (values seen: {dict(thinks)})"
)
(ok if manifest["config"].get("think") is True else fail)(
    f"manifest.config.think = {manifest['config'].get('think')}"
)
ok(f"manifest config_hash = {manifest['config_hash'][:12]}, num_predict = {manifest['config']['num_predict']}, num_ctx = {manifest['config']['num_ctx']}")
caps = manifest.get("model_show", {}).get("capabilities", [])
(ok if "thinking" in caps else fail)(f"model advertises capabilities {caps}")
cache = Counter(r.get("cache_policy") for r in all_rows)
(ok if list(cache) == ["none"] else fail)(f"cache_policy: {dict(cache)}")

sub("1.6 decision domain and label coverage")
outside = Counter(r["decision"] for r in all_rows if r["decision"] not in DOMAIN)
(ok if not outside else fail)(f"decisions outside {sorted(DOMAIN)}: {dict(outside)}")
cases_seen = {r["case_id"] for r in all_rows}
unlabelled = sorted(c for c in cases_seen if c not in labels)
(ok if not unlabelled else fail)(f"cases with no ground-truth label: {unlabelled}")
(ok if len(primary_ids) == 50 else fail)(f"primary cases in alerts.json: {len(primary_ids)}")
(ok if len(pert_ids) == 10 else fail)(f"perturbation cases: {len(pert_ids)}")
bad_gt = {c: labels[c] for c in cases_seen if labels.get(c) not in DECISIONS}
(ok if not bad_gt else fail)(f"ground-truth values outside the decision ontology: {bad_gt}")

sub("1.7 decision re-extraction from raw_output (locked FINAL DECISION rule)")
mismatch = [
    (r["run_id"], r["decision"], my_extract(r.get("raw_output")))
    for r in all_rows
    if my_extract(r.get("raw_output")) != r["decision"]
]
(ok if not mismatch else fail)(
    f"journal decision != independently re-extracted decision: {len(mismatch)}"
)
for rid, j, m in mismatch[:10]:
    print(f"         {rid}: journal={j} recomputed={m}")

sub("1.8 malformed accounting")
malformed_rows = [r for r in all_rows if r["decision"] == "malformed"]
n_mal = len(malformed_rows)
print(f"       malformed runs = {n_mal} / 2300 = {n_mal / 2300:.4f} ({n_mal / 2300 * 100:.2f}%)")
(ok if n_mal == EXPECTED_MALFORMED else fail)(
    f"malformed count {n_mal} vs report claim {EXPECTED_MALFORMED}"
)
errs = Counter(r.get("error") for r in all_rows if r.get("error") is not None)
(ok if not errs else note)(f"rows with non-null error: {sum(errs.values())} {dict(errs)}")

sub("1.9 field sanity (tokens, wall clock, timestamps)")
neg = [
    r["run_id"]
    for r in all_rows
    if r["prompt_tokens"] < 0 or r["completion_tokens"] < 0 or r["wall_clock_s"] < 0
]
(ok if not neg else fail)(f"negative token/wall-clock values: {len(neg)}")
zero_prompt = [r["run_id"] for r in all_rows if r["prompt_tokens"] == 0]
(ok if not zero_prompt else note)(f"rows with prompt_tokens == 0: {len(zero_prompt)}")
ts_bad = [r["run_id"] for r in all_rows if not re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", r["started_at"])]
(ok if not ts_bad else fail)(f"malformed started_at timestamps: {len(ts_bad)}")
starts = sorted(r["started_at"] for r in all_rows)
ok(f"run window: {starts[0]} -> {starts[-1]} (UTC)")


# ------------------------------------------------------------ 2. FORENSICS

hdr("SECTION 2 - THINKING-CHANNEL FORENSICS AND MALFORMED CHARACTERISATION")

sub("2.1 inline reasoning markup in the scored answer channel (raw_output)")
# The pre-registered INVERTED criterion (CHANGELOG 2026-08-11 evening):
# reasoning must be emitted on a SEPARATE channel and the answer content must
# be free of inline reasoning markup. Scan is deliberately broad: the literal
# tags observed for this model under think:false, plus the common alternatives
# used by other reasoning models, plus a catch-all for any XML-ish or
# harmony-style tag whose name mentions think/reason/analysis/channel.
MARKUP_PATTERNS = {
    "<think>": re.compile(r"<think\s*>", re.I),
    "</think>": re.compile(r"</\s*think\s*>", re.I),
    "<thinking>": re.compile(r"</?\s*thinking\s*>", re.I),
    "<reasoning>": re.compile(r"</?\s*reasoning\s*>", re.I),
    "<analysis>/<final> (harmony)": re.compile(r"<\|(?:start|end|channel|message)\|>|<\|analysis\|>|<\|final\|>", re.I),
    "unicode think delims": re.compile(r"[\u25c1\u25b7\u25c0\u25b6]\s*/?\s*think\s*[\u25b7\u25c1\u25b6\u25c0]", re.I),
    "[THINK]/[/THINK]": re.compile(r"\[/?\s*(?:think|thinking|reasoning)\s*\]", re.I),
    "catch-all tag": re.compile(r"</?[a-z_|]*(?:think|reason|analysis|channel)[a-z_|]*\s*/?>", re.I),
}
contaminated: list[tuple[str, str, str, str]] = []
for r in all_rows:
    text = r.get("raw_output") or ""
    hits = sorted({name for name, pat in MARKUP_PATTERNS.items() if pat.search(text)})
    if hits:
        contaminated.append((r["run_id"], ",".join(hits), r["decision"], text))
print(f"       raw_output values scanned: {len(all_rows)}")
if contaminated:
    fail(
        f"INLINE REASONING MARKUP FOUND in {len(contaminated)}/2300 raw_output values "
        "-- violates the pre-registered inverted criterion"
    )
    for rid, hits, dec, text in contaminated:
        row = next(r for r in all_rows if r["run_id"] == rid)
        # locate the tag and show its immediate context
        m = re.search(r"</?\s*think\s*>", text, re.I)
        pos = m.start() if m else 0
        ctx = text[max(0, pos - 90) : pos + 40].replace("\n", "\\n")
        print(f"         run_id={rid}")
        print(f"           markup={hits}  decision={dec}  arm={row['arm']} condition={row['condition']}")
        print(f"           completion_tokens={row['completion_tokens']} agent_messages={row['agent_messages']}")
        print(f"           context: ...{ctx}...")
        print(f"           tail:    {text[-60:]!r}")
else:
    ok("no inline reasoning markup in any raw_output (criterion satisfied)")

sub("2.2 same scan over MAS intermediate node_outputs (context, not scored)")
node_hits: list[tuple[str, str]] = []
for r in journals["mas"]:
    no = r.get("node_outputs") or {}
    for node, text in no.items():
        if not text:
            continue
        if any(pat.search(text) for pat in MARKUP_PATTERNS.values()):
            node_hits.append((r["run_id"], node))
if node_hits:
    note(
        f"inline reasoning markup in {len(node_hits)} MAS intermediate node output(s) "
        "(not the scored channel, but it enters downstream nodes' context): "
        + ", ".join(f"{rid}[{n}]" for rid, n in node_hits)
    )
else:
    ok("no inline reasoning markup in any MAS node_outputs")

sub("2.3 malformed characterisation - cause taxonomy")


def classify_malformed(r: dict) -> str:
    """Cause taxonomy, decided from the raw text alone."""
    text = r.get("raw_output")
    if r.get("error"):
        return "A. harness error / timeout"
    if text is None:
        return "B. raw_output null"
    if text.strip() == "":
        return "B. empty answer channel (no content emitted)"
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    last = re.sub(r"[*_`#]", "", lines[-1]).strip()
    if any(_CONTRACT.match(re.sub(r"[*_`#]", "", ln).strip()) for ln in lines):
        return "C. valid contract line present but trailing content after it"
    if re.search(r"final\s+decision\s*:\s*(escalate|dismiss|investigate)\b", last, re.I):
        return "D. answer collapsed onto ONE line (prose + contract on the same line)"
    if re.search(r"final\s+decision\s*:", last, re.I):
        return "E. last line is FINAL DECISION: with an absent/invalid label"
    if re.search(r"final\s+decision", text, re.I):
        return "F. FINAL DECISION mentioned in the body only, never as the last line"
    if re.match(r"^decision\s*:\s*(escalate|dismiss|investigate)\b", last, re.I):
        return "G. wrong keyword: 'DECISION:' emitted without 'FINAL'"
    return "H. no decision statement at all (truncated mid-analysis / refusal)"


causes = Counter(classify_malformed(r) for r in malformed_rows)
print(f"       {'cause':<70} {'n':>5}  {'share':>7}")
for cause, n in sorted(causes.items()):
    print(f"       {cause:<70} {n:>5}  {n / max(n_mal, 1) * 100:>6.1f}%")
(ok if sum(causes.values()) == n_mal else fail)(
    f"cause taxonomy is exhaustive: {sum(causes.values())} classified of {n_mal}"
)

sub("2.4 malformed by (arm, condition)")
by_ac = Counter((r["arm"], r["condition"]) for r in malformed_rows)
tot_ac = Counter((r["arm"], r["condition"]) for r in all_rows)
print(f"       {'arm':<8} {'condition':<12} {'malformed':>9} {'runs':>6} {'rate':>8}")
for arm in ARMS:
    for name, _b, _t, _rep, _s in PLAN:
        key = (arm, name)
        if tot_ac[key]:
            print(
                f"       {arm:<8} {name:<12} {by_ac[key]:>9} {tot_ac[key]:>6} "
                f"{by_ac[key] / tot_ac[key]:>8.4f}"
            )

sub("2.5 malformed by cause x (arm, condition)")
cross = Counter((classify_malformed(r), r["arm"], r["condition"]) for r in malformed_rows)
for (cause, arm, cond), n in sorted(cross.items(), key=lambda kv: -kv[1]):
    print(f"       {n:>4}  {arm:<7} {cond:<12} {cause}")

sub("2.6 generation-cap correlation")
num_predict = manifest["config"]["num_predict"]
journal_has_np = any("num_predict" in r for r in all_rows)
print(f"       num_predict recorded in manifest.config = {num_predict}")
print(f"       num_predict recorded on journal lines   = {journal_has_np} "
      "(journal stores per-run totals only; the cap is per LLM call)")
print("       completion_tokens on a journal line is the SUM over that run's LLM calls,")
print("       so the cap shows up as a per-call ceiling, approximated below by")
print("       completion_tokens / agent_messages.")

print()
print("       (a) UNAMBIGUOUS cap hits: agent_messages == 1, so completion_tokens IS")
print("           the single call's output length.")
single_call = [r for r in all_rows if r.get("agent_messages") == 1]
capped = [r for r in single_call if r["completion_tokens"] == num_predict]
uncapped = [r for r in single_call if r["completion_tokens"] != num_predict]
print(f"           one-call runs: {len(single_call)}")
print(
    f"           of these, completion_tokens == {num_predict} exactly: {len(capped)} "
    f"-> malformed {sum(1 for r in capped if r['decision'] == 'malformed')}/{len(capped)}"
)
print(
    f"           the other one-call runs                       : {len(uncapped)} "
    f"-> malformed {sum(1 for r in uncapped if r['decision'] == 'malformed')}/{len(uncapped)}"
)
for r in capped:
    print(f"             {r['run_id']:<42} decision={r['decision']} cause={classify_malformed(r) if r['decision']=='malformed' else '-'}")
print()
print("       (b) EMPTY-ANSWER runs (the budget-exhaustion signature: reasoning")
print("           consumed the call, content came back empty).")
empty_rows = [r for r in all_rows if not (r.get("raw_output") or "").strip()]
base_med: dict[tuple, float] = {}
tmp: dict[tuple, list[int]] = defaultdict(list)
for r in all_rows:
    if (r.get("raw_output") or "").strip():
        tmp[(r["arm"], r["condition"], r["case_id"])].append(r["completion_tokens"])
for k, v in tmp.items():
    v.sort()
    base_med[k] = v[len(v) // 2]
excess = [
    r["completion_tokens"] - base_med[(r["arm"], r["condition"], r["case_id"])]
    for r in empty_rows
    if (r["arm"], r["condition"], r["case_id"]) in base_med
]
print(f"           empty-answer runs: {len(empty_rows)}  arms/conditions: "
      f"{dict(Counter((r['arm'], r['condition']) for r in empty_rows))}")
if excess:
    excess.sort()
    print(
        f"           excess completion_tokens vs the SAME case's well-formed median: "
        f"mean {sum(excess)/len(excess):+.0f}, median {excess[len(excess)//2]:+.0f}, "
        f"max {excess[-1]:+.0f}"
    )
    print("           -> empty answers cost MORE tokens than successful ones on the same")
    print("              case: the budget went to the thinking channel, not the answer.")
print()
print("       (c) per-call approximation over all runs")


def per_call(r: dict) -> float:
    n = max(int(r.get("agent_messages") or 0), 1)
    return r["completion_tokens"] / n


for arm in ARMS:
    rows = journals[arm]
    mal = [r for r in rows if r["decision"] == "malformed"]
    good = [r for r in rows if r["decision"] != "malformed"]
    def stat(rs, f):
        v = sorted(f(r) for r in rs)
        if not v:
            return "n/a"
        return f"n={len(v):<4} mean={sum(v)/len(v):>8.1f} med={v[len(v)//2]:>8.1f} p90={v[int(0.9*(len(v)-1))]:>8.1f} max={v[-1]:>8.1f}"
    print(f"       [{arm}] completion_tokens  malformed: {stat(mal, lambda r: r['completion_tokens'])}")
    print(f"       [{arm}] completion_tokens  well-formed: {stat(good, lambda r: r['completion_tokens'])}")
    print(f"       [{arm}] per-call approx    malformed: {stat(mal, per_call)}")
    print(f"       [{arm}] per-call approx    well-formed: {stat(good, per_call)}")
    # how many runs contain at least one call that plausibly hit the cap
    near = lambda r: per_call(r) >= 0.95 * num_predict  # noqa: E731
    nm = sum(1 for r in mal if near(r))
    ng = sum(1 for r in good if near(r))
    print(
        f"       [{arm}] mean per-call >= 95% of cap ({0.95 * num_predict:.0f}): "
        f"malformed {nm}/{len(mal)} = {nm / max(len(mal), 1):.3f}   "
        f"well-formed {ng}/{len(good)} = {ng / max(len(good), 1):.3f}"
    )

# point-biserial correlation between malformed and per-call token load
def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


for arm in ARMS:
    rows = journals[arm]
    y = [1.0 if r["decision"] == "malformed" else 0.0 for r in rows]
    print(
        f"       [{arm}] point-biserial r(malformed, completion_tokens) = "
        f"{pearson([float(r['completion_tokens']) for r in rows], y):+.3f}   "
        f"r(malformed, per-call approx) = {pearson([per_call(r) for r in rows], y):+.3f}"
    )

sub("2.7 malformed examples (tail of the output, one per cause)")
shown = set()
for r in malformed_rows:
    c = classify_malformed(r)
    if c in shown:
        continue
    shown.add(c)
    text = r.get("raw_output")
    tail = (text or "")[-260:].replace("\n", "\\n")
    print(f"       [{c}] {r['run_id']} len={len(text or '')} compl_tok={r['completion_tokens']} msgs={r['agent_messages']}")
    print(f"          ...{tail}")


# -------------------------------------------------------------- 3. METRICS

hdr("SECTION 3 - INDEPENDENT METRIC RECOMPUTATION")


def group(rows: list[dict]) -> dict[tuple[str, str], dict[str, list[dict]]]:
    """(arm, condition) -> case_id -> rows ordered by repeat_idx."""
    g: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        g[(r["arm"], r["condition"])][r["case_id"]].append(r)
    for key in g:
        for cid in g[key]:
            g[key][cid].sort(key=lambda r: r["repeat_idx"])
    return g


G = group(all_rows)


def condition_metrics(arm: str, cond: str) -> dict:
    cases = G[(arm, cond)]
    per_case_counts = []
    dar_vals, ent_vals, tar_vals, jac_vals, lcs_vals, rouge_vals = [], [], [], [], [], []
    flips = 0
    maj_hits = 0
    units = []
    n_mal = 0
    n_runs = 0
    toks = []
    walls = []
    per_case_pass = {}
    per_case_dar = {}
    per_case_ent = {}
    for cid, rows in sorted(cases.items()):
        decs = [r["decision"] for r in rows]
        gt = labels[cid]
        c = sum(1 for d in decs if d == gt)
        per_case_counts.append((len(decs), c))
        per_case_pass[cid] = c / len(decs)
        d = pairwise_agreement(decs)
        dar_vals.append(d)
        per_case_dar[cid] = d
        e = norm_entropy(decs)
        ent_vals.append(e)
        per_case_ent[cid] = e
        units.append(decs)
        if len(set(decs)) > 1:
            flips += 1
        if majority(decs) == gt:
            maj_hits += 1
        n_mal += sum(1 for x in decs if x == "malformed")
        n_runs += len(rows)
        toks.extend(r["prompt_tokens"] + r["completion_tokens"] for r in rows)
        walls.extend(r["wall_clock_s"] for r in rows)
        # trajectory metrics over the canonical trajectory = ordered tool names
        trajs = [list(r.get("tool_calls") or []) for r in rows]
        sets = [set(t) for t in trajs]
        texts = [(r.get("raw_output") or "").lower().split() for r in rows]
        pairs = list(combinations(range(len(rows)), 2))
        if pairs:
            tar_vals.append(sum(1 for i, j in pairs if trajs[i] == trajs[j]) / len(pairs))
            jac_vals.append(sum(jaccard(sets[i], sets[j]) for i, j in pairs) / len(pairs))
            lcs_vals.append(sum(nlcs(trajs[i], trajs[j]) for i, j in pairs) / len(pairs))
            rouge_vals.append(sum(rouge_l_f1(texts[i], texts[j]) for i, j in pairs) / len(pairs))
        else:
            tar_vals.append(1.0)
            jac_vals.append(1.0)
            lcs_vals.append(1.0)
            rouge_vals.append(1.0)
    mean = lambda v: sum(v) / len(v) if v else float("nan")  # noqa: E731
    tpr = mean(toks)
    out = {
        "cases": len(cases),
        "repeats": per_case_counts[0][0] if per_case_counts else 0,
        "pass^1": pass_at_k(per_case_counts, 1),
        "pass^5": pass_at_k(per_case_counts, 5),
        "pass^15": pass_at_k(per_case_counts, 15),
        "DAR": mean(dar_vals),
        "krippendorff_alpha": krippendorff_alpha_nominal(units),
        "flip_rate": flips / len(cases),
        "majority_vote_accuracy": maj_hits / len(cases),
        "mean_entropy": mean(ent_vals),
        "TAR": mean(tar_vals),
        "jaccard": mean(jac_vals),
        "nLCS": mean(lcs_vals),
        "malformed_rate": n_mal / n_runs,
        "rouge_l_f1": mean(rouge_vals),
        "tokens_per_run": tpr,
        "mean_wall_clock_s": mean(walls),
        "_pass": per_case_pass,
        "_dar": per_case_dar,
        "_ent": per_case_ent,
    }
    for k in (1, 5, 15):
        p = out[f"pass^{k}"]
        out[f"tokens_per_pass^{k}"] = (tpr / p) if p else (None if p is None else float("inf"))
    return out


MET = {(a, c): condition_metrics(a, c) for a in ARMS for c, *_ in PLAN}

# ---- parse the report under audit so the comparison is mechanical


def parse_report_tables(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    header: list[str] | None = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if cells[:2] == ["arm", "condition"]:
            header = cells
            continue
        if header and len(cells) == len(header) and cells[0] in ARMS:
            arm, cond = cells[0], cells[1]
            for name, val in zip(header[2:], cells[2:]):
                if val in ("", "-", "\u2014"):
                    continue
                try:
                    out[(arm, cond)][name] = float(val)
                except ValueError:
                    pass
    return out


REPORTED = parse_report_tables(RES / "analysis-report.md")

TABLES = [
    ("Tier 1 (headline)", ["pass^1", "pass^5", "pass^15", "DAR", "krippendorff_alpha", "flip_rate"],
     [("single", "t0-fixed"), ("single", "t07-varied"), ("mas", "t0-fixed"), ("mas", "t07-varied")]),
    ("Tier 2", ["majority_vote_accuracy", "mean_entropy", "TAR", "jaccard", "nLCS", "malformed_rate"],
     [("single", "t0-fixed"), ("single", "t07-varied"), ("mas", "t0-fixed"), ("mas", "t07-varied")]),
    ("Tier 3 (cost)", ["tokens_per_run", "tokens_per_pass^1", "tokens_per_pass^5", "tokens_per_pass^15", "mean_wall_clock_s"],
     [("single", "t0-fixed"), ("single", "t07-varied"), ("mas", "t0-fixed"), ("mas", "t07-varied")]),
    ("Perturbation block", ["pass^1", "pass^5", "pass^15", "DAR", "krippendorff_alpha", "flip_rate", "mean_entropy"],
     [(a, c) for a in ARMS for c in ("pert-t0", "pert-t05", "pert-t10")]),
    ("Appendix ROUGE-L", ["rouge_l_f1"],
     [(a, c) for a in ARMS for c, *_ in PLAN]),
]

metric_flags: list[str] = []
for title, cols, keys in TABLES:
    sub(title)
    print(f"       {'arm':<7} {'condition':<12} {'metric':<22} {'report':>14} {'mine':>14} {'diff':>12}")
    for arm, cond in keys:
        mine = MET[(arm, cond)]
        rep = REPORTED.get((arm, cond), {})
        for col in cols:
            mv = mine.get(col)
            rv = rep.get(col)
            if rv is None and mv is None:
                continue
            if rv is None:
                print(f"       {arm:<7} {cond:<12} {col:<22} {'(not reported)':>14} {mv if mv is None else f'{mv:14.4f}'} {'':>12}")
                continue
            if mv is None:
                metric_flags.append(f"{arm}/{cond}/{col}: report has {rv} but the metric is undefined here")
                print(f"       {arm:<7} {cond:<12} {col:<22} {rv:>14.4f} {'(undefined)':>14} {'FLAG':>12}")
                continue
            if mv in (float("inf"),):
                print(f"       {arm:<7} {cond:<12} {col:<22} {rv:>14.4f} {'inf':>14} {'':>12}")
                continue
            diff = mv - rv
            big = abs(rv) > 10
            bad = (abs(diff) / max(abs(rv), 1e-12) > TOL_REL) if big else (abs(diff) > TOL)
            tag = "  <-- FLAG" if bad else ""
            if bad:
                metric_flags.append(f"{arm}/{cond}/{col}: report={rv} mine={mv} diff={diff:+.6f}")
            print(f"       {arm:<7} {cond:<12} {col:<22} {rv:>14.4f} {mv:>14.4f} {diff:>+12.5f}{tag}")

sub("3.x cross-checks on the metric definitions themselves")
# Do == 1 - DAR when every unit has the same number of repeats; this is an
# internal consistency check on my own alpha implementation.
for arm, cond in [("single", "t07-varied"), ("mas", "t07-varied")]:
    units = [[r["decision"] for r in rows] for rows in G[(arm, cond)].values()]
    a = krippendorff_alpha_nominal(units)
    dar = MET[(arm, cond)]["DAR"]
    n = sum(len(u) for u in units)
    glob = Counter(x for u in units for x in u)
    de = (n * n - sum(v * v for v in glob.values())) / (n * (n - 1))
    implied = 1 - (1 - dar) / de
    okay = abs(implied - a) < 1e-9
    (ok if okay else fail)(
        f"{arm}/{cond}: alpha={a:.6f}, 1-(1-DAR)/De={implied:.6f} (De={de:.6f}) -> consistent={okay}"
    )

# Majority-vote tie-break: the report's prose says "ties break by first-observed
# decision"; that is the rule implemented above. The alternative rule in use
# elsewhere in the project is the canonical OUTCOMES order
# (escalate > dismiss > investigate > malformed). Where a case is tied AND the
# two rules disagree about label agreement, the reported number can only match
# one of them. This block identifies every such case.
sub("3.y majority-vote tie-break diagnostic")


def majority_canonical(decs: list[str]) -> str:
    cnt = Counter(decs)
    top = max(cnt.values())
    return next(o for o in OUTCOMES if cnt.get(o, 0) == top)


tie_rows = []
for arm in ARMS:
    for cond, *_ in PLAN:
        cases = G[(arm, cond)]
        hit_first = hit_canon = 0
        for cid, rows_ in sorted(cases.items()):
            decs = [r["decision"] for r in rows_]
            cnt = Counter(decs)
            top = max(cnt.values())
            tied = [k for k in cnt if cnt[k] == top]
            f_, c_ = majority(decs), majority_canonical(decs)
            hit_first += f_ == labels[cid]
            hit_canon += c_ == labels[cid]
            if len(tied) > 1:
                tie_rows.append((arm, cond, cid, labels[cid], sorted(tied), f_, c_))
        n = len(cases)
        if n and hit_first != hit_canon:
            note(
                f"{arm}/{cond}: majority_vote_accuracy = {hit_first/n:.4f} under the "
                f"REPORTED convention (first-observed) but {hit_canon/n:.4f} under the "
                "canonical-OUTCOMES-order convention implemented in analysis/metrics.py"
            )
print(f"       tied cases in this sweep: {len(tie_rows)}")
for arm, cond, cid, gt, tied, f_, c_ in tie_rows:
    flag = "  <-- conventions disagree on label agreement" if (f_ == gt) != (c_ == gt) else ""
    print(f"       {arm:<7} {cond:<12} {cid} gt={gt:<11} tied={tied} first-observed={f_:<11} canonical={c_}{flag}")

# malformed totals reconcile with the per-condition rates
recon = sum(
    MET[(a, c)]["malformed_rate"] * MET[(a, c)]["cases"] * MET[(a, c)]["repeats"]
    for a in ARMS
    for c, *_ in PLAN
)
(ok if abs(recon - n_mal) < 1e-6 else fail)(
    f"malformed reconciliation: sum(rate*runs)={recon:.1f} vs raw count {n_mal}"
)


# ---------------------------------------------------------------- 4. STATS

hdr("SECTION 4 - ARM-DIFFERENCE STATISTICS (t07-varied, single - mas)")

BOOT = 20000
PERM = 20000
rand = random.Random(20260812)

single_m = MET[("single", "t07-varied")]
mas_m = MET[("mas", "t07-varied")]
case_ids = sorted(set(single_m["_pass"]) & set(mas_m["_pass"]))
print(f"       paired cases: {len(case_ids)}")

STAT_KEYS = [("pass_fraction", "_pass"), ("DAR", "_dar"), ("entropy", "_ent")]

reported_stats = {}
in_stats = False
for line in open(RES / "analysis-report.md", encoding="utf-8"):
    if line.startswith("## Arm difference"):
        in_stats = True
        continue
    if in_stats and line.startswith("##"):
        in_stats = False
    if in_stats and line.strip().startswith("|"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] not in ("metric",) and not set("".join(cells)) <= set("-: "):
            m = re.match(r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", cells[2])
            reported_stats[cells[0]] = (
                float(cells[1]),
                (float(m.group(1)), float(m.group(2))) if m else None,
                float(cells[3]),
            )

print(f"       {'metric':<16} {'source':<8} {'mean diff':>10} {'95% CI':>22} {'perm p':>9}")
stat_flags: list[str] = []
for name, key in STAT_KEYS:
    diffs = [single_m[key][c] - mas_m[key][c] for c in case_ids]
    n = len(diffs)
    obs = sum(diffs) / n
    # percentile bootstrap over cases (the sampling unit)
    boots = []
    for _ in range(BOOT):
        s = sum(diffs[rand.randrange(n)] for _ in range(n))
        boots.append(s / n)
    boots.sort()
    lo = boots[int(0.025 * BOOT)]
    hi = boots[int(0.975 * BOOT) - 1]
    # paired sign-flip permutation, two-sided
    ge = 0
    for _ in range(PERM):
        s = sum(d if rand.getrandbits(1) else -d for d in diffs)
        if abs(s / n) >= abs(obs) - 1e-15:
            ge += 1
    p_addone = (ge + 1) / (PERM + 1)
    p_plain = ge / PERM
    rep = reported_stats.get(name)
    if rep:
        print(f"       {name:<16} {'report':<8} {rep[0]:>10.3f} {str(rep[1]):>22} {rep[2]:>9.3f}")
    print(f"       {name:<16} {'mine':<8} {obs:>10.3f} {f'[{lo:.3f}, {hi:.3f}]':>22} {p_addone:>9.3f}"
          f"   (p without +1 correction: {p_plain:.4f})")
    if rep:
        if abs(obs - rep[0]) > TOL:
            stat_flags.append(f"{name}: mean diff report={rep[0]} mine={obs:.4f}")
        if rep[1] and (abs(lo - rep[1][0]) > TOL or abs(hi - rep[1][1]) > TOL):
            stat_flags.append(f"{name}: CI report={rep[1]} mine=[{lo:.4f}, {hi:.4f}]")
        # p-values are Monte Carlo; allow a generous tolerance
        if min(abs(p_addone - rep[2]), abs(p_plain - rep[2])) > 0.02:
            stat_flags.append(f"{name}: permutation p report={rep[2]} mine={p_addone:.4f}")
if stat_flags:
    for f_ in stat_flags:
        fail(f_)
else:
    ok("arm-difference table reproduces within tolerance (CIs/p are Monte Carlo)")

sub("4.2 worst-entropy cases (t07-varied)")
for arm in ARMS:
    ent = MET[(arm, "t07-varied")]["_ent"]
    worst = sorted(ent.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    print(f"       {arm}: " + ", ".join(f"{c}={v:.3f}" for c, v in worst))
rep_worst = {}
for line in open(RES / "analysis-report.md", encoding="utf-8"):
    m = re.match(r"Worst-entropy cases \((\w+), t07-varied\): (.+)", line.strip())
    if m:
        rep_worst[m.group(1)] = [x.strip() for x in m.group(2).split(",")]
for arm, names in rep_worst.items():
    ent = MET[(arm, "t07-varied")]["_ent"]
    mine_top = sorted(ent.items(), key=lambda kv: -kv[1])[:3]
    mine_vals = sorted((round(v, 6) for _, v in mine_top), reverse=True)
    rep_vals = sorted((round(ent[c], 6) for c in names if c in ent), reverse=True)
    same = mine_vals == rep_vals
    (ok if same else note)(
        f"{arm} worst-3 reported {names} (entropies {[round(ent.get(c, float('nan')), 3) for c in names]}) "
        f"vs my top-3 {[c for c, _ in mine_top]} -- same entropy multiset: {same}"
    )


# --------------------------------------------------------- 5. CROSS-MODEL

hdr("SECTION 5 - CROSS-MODEL CONTEXT (CONFOUNDED: different models, not a thinking on/off contrast)")

SEALED = [
    ("results", "qwen3.5:9b"),
    ("results-qwen2.5-7b", "qwen2.5:7b"),
    ("results-qwen2.5-14b", "qwen2.5:14b"),
    ("results-gemma4", "gemma4:latest"),
]

print("       Tier 1 recomputed from each sweep's RAW journals by this script")
print("       (not copied from their analysis-report.md files).")
print()
print(f"       {'model':<16} {'track':<11} {'ollama':<8} {'arm':<7} {'cond':<11} "
      f"{'pass^1':>7} {'pass^5':>7} {'DAR':>7} {'alpha':>7} {'flip':>6} {'malf':>6}")


def tier1_from_dir(d: Path) -> dict:
    rows = []
    for arm in ARMS:
        rows.extend(read_journal(d / f"journal-{arm}.jsonl"))
    g = group(rows)
    out = {}
    for arm in ARMS:
        for cond in ("t0-fixed", "t07-varied"):
            cases = g.get((arm, cond)) or {}
            if not cases:
                continue
            counts, dars, units = [], [], []
            flips = mal = tot = 0
            for cid, rr in cases.items():
                decs = [r["decision"] for r in sorted(rr, key=lambda r: r["repeat_idx"])]
                counts.append((len(decs), sum(1 for x in decs if x == labels[cid])))
                dars.append(pairwise_agreement(decs))
                units.append(decs)
                flips += len(set(decs)) > 1
                mal += sum(1 for x in decs if x == "malformed")
                tot += len(decs)
            out[(arm, cond)] = {
                "pass^1": pass_at_k(counts, 1),
                "pass^5": pass_at_k(counts, 5),
                "DAR": sum(dars) / len(dars),
                "alpha": krippendorff_alpha_nominal(units),
                "flip_rate": flips / len(cases),
                "malformed_rate": mal / tot,
            }
    return out


def emit(model, track, ver, t1):
    for arm in ARMS:
        for cond in ("t0-fixed", "t07-varied"):
            v = t1.get((arm, cond))
            if not v:
                continue
            print(
                f"       {model:<16} {track:<11} {ver:<8} {arm:<7} {cond:<11} "
                f"{v['pass^1']:>7.3f} {v['pass^5']:>7.3f} {v['DAR']:>7.3f} {v['alpha']:>7.3f} "
                f"{v['flip_rate']:>6.3f} {v['malformed_rate']:>6.3f}"
            )


mine_t1 = {
    (a, c): {
        "pass^1": MET[(a, c)]["pass^1"],
        "pass^5": MET[(a, c)]["pass^5"],
        "DAR": MET[(a, c)]["DAR"],
        "alpha": MET[(a, c)]["krippendorff_alpha"],
        "flip_rate": MET[(a, c)]["flip_rate"],
        "malformed_rate": MET[(a, c)]["malformed_rate"],
    }
    for a in ARMS
    for c in ("t0-fixed", "t07-varied")
}
emit("lfm2.5:8b", "THINKING-ON", "0.32.9", mine_t1)
for d, model in SEALED:
    p = EXP / d
    man = json.load(open(p / "manifest.json", encoding="utf-8"))
    emit(model, "thinking-off", man["ollama_version"], tier1_from_dir(p))

print()
print("       Interpretation limits (pre-registered, CHANGELOG 2026-08-12 overnight):")
print("       * lfm2.5:8b has NO admissible thinking-off configuration (it inlines")
print("         reasoning into content under think:false), so this table contrasts")
print("         DIFFERENT MODELS, not deliberation on vs off.")
print("       * Any gap here is confounded with model identity, size, family and")
print("         (for the qwen sweeps) Ollama version 0.31.1 vs 0.32.9.")
print("       * The only clean within-model thinking on/off contrast in the project")
print("         is muse-glimmer:30b, which is not part of this sweep.")


# ------------------------------------------------------------- 6. VERDICT

hdr("SECTION 6 - VERDICT")

print(f"       integrity failures            : {len(FAILURES)}")
print(f"       metric discrepancies (>0.005) : {len(metric_flags)}")
print(f"       stats discrepancies           : {len(stat_flags)}")
print(f"       thinking-channel violations   : {len(contaminated)} raw_output, {len(node_hits)} node_output")
print()
if FAILURES:
    print("       FAILURES:")
    for f_ in FAILURES:
        print(f"         - {f_}")
if metric_flags:
    print("       METRIC FLAGS:")
    for f_ in metric_flags:
        print(f"         - {f_}")
if stat_flags:
    print("       STAT FLAGS:")
    for f_ in stat_flags:
        print(f"         - {f_}")
if NOTES:
    print("       NOTES:")
    for f_ in NOTES:
        print(f"         - {f_}")

arith_flags = [f_ for f_ in metric_flags if "majority_vote_accuracy" not in f_]
conv_flags = [f_ for f_ in metric_flags if "majority_vote_accuracy" in f_]
print()
print("       Classification of the findings:")
print(f"         * arithmetic discrepancies (a number cannot be reproduced under any")
print(f"           stated convention)                              : {len(arith_flags)}")
print(f"         * convention discrepancies (the number is correct under the rule the")
print(f"           code implements, but not under the rule the report states): {len(conv_flags)}")
for f_ in conv_flags:
    print(f"             - {f_}")
if conv_flags:
    print("           analysis/metrics.py:115-120 breaks majority ties by canonical")
    print("           OUTCOMES order (escalate > dismiss > investigate > malformed);")
    print("           analysis-report.md and docs/METRICS-PROVENANCE.md both state")
    print("           'ties break by first-observed decision'. One tied case")
    print("           (mas / t07-varied / TXN-2025-019, 5 investigate vs 5 escalate,")
    print("           label escalate) makes the two rules disagree, worth exactly")
    print("           1/50 = 0.02 of majority_vote_accuracy. Every other number in the")
    print("           report is unaffected by the tie-break rule.")
print(f"         * pre-registered thinking-channel criterion violations : {len(contaminated)}")
print()
print(f"       ARITHMETIC REPRODUCTION OF analysis-report.md : {'CONFIRMED' if not arith_flags and not stat_flags else 'FAILED'}")
print(f"       PRE-REGISTERED THINKING-CHANNEL CRITERION HELD: {not contaminated}")
