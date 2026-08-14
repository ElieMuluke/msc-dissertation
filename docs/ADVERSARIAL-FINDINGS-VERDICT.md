# Adversarial verification verdict — DEFECT-IMPACT-ANALYSIS.md

*Written 2026-08-14. Mandate: refute, not confirm. Everything below recomputed
read-only from the sealed journals by
`backend/experiments/analysis/adv_findings_recompute.py` and
`adv_findings_followup.py` (run from `backend/` with `PYTHONPATH=. ./.venv/bin/python`).
No LLM/GPU/ollama use; muse-glimmer untouched. The claims attacked are the four
load-bearing assertions of `docs/DEFECT-IMPACT-ANALYSIS.md`.*

## Verdict table

| claim | verdict |
|---|---|
| C1 — four headline conclusions derive solely from the four ctx-1/2 sweeps; zero deepseek/granite numbers | **SURVIVES** (every underlying number reproduced exactly; grep clean) — but two committed headline docs contain cost numbers that do not reproduce from any journal (new defect, unrelated to deepseek/granite) |
| C2 — headline sweeps' tool channels healthy; no conclusion contaminated | **SURVIVES** on materiality (worst-case flip of every pocket run shifts pass¹ ≤0.008; one escalate-table cell contains one zero-tool run; no conclusion moves) |
| C3 — gemma4-single 0.552 corrected ranking right and unthreatened | **WEAKENED** — 0.552 reproduces, but 0.552 vs 0.548 is a statistical tie (gap +0.004, 95% CI [−0.096, +0.111]) and the ranking *inverts* under a defensible sensitivity (drop repeat 0: 0.546 vs 0.553). "Best" requires a tie disclosure |
| C4 — no re-runs needed; pockets are disclosure-only; only 2 .tex lines change | **REFUTED in part** — "no re-runs" survives; "disclosure-only" mostly survives the severity test; **"only 2 .tex lines" is refuted**: `.tex:657`'s perturbation universal is false *within the sealed corpus itself*, and the impact doc's own proposed fix for it would still be false |

**Single strongest contrary finding:** the perturbation/degeneracy criteria that
excluded granite4.1 are failed, equally or worse, by retained headline cells.
qwen2.5-14b is *more* mode-collapsed than the excluded granite (93.1% vs 87.7%
modal `investigate` in MAS), less accurate (pass¹ 0.221 vs 0.289; MV 11/50 vs
11/50), and *less* perturbation-responsive (MAS majority vote moved 1/10 at
pert-t0 and 0/10 at both T>0 conditions; run-level flips 2/100 vs granite's
17/100). qwen3.5's MAS arm matches granite-MAS cell-for-cell (86.0% modal,
pass¹ 0.253, MV 11/50, pert MV moved 0–1/10). The exclusion standard is
inconsistent: applied uniformly it either re-admits granite's null or forces
the same degeneracy annotation onto qwen2.5-14b's "no arm difference" story and
onto the qwen3.5 MAS cells that drive the winner selection.

---

## C1 — recomputation of the four headline conclusions

All recomputed from journals, t07-varied, and **all reproduce exactly**:

- Tier-1 table (all 9 sweeps incl. 0.32.6 replicas): every pass¹/DAR/alpha
  matches the committed `analysis-report.md` to 3 dp (e.g. gemma4 0.552/0.297,
  qwen2.5-7b 0.293/0.449, qwen3.5 0.364/0.253, 14b 0.248/0.221).
- Spectrum redistribution: dismiss per-label rate single→MAS: q3.5 .197→.051,
  14b .036→.005, gemma4 .456→.003 (1/390), 7b the exception .190→.515. ✔
- Escalation suppression in qwens: .440→.240, .129→.102, .196→.164;
  gemma4 amplified .724→.778. ✔
- gemma4 escalation competence: escalate-case table reproduced cell-for-cell
  (002: 14|15, 004: 14|11, 015: 15|14, 039: 15|9, 049: 15|12; TXN-015 gemma4
  15/15 single vs qwens 0–5/15). Tool-diligence numbers confirmed
  (q3.5-single 1.02→.44, q7b-mas 4.22→.10, gemma4 2.05 tools/run). ✔
- Majority-vote rescue: 7b-MAS 27/50, gemma4-single 30/50 — top two among the
  four sealed sweeps. ✔
- Grep + read of FINAL-RESULTS, ANALYSIS-INSIGHTS, SUPERVISOR-PACK,
  cross-model-comparison.md, the .tex results chapters: **zero deepseek-r1 or
  granite4.1 numbers**, including pooled aggregates. The .tex token/time ranges
  (163: "1.8 to 3.1 times the tokens", 657: "2.2 to 3.7 times the wall-clock")
  derive exactly from the four sweeps (recomputed ratios 1.83/3.11/2.77/2.41×
  tokens; 2.50/3.65/2.19/2.29× wall). `granite4` in the six-exclusions list is
  the old model, correctly distinct. `.tex:470` names deepseek-r1:14b as the
  Component-1 RAG generator — RAG uses no tools, so Defect A does not touch it,
  but a one-line disclosure is prudent now that the model's template defect is
  a named finding.

**New defect found while checking C1's aggregates** (nobody flagged; unrelated
to deepseek/granite): the committed cost numbers in FINAL-RESULTS.md and
SUPERVISOR-PACK.md do not reproduce from any journal or per-sweep report:

| committed claim | journal truth |
|---|---|
| FINAL-RESULTS table: qwen2.5-7b "3.0k→~7.5k" tokens | 2,074→6,458 |
| FINAL-RESULTS table: qwen2.5-14b "~4.2k→~7.7k" tokens | 2,128→5,903 |
| FINAL-RESULTS:68 / SUPERVISOR-PACK:61 "MAS uses ~1.8× the tokens" | 1.83–3.11× across the four sweeps (not "consistent") |
| Both docs: "~2.5–3.4× the time" | 2.19–3.65× |

The per-sweep reports and the .tex are correct; the two summary docs are wrong.
Also minor: SUPERVISOR-PACK finding 4 "malformed outputs concentrate in the
single arm, all four models" — qwen2.5-14b is 2 vs 2, a tie.

## C2 — pocket runs traced into the headline numbers

Every zero-tool run in the four sweeps, individually traced:

- **qwen3.5 MAS, 5 runs** (TXN-2025-009/014/016/017/028, all t07): labels
  4×dismiss + 1×investigate, all decided `investigate`. None of the five
  escalate-table cases. Max pass¹ shift if all five flipped: 5/750 = **0.0067**.
- **gemma4 single, 7 runs** (6 at t07, 1 at t0-fixed): max pass¹ shift
  6/750 = **0.0080**. Exactly one sits in an escalate-table cell:
  `single:TXN-2025-039:t07-varied:14`, decided `escalate` with zero tool calls —
  the "15" in gemma4's 15|9 row contains one un-tooled escalation (cell becomes
  14/14 if excluded; conclusion unchanged). Max per-label escalate-rate shift
  1/225 = 0.0044 against a 0.72-vs-≤0.44 gap. One other zero-tool run
  (TXN-2025-044, dismiss-labelled) escalated while asserting unearned facts —
  footnote-grade only.
- qwen2.5-14b MAS: 1 run (dismiss on dismiss). qwen2.5-7b: none.
- gemma4-MAS additionally has 3 policy-node-dead runs (census) — 3/1150, immaterial.

No headline conclusion moves under worst-case flipping of every pocket run.
The census phrase "fully healthy" is mild overstatement; the impact analysis's
substantive claim holds. What would have refuted it: pocket runs concentrated
in escalate-table cells or shifts > smallest reported gap — checked, absent.

## C3 — the 0.552 superlative

Metric identified: **single-arm pass¹ (label agreement), t07-varied, 50×15** —
not majority vote (gemma4's MV accuracy is 0.60). Recomputed 0.5520 exactly.
Robustness: excluding the 6 t07 zero-tool runs → 0.5506; excluding 10 malformed
→ 0.5605; journal has zero `error` records. The number is real.

The **superlative** is not robust:

- Gap to qwen3.5-budget-single (0.5480, also reproduced exactly): **+0.0040**,
  bootstrap 95% CI **[−0.096, +0.111]** paired by case ([−0.111, +0.123]
  unpaired). Each estimate's own CI spans ±~0.08. A statistical tie.
- Dropping repeat 0 from both (the deepseek audit's first-repeat cache concern,
  applied symmetrically): gemma4 0.5457 vs budget 0.5529 — **the ranking
  inverts**.
- Budget's own defect does not rescue gemma4: excluding budget-single's 45 runs
  that call hallucinated decision-verb tools, budget is 0.5472 — still a tie.
- Threat scan of other sealed sweeps: lfm2.5-single rises 0.491→0.508 when its
  141 defective runs (97 zero-tool + 44 hallucinated-tool) are excluded — still
  below; no other sweep approaches. Checked.

The impact doc's flat "across all valid sweeps it also stands, 0.552 > 0.548"
is point-estimate ordering presented as a finding. The .tex:647 fix must say
"best label agreement among the sealed sweeps **(statistically indistinguishable
from qwen3.5:9b-thinking-budget's 0.548 under the third context)**" or scope to
the thinking-off corpus where the gap (0.552 vs 0.364) is real. Secondary:
ANALYSIS-INSIGHTS item 5's "30/50 leads all configs" is already stale across
valid sweeps (lfm2.5-single 34/50, budget-single 32/50) — scope armour needed
on any regeneration.

## C4 — severity of the pockets, and the unread perturbation control

**Severity test (as specified — exclude every MAS run with any tool-dead node,
recompute Tier-1, compare to committed):**

| sweep, MAS t07 | committed | excl. node-dead (dropped/750) | arm-diff pass_fraction: committed CI → filtered |
|---|---|---|---|
| lfm2.5-think | pass¹ .344, DAR .421, α .130 | pass¹ .376, DAR .439, **α .197** (357) | +0.147 [0.071,0.220] → +0.115 (inside CI) |
| qwen3.5-budget | pass¹ .264, DAR .724, α .277 | pass¹ .273, DAR .747, α .299 (168) | +0.284 [0.173,0.395] → +0.275 (inside CI) |

t0-fixed: DAR/alpha stay 1.000 in both sweeps after exclusion. No arm-difference
statistic leaves its committed bootstrap CI; every direction claim ("single
beats MAS on both valid thinking sweeps") holds under filtering (0.491-vs-0.376
and 0.548-vs-0.273). **"Disclosure only" is defensible for those two sweeps'
Tier-1** — with one exception: lfm2.5's alpha entry in the impact doc's ranking
table (".159/.130") becomes .159/**.197** under exclusion; the single-vs-MAS
alpha ordering for that sweep is an artefact of including 40.9% policy-dead
runs and must not be cited.

**The hole in C1's survival story — confirmed.** The granite exclusion
instrument (base-case MV vs perturbed-case MV), run on all four headline
sweeps:

| sweep | arm | pert-t0 | pert-t05 | pert-t10 | run-level flips at T>0 |
|---|---|---|---|---|---|
| qwen3.5 | single | 5/10 | 6/10 | 5/10 | 48/100 |
| qwen3.5 | **mas** | **1/10** | **0/10** | **1/10** | 19/100 |
| qwen2.5-7b | single | 1/10 | 3/10 | **0/10** | 19/100 |
| qwen2.5-7b | mas | 3/10 | 2/10 | 1/10 | 26/100 |
| qwen2.5-14b | single | 4/10 | 1/10 | **0/10** | 12/100 |
| qwen2.5-14b | **mas** | **1/10** | **0/10** | **0/10** | **2/100** |
| gemma4 | single | 9/10 | 9/10 | 8/10 | 80/100 |
| gemma4 | mas | 7/10 | 7/10 | 7/10 | 69/100 |
| (granite4.1, struck) | mas | 0/10 | — | — | 17/100 |

`.tex:657` — "flipped cases flipped decisions at T>0 in both arms of every
model. High repeatability was not the models ignoring their input." — is
**false as written**: qwen2.5-14b's MAS arm, the highest-repeatability cell in
the corpus (DAR 0.914), moved its majority vote on 0/10 perturbations at both
T>0 conditions and flipped 2 runs in 100 — *less* responsive than the granite
sweep excluded for exactly this. The impact doc's planned §5.2 correction
("scope to every sealed-corpus model") would still be false. FINAL-RESULTS:113
and SUPERVISOR-PACK finding 5 carry the same false universal. So the .tex needs
**three** unconditional line changes (647, 759, 657), plus the two summary
docs — and the honest fix for 657 is to report the table above, which converts
an instrument-check boast into a finding (MAS arms are systematically less
input-responsive; gemma4 is the only model whose MAS passes its own control).

Consequences for the impact doc's verdicts: the C12 entry ("True for the 4
sealed context-1/2 models it describes") is wrong at majority-vote level; the
winner selection (MAS default via qwen3.5 DAR 0.802 vs 0.618, alpha caveat
already given) now carries a second unstated caveat — the DAR advantage
coexists with 86% modal collapse and a 0–1/10 perturbation response, the exact
"DAR without alpha/degeneracy" trap Chapter 5 warns about.

**"No experiment needs re-running" — survives.** Every defect found here is
model behaviour measured correctly, not infrastructure: 14b reproduced its
sweep decision-for-decision across serving versions (2,297/2,300 byte-identical),
so a re-run reproduces the defect. What forces work is re-*scoping* and
re-*annotating*, not re-running. What would have refuted it: an
infrastructure-caused defect (deepseek-class) inside a valid sweep — checked
for (template audit, error fields, version pairs); absent.

## Bonus — entropy ln 4 (granite audit D1)

Generalises to the entire corpus: `metrics.py:129` normalises by
`log2(len(OUTCOMES))` = log2(4) because `malformed` is a fourth category, so
every committed report (all four headline sweeps included) deflates decision
entropy by the same 20.75% (log2(3)/log2(4) = 0.7925). Checked every committed
comparison: entropy appears only as within-sweep arm differences (CIs sign-
invariant under a common scale factor) and methodological prose; no committed
conclusion depends on an entropy magnitude. Disclosure line, no impact.

## New defects found (none previously flagged)

1. **Retained headline cells fail the granite exclusion criteria** (qwen2.5-14b
   both arms; qwen3.5 MAS) — see strongest finding above. Decide the standard
   and apply it uniformly.
2. **FINAL-RESULTS.md and SUPERVISOR-PACK.md cost numbers are unreproducible**
   (7b/14b token cells ~30% high; "~1.8×"/"~2.5–3.4×" ranges wrong). The .tex
   and per-sweep reports are correct.
3. **`.tex:657` perturbation universal is false within the sealed corpus**, and
   the planned fix in DEFECT-IMPACT-ANALYSIS §5.2 would not repair it.
4. **The 0.552 ranking inverts when repeat 0 is excluded from both contenders**
   (0.546 vs 0.553) — the superlative is inside noise on every stressor.
5. lfm2.5's committed single/MAS alpha ordering (.159/.130) reverses (.159/.197)
   once tool-dead-node runs are excluded.
6. Minor: SUPERVISOR-PACK "malformed concentrate in the single arm, all four
   models" — false for 14b (2 vs 2); deepseek-r1:14b is Component 1's RAG
   generator (.tex:470) — unaffected by Defect A but should be disclosed.

---

## Owner resolution 2026-08-14: option (a) adopted — granite re-admitted, uniform degeneracy annotation

The owner resolved new-defect #1 by choosing full honesty: rather than excluding
granite4.1 while retaining equally-degenerate headline cells, granite4.1 returns as
a **fifth no-arm-difference data point** and the degeneracy annotation is applied
**uniformly** to every cell that fails the same criteria — granite4.1 (87.7%
modal-`investigate` MAS / 85.6% single), qwen2.5-14b-MAS (93.1% modal), and
qwen3.5-MAS (86.0% modal), all with majority-vote accuracy below the 0.520
constant-`dismiss` baseline. deepseek-r1:14b stays excluded (infrastructure-invalid:
the model never saw tools — no annotation can repair a dead channel). Changes
applied:

- `docs/DEFECT-IMPACT-ANALYSIS.md` — §0 disposition note added; C5 reclassified
  DEAD→REVISE with the re-admission text ("5 models show no meaningful arm advantage
  in accuracy"); C12 corrected (the "scope to the four sealed models" fix was itself
  false — qwen2.5-14b-MAS moved 0/10); §2 ranking table: granite row re-admitted with
  annotation, gemma4/budget rows marked as a statistical tie; §2 superlative bullet
  rewritten with the full tie disclosure (+0.004, 95% CI [−0.096, +0.111], inversion
  0.546 vs 0.553 without repeat 0); §3 verdicts updated (fifth-data-point row,
  winner-selection row gains the degeneracy caveat and flags the platform `mas`
  default — deps.py DAR 0.802 vs 0.618 docstring — as an owner decision point,
  deps.py unchanged); §5.1/§5.2 .tex instructions updated to the applied wording.
- `docs/FINAL-RESULTS.md` — uniform degeneracy annotation block added under the main
  table (no number deleted); 7b token cell corrected 3.0k→7.5k ⇒ **2.1k→6.5k**, 14b
  ⇒ 2.1k→5.9k, gemma4 ⇒ 3.9k→9.5k (journal-recomputed); "~1.8×"/"~2.5–3.4×" ⇒
  **1.8–3.1×** tokens / **2.2–3.7×** wall; perturbation instrument-check universal
  corrected to name the qwen2.5-14b-MAS exception.
- `docs/SUPERVISOR-PACK.md` — same annotation block under the headline table; same
  cost corrections; finding 4's gemma4 superlative scoped + tie noted; finding 5's
  universal corrected; winner-selection paragraph gains the second caveat and the
  owner-decision-point flag.
- `docs/ANALYSIS-INSIGHTS.md` — item 1 gains the uniform annotation (modal rates,
  constant-baseline comparison, perturbation response, granite re-admission).
- `docs/TOOL-CHANNEL-CENSUS.md` — new §9 correction: MAS truncation sub-attributions
  retracted (broken run-sum vs per-call-cap classifier; "1,048 deepseek MAS
  truncated" is an artifact); thinking-budget policy deaths reclassified (92/167
  starvation at 8192, 11 server errors, ~64 genuine declines); lfm2.5/muse pockets
  confirmed as model behaviour.
- `docs/dissertation-corrected.tex` — line ~647 superlative scoped to "among the
  sealed thinking-off sweeps" + tie footnote; line ~657 perturbation universal
  replaced with the journal-supported seven-of-eight-cells statement naming the
  qwen2.5-14b-MAS exception; line ~470 one-line deepseek RAG-generator disclosure;
  line ~510 granite4-vs-granite4.1 conflation guard consistent with the
  re-admission.
