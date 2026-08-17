# Independent audit — `results-muse-glimmer-30b` (thinking-off, sealed 2026-08-15)

**Auditor:** independent recomputation, 2026-08-17.
**Inputs used:** `manifest.json`, `journal-single.jsonl`, `journal-mas.jsonl`,
`progress.json`, benchmark labels
(`dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json`),
`experiments/perturbation_cases.json`, and harness source
(`harness/extraction.py`, `harness/runner.py`, `harness/manifest.py`,
`analysis/metrics.py`) for locked-definition reference only.

**Scripts:** `analysis/eval_museglimmer_integrity.py`,
`analysis/eval_museglimmer_metrics.py` (own implementations of pass^k, DAR,
Krippendorff α, normalised entropy, LCS, Jaccard, bootstrap, paired permutation).

**Blindness protocol observed.** All numbers below were derived and frozen before
`seal-checks.txt`, `analysis/seal_checks_muse_glimmer.py` or `CHANGELOG.md` were
opened. No `analysis-report.md` exists for this sweep — this document is the first
independent recomputation of it.

**Constraints honoured.** Zero LLM calls, zero GPU use, no `ollama` invocation, no
port contact. Pure-Python over JSONL. No existing file modified. The in-flight
`results-muse-glimmer-30b-thinking/` was not read or touched.

---

## 1. Headline table

Per arm × condition, recomputed from raw journals (n = cases, rep = repeats/case):

| arm | condition | n | rep | pass^1 | pass^5 | pass^15 | DAR | α | flip | maj-acc | norm-ent |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| single | t0-fixed | 50 | 5 | 0.3600 | 0.3600 | — | 1.0000 | 1.0000 | 0.000 | 0.3600 | 0.000 |
| single | t07-varied | 50 | 15 | 0.3920 | 0.1749 | 0.1400 | 0.7531 | 0.4353 | 0.640 | 0.3800 | 0.250 |
| single | pert-t0 | 10 | 5 | 0.4000 | 0.4000 | — | 1.0000 | 1.0000 | 0.000 | 0.4000 | 0.000 |
| single | pert-t05 | 10 | 5 | 0.3800 | 0.1000 | — | 0.6200 | 0.3649 | 0.700 | 0.3000 | 0.315 |
| single | pert-t10 | 10 | 5 | 0.4200 | 0.1000 | — | 0.5800 | 0.3038 | 0.700 | 0.4000 | 0.367 |
| mas | t0-fixed | 50 | 5 | 0.2920 | 0.2000 | — | 0.9360 | 0.7802 | 0.140 | 0.3200 | 0.056 |
| mas | t07-varied | 50 | 15 | 0.2640 | 0.1534 | 0.1000 | 0.8815 | 0.6193 | 0.340 | 0.2400 | 0.121 |
| mas | pert-t0 | 10 | 5 | 0.1200 | 0.1000 | — | 0.9000 | 0.6354 | 0.200 | 0.1000 | 0.085 |
| mas | pert-t05 | 10 | 5 | 0.0800 | 0.0000 | — | 0.7400 | 0.2875 | 0.600 | 0.1000 | 0.229 |
| mas | pert-t10 | 10 | 5 | 0.0800 | 0.0000 | — | 0.8600 | 0.5807 | 0.200 | 0.1000 | 0.125 |

Pooled per arm:

| arm | scope | runs | pass^1 | α | DAR | flip |
|---|---|---:|---:|---:|---:|---:|
| single | primary | 1000 | 0.3840 | 0.5715 | 0.8766 | 0.320 |
| single | perturbation | 150 | 0.4000 | 0.5492 | 0.7333 | 0.467 |
| single | all | 1150 | 0.3861 | 0.5765 | 0.8435 | 0.354 |
| mas | primary | 1000 | 0.2710 | 0.6573 | 0.9088 | 0.240 |
| mas | perturbation | 150 | 0.0933 | 0.4808 | 0.8333 | 0.333 |
| mas | all | 1150 | 0.2478 | 0.6331 | 0.8914 | 0.262 |

Cost:

| arm | prompt tok/run | compl tok/run | total tok/run | total tokens | wall/run | wall total |
|---|---:|---:|---:|---:|---:|---:|
| single | 6 293.9 | 997.3 | 7 291.2 | 8 384 863 | 39.55 s | 12.63 h |
| mas | 13 548.9 | 3 746.2 | 17 295.1 | 19 889 384 | 95.83 s | 30.61 h |

MAS/single: **tokens ×2.372**, wall ×2.423 (wall ratio is **not** interpretable — see
Threat T4). Tokens per unit pass^k, primary block:

| arm | condition | tok/pass^1 | tok/pass^5 | tok/pass^15 |
|---|---|---:|---:|---:|
| single | t0-fixed | 20 253 | 20 253 | — |
| single | t07-varied | 18 600 | 41 687 | 52 080 |
| mas | t0-fixed | 59 230 | 86 476 | — |
| mas | t07-varied | 65 512 | 112 775 | 172 951 |

MAS costs **3.2–3.5× more tokens per correct answer** than single at k=1, rising to
3.3× at k=15.

Trajectory metrics over tool-call name sequences (within-group pairwise means):

| arm | condition | exact-order | Jaccard | nLCS | mean \|seq\| | empty |
|---|---|---:|---:|---:|---:|---:|
| single | t0-fixed | 1.0000 | 1.0000 | 1.0000 | 4.16 | 0 |
| single | t07-varied | 0.2520 | 0.8852 | 0.7220 | 3.97 | 1 |
| single | pert-t0 | 1.0000 | 1.0000 | 1.0000 | 4.50 | 0 |
| single | pert-t05 | 0.4700 | 0.9100 | 0.8043 | 4.54 | 0 |
| single | pert-t10 | 0.2100 | 0.9250 | 0.7309 | 4.62 | 0 |
| mas | t0-fixed | 0.6280 | 0.9780 | 0.9001 | 7.74 | 0 |
| mas | t07-varied | 0.0870 | 0.9361 | 0.7061 | 7.32 | 5 |
| mas | pert-t0 | 0.5800 | 0.9450 | 0.8757 | 7.48 | 0 |
| mas | pert-t05 | 0.0900 | 1.0000 | 0.7354 | 7.56 | 0 |
| mas | pert-t10 | 0.1000 | 0.8800 | 0.6810 | 6.88 | 2 |

Arm-difference statistics, paired over cases (10 000 bootstrap resamples, 20 000
permutations, seed 20260817):

| scope | single | mas | diff (mas−single) | 95 % bootstrap CI | paired perm. p |
|---|---:|---:|---:|---|---:|
| primary accuracy (n=50) | 0.3840 | 0.2710 | **−0.1130** | [−0.2000, −0.0330] | **0.0121** |
| perturbation accuracy (n=10) | 0.4000 | 0.0933 | **−0.3067** | [−0.4600, −0.1667] | **0.0036** |
| primary DAR (n=50) | 0.8766 | 0.9088 | +0.0322 | [−0.0057, +0.0696] | 0.1034 (n.s.) |
| perturbation DAR (n=10) | 0.7333 | 0.8333 | +0.1000 | [−0.0633, +0.2433] | 0.2599 (n.s.) |

**The MAS arm is significantly *less* accurate than the single arm on both blocks, and
its higher agreement is not statistically distinguishable from zero.** MAS buys 2.37×
the tokens for a −0.113 accuracy penalty on primary and −0.307 on perturbation.

---

## 2. Per-dimension verdicts

### 2.1 Data integrity — **SOUND-WITH-CAVEATS**

Everything structural passes:

- 1150 + 1150 = 2300 journal records = `manifest.totals` = `len(manifest.runs)`. ✅
- **0** duplicate run keys, **0** plan keys missing, **0** journal keys outside plan. ✅
- **0** `run_id` strings inconsistent with their `(arm, case_id, condition, repeat_idx)`
  tuple. ✅
- **All 2300 runs** match the pre-generated plan on `seed`, `temperature`, `block`,
  `condition`, `case_id`, `arm` — zero mismatches. ✅
- Condition semantics hold: `t0-fixed` and `pert-t0` use exactly seed 42 (1 distinct
  seed over 500 and 100 runs); `t07-varied` has 750 distinct seeds over 1500 runs,
  `pert-t05`/`pert-t10` 50 over 100 each — i.e. **seeds are unique within each
  (arm, case, condition) group and shared across arms** (750/750, 50/50, 50/50
  identical cross-arm), which is the documented paired design. ✅
- Uniform across all 2300 runs and matching the manifest: `model`
  (`muse-glimmer:30b`), `model_digest` (`de878ce33ad8…4464c1`), `ollama_version`
  (`0.32.9`), `think` (`false`), `num_predict` (2048), `cache_policy` (`none`),
  `env.gpu_name`, `env.gpu_driver` (595.71). `host_load_high` false in 0/2300. ✅
- Decision domain is exactly {escalate, dismiss, investigate, malformed}. ✅
- **0/2300 disagreements** between the journalled `decision` and my independent
  re-implementation of the locked PRD-A extraction contract. ✅
- Journals are forensically homogeneous: a single JSON key ordering across all 2300
  lines in both files — no trace of re-serialised or reconstructed records. ✅
- `progress.json` `last_run_at` matches `max(started_at)` for both arms. ✅
- **Provenance verified against the seal commit.** SHA-256 of every tracked analysis
  input in this directory is byte-identical to seal commit `9be3958`
  ("results: seal muse-glimmer:30b thinking-off (2300/2300)…"): `journal-mas.jsonl`,
  `journal-single.jsonl`, `manifest.json`, `progress.json`, `seal-checks.txt`,
  `gates/mini-gates.json`. Nothing I audited has drifted since the seal. ✅

Caveats:

1. **`progress.json` mean wall-clock does not reconcile with the journals.** Recomputed
   single mean **39.548 s** vs `progress.json` 39.41; recomputed MAS mean **95.830 s**
   vs `progress.json` **85.08** — a **12.6 % understatement**. `progress.json` was
   regenerated at 2026-08-15T06:08:47Z with `done: 2300`, so the discrepancy is not a
   staleness-of-count issue. The MAS figure matches no prefix, suffix, or session
   window of the journal (nearest contiguous-window match is coincidental). It is a
   derived artefact that is simply wrong. Anything citing it inherits the error.
2. **The single journalled error is an infrastructure failure scored as a model
   outcome.** `single:TXN-2025-046:t07-varied:3`:
   `ResponseError: parse Glimmer call to calculate_risk_score: unterminated ATEM
   parameter "factors" (status code: 500)`, with `prompt_tokens=0`,
   `completion_tokens=0`, `agent_messages=0`, `tool_calls=[]`, `raw_output=""`,
   `wall_clock_s=19.678`. Classification: **server-side tool-call parse fault in
   Ollama 0.32.9, not a model refusal and not a truncation** — the model never
   produced a token. It is recorded as `decision: "malformed"`, i.e. it enters
   `single/t07-varied` as one of 750 scored outcomes. This is per the pre-registration
   ("outcome category, not excluded"), but conflates an infra defect with a model
   formatting failure. Impact is small (1/750) but it is the *only* malformed outcome
   in the entire sweep, so `single/t07-varied`'s malformed rate is 100 % infra-caused.
3. **The sealed directory is not immutable: the successor sweep wrote into it.**
   `serve-armB-postreboot.log` was committed at **34 107 451 bytes** in seal commit
   `9be3958` and now stands at **34 990 103 bytes** — **882 652 bytes appended after the
   seal**, with mtime `2026-08-15 08:16:16`. That window (07:31 → 08:16) is exactly the
   `muse-glimmer:30b@think` launch on arm B / `:11435` described in the CHANGELOG, which
   the 2026-08-17 entry says was killed by a machine power-off at ~08:16. The successor
   sweep's server reused the sealed sweep's log path. No analysis input was affected
   (all hash-identical above), and the file has not grown since, but the seal boundary
   was crossed by a live process — had the reused path been a journal rather than a
   server log, the sealed data would have been corrupted silently.
   Separately, `runner-mas.log` and `runner-single.log` are **gitignored**
   (`.gitignore:33`) and therefore outside the seal entirely — they cannot be
   provenance-checked, and they are the artefacts that would explain the undeclared
   05:25 stall (§2.2b).
4. `completion_tokens ≥ num_predict` in **1150/1150** MAS runs. This is *not*
   truncation evidence — MAS `completion_tokens` is summed across four nodes against a
   per-call cap of 2048. The proxy is invalid for multi-node arms and must not be used
   as a truncation classifier (the CHANGELOG already retracted one such classifier on
   2026-08-14; the same trap is live here).

### 2.2 The two declared deviations — **SOUND** (reboot) / **SOUND-WITH-CAVEATS** (overall)

**(a) The 2026-08-14 mid-sweep reboot: verified lossless.**

Exactly one inter-run `started_at` gap exceeds 10 minutes in either journal:

- MAS, **1009 s** gap (excess over the prior run's wall clock: **917 s**), between
  `2026-08-14T18:58:29Z` and `2026-08-14T19:15:18Z`.
- Last pre-gap run: **`mas:TXN-2025-027:t07-varied:12`** — manifest plan position
  **653/1150**, exactly matching the declared "stopped at MAS 653".
- **First post-resume run key: `mas:TXN-2025-027:t07-varied:13`** — plan position
  654/1150.

Resume integrity:

| check | result |
|---|---|
| plan adjacency across the boundary (653 → 654) | contiguous ✅ |
| journal record order == manifest plan order (whole MAS arm) | identical ✅ |
| duplicate keys within ±25 runs of the boundary | 0 ✅ |
| seed/temperature mismatches within ±25 runs | 0 ✅ |
| `ollama_version`, `model_digest`, `num_predict`, `think` across boundary | unchanged ✅ |
| `env.gpu_name`, `env.gpu_driver` across boundary | unchanged ✅ |
| `env.gpu_vram_used_mb` across boundary | 36 658 → **18 508** (model reload signature) |

**Cold-cache boundary behaviour of the first post-resume run** — nuanced, and the
declared expectation is only half right. `mas:TXN-2025-027:t07-varied:13` against its
14 sibling repeats:

- **Decision level: not anomalous.** It decided `escalate`, matching 5 of its 14
  siblings; the group is 7 escalate / 8 investigate. No decision-level artefact.
- **Byte / magnitude level: it is the extreme of its group on three of four measures.**
  Highest `completion_tokens` of all 15 (5160 vs group median ~4083), longest
  `raw_output` of all 15 (2638 chars vs median ~1661), longest `wall_clock_s` of all 15
  (102.75 s vs 1.24× the arm median and 1.31× the contemporaneous solo mean of 78.5 s),
  and 9 tool calls (joint maximum). The next 10 runs return to 68–87 s.

So the CHANGELOG's pre-declared consequence — "any residual effect is confined to the
first scored run after resume" — **holds, and the effect is real but confined to output
volume, not to the decision.** No metric that this audit recomputes changes if that run
is dropped.

**(b) An undeclared second interruption, affecting BOTH arms simultaneously.**

The >10-minute threshold hides it, but both journals contain a synchronous stall:

| arm | gap | excess over prior wall clock | resumes at |
|---|---:|---:|---|
| single | 502 s (between runs 561 → 562) | +458 s | **2026-08-14T05:25:45Z** |
| mas | 599 s (between runs 159 → 160) | +457 s | **2026-08-14T05:25:45Z** |

Both arms resume at the **identical second**. This is a host-level stall of ~7.6 min,
not an arm-local one, and it is 1 s below the seal check's 600 s detection threshold.
I found **no data loss from it**: no duplicate keys, no plan discontinuity, no seed
mismatch, order still equals plan order in both arms. It is benign as far as the
journals can show, but it was **not declared**, and the detection threshold that
missed it is the same one relied on to certify the reboot. This is the "earlier
data-recovery incident" candidate; nothing in the journals identifies it further.

Verdict: **the reboot resume is verifiably lossless. The declared-deviation record is
incomplete by one event, and the gap detector that certifies it is mis-calibrated.**

### 2.3 Recomputed metrics — **SOUND** (decision metrics) / **FLAWED** (wall-clock cost metrics)

All decision-based metrics in §1 are internally consistent and reproduce from raw
journals with independent implementations. Krippendorff α and DAR are mutually
consistent everywhere (α = 1 − D_o/D_e with D_o = 1 − DAR at equal group sizes).
Token-based cost metrics are sound. **Wall-clock metrics are not** — see Threat T4.

Note for interpretation: `pass^15` is only defined for `t07-varied` (15 repeats); all
other conditions have 5.

### 2.4 T=0 fixed-seed behaviour — **SOUND** (single arm) / **FLAWED** (MAS arm)

| arm | condition | byte-identical groups | decision-identical groups | mean distinct outputs/group |
|---|---|---|---|---:|
| single | t0-fixed | **48/50 (96 %)** | 50/50 (100 %) | 1.04 |
| single | pert-t0 | **10/10 (100 %)** | 10/10 (100 %) | 1.00 |
| mas | t0-fixed | **0/50 (0 %)** | 43/50 (86 %) | 3.76 |
| mas | pert-t0 | **0/10 (0 %)** | 8/10 (80 %) | 4.00 |

**The MAS arm is not reproducible at T=0 with a fixed seed, at all.** Zero of sixty
fixed-seed groups produced byte-identical output. Seven t0-fixed groups even flip
*decision* under identical seed and temperature (TXN-2025-015, -017, -019, -025, -029,
-035, -041), as do 2 of 10 `pert-t0` groups (PERT-001, PERT-008).

This is **not** a GPU-contention artefact: MAS `t0-fixed` ran 250/250 under
co-residency with the single arm (mean 138.6 s) while MAS `pert-t0` ran 50/50 solo
(mean 80.0 s), and **both show 0 % byte identity**. The single arm was 100 % contended
and stayed byte-deterministic. The nondeterminism is structural to the 4-node
pipeline, not environmental.

**First-repeat cache artefact — CONFIRMED, present in both arms, and worse in MAS than
the deepseek-r1 precedent.**

Progressive exclusion of early repeats, `t0-fixed`:

| repeats dropped | arm | n rep | DAR | α | byte-identical | decision-identical |
|---|---|---:|---:|---:|---|---|
| — | single | 5 | 1.0000 | 1.0000 | 48/50 | 50/50 |
| {0} | single | 4 | 1.0000 | 1.0000 | **50/50** | 50/50 |
| {0,1} | single | 3 | 1.0000 | 1.0000 | 50/50 | 50/50 |
| — | mas | 5 | 0.9360 | 0.7802 | 0/50 | 43/50 |
| {0} | mas | 4 | 0.9733 | **0.9101** | **0/50** | 48/50 |
| {0,1} | mas | 3 | 0.9733 | 0.9103 | **14/50** | 48/50 |
| {0,1,2} | mas | 2 | 0.9600 | 0.8659 | **37/50** | 48/50 |

Answers to the pre-registered question:

- **Single arm:** dropping repeat 0 changes **byte identity** (48/50 → 50/50) but not
  DAR or α (already 1.0). Per-repeat byte-deviation-from-modal: **r0 = 2/50, r1–r4 =
  0/50**. Textbook first-repeat artefact, identical in shape to deepseek-r1.
- **MAS arm:** dropping repeat 0 changes **DAR (0.9360 → 0.9733) and α (0.7802 →
  0.9101, +0.130)** and decision-identity (43 → 48/50), but **does not restore byte
  identity at all (0/50)**. The MAS warm-up spans *at least two* repeats: pairwise
  byte-identity counts are r3↔r4 **37/50**, r2↔r4 19/50, r2↔r3 15/50, but every pair
  involving r0 or r1 is ≤ 3/50. The single-arm remedy (drop repeat 0) is
  **insufficient for MAS**.

Mechanism, evidenced: `config.cache_policy = "none"`, and the manifest plan is
case-major (a case's repeats run consecutively — confirmed at the reboot boundary,
plan 653/654 are repeats 12/13 of the same case). Repeat 0 of every case is therefore
the first call against a cold prompt-prefix cache for that case; repeats 1–4 hit a warm
prefix. The harness *has* the mitigation — `runner.PREWARM_CONDITIONS = ("t0-fixed",
"pert-t0")` under `cache_policy="prewarm"` — but **this sweep ran with
`cache_policy="none"`, so it was never applied.** The global `_warm_up()` discard is
once per runner start, not per case, and does not address this.

Concrete illustration (single, TXN-2025-001, t0-fixed, all 5 decide `dismiss`):
repeat 0 emits a 448-char reasoned answer (743 completion tokens); repeats 1–4 emit the
bare 23-char string `FINAL DECISION: dismiss` (661 tokens). **The visible audit trail
disappears on warm calls.** Same pattern at TXN-2025-045. Any rationale-quality or
ROUGE analysis on this corpus is measuring cache state as much as model behaviour.

### 2.5 Degeneracy — **CONFIRMED, 10/10 cells** (but the driver is not what the modal-rate criterion suggests)

Label priors, computed per block (the correct denominators):

- Primary (n=50): dismiss 26, escalate 15, investigate 9 → **best constant baseline =
  always-`dismiss` at 0.5200**.
- Perturbation (n=10): dismiss 6, escalate 4 → **best constant baseline =
  always-`dismiss` at 0.6000**.

| arm | condition | escalate | dismiss | investigate | malformed | modal | **modal rate** | maj-acc | baseline | Δ |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| single | t0-fixed | 40 | 25 | 185 | 0 | investigate | **0.7400** | 0.3600 | 0.5200 | −0.1600 |
| single | t07-varied | 124 | 82 | 543 | 1 | investigate | **0.7240** | 0.3800 | 0.5200 | −0.1400 |
| single | pert-t0 | 20 | 5 | 25 | 0 | investigate | **0.5000** | 0.4000 | 0.6000 | −0.2000 |
| single | pert-t05 | 16 | 7 | 27 | 0 | investigate | **0.5400** | 0.3000 | 0.6000 | −0.3000 |
| single | pert-t10 | 19 | 6 | 25 | 0 | investigate | **0.5000** | 0.4000 | 0.6000 | −0.2000 |
| mas | t0-fixed | 44 | **0** | 206 | 0 | investigate | **0.8240** | 0.3200 | 0.5200 | −0.2000 |
| mas | t07-varied | 143 | **1** | 606 | 0 | investigate | **0.8080** | 0.2400 | 0.5200 | −0.2800 |
| mas | pert-t0 | 8 | **0** | 42 | 0 | investigate | **0.8400** | 0.1000 | 0.6000 | −0.5000 |
| mas | pert-t05 | 9 | **2** | 39 | 0 | investigate | **0.7800** | 0.1000 | 0.6000 | −0.5000 |
| mas | pert-t10 | 9 | **1** | 40 | 0 | investigate | **0.8000** | 0.1000 | 0.6000 | −0.5000 |

**Verdict: all 10 cells are degenerate — CONFIRMED. Every cell's majority-vote accuracy
is below the best constant-answer baseline, by −0.14 to −0.50.** An always-`dismiss`
stub outperforms both arms in every condition.

But the confirmation rests **entirely** on the below-baseline criterion. **No cell
reaches a 0.90 modal rate** (max 0.8400), and only 3 of 10 exceed 0.80. A reader who
takes "degenerate" to mean "answers one label almost always" would be misled: single's
perturbation cells are only 50–54 % modal. The honest statement is *"below a
constant-answer baseline in 10/10 cells; modal-answer concentration 0.50–0.84"*.

Supporting evidence that this is real degeneracy and not baseline pedantry:

- **MAS has effectively lost the `dismiss` class: 4 dismissals in 1150 runs (0.35 %)**,
  vs single's 125/1150 (10.9 %). `dismiss` is 26/50 of the primary labels — this single
  behaviour explains most of MAS's accuracy deficit.
- Per-case majority answers: MAS produces only **two distinct answers across all 50
  primary cases** (investigate 41, escalate 9) in both t0-fixed and t07-varied. Single
  produces three (investigate 37–38, escalate 8, dismiss 4–5).
- **The perturbation instrument fails in MAS.** Ground truth flips on 10/10
  perturbed pairs. Single's majority answer moves on 7/10 (pert-t0), 5/10, 5/10.
  **MAS moves on 2/10 in all three perturbation conditions.** MAS is nearly blind to
  the perturbation it exists to detect.

### 2.6 Tool channel — **FLAWED** (the liveness metric under-detects by ~15×)

Global census — every emitted name is inside the declared partition, no unknown tools:

| arm | total calls | check_sanctions_list | search_precedents | get_customer_profile | calculate_risk_score |
|---|---:|---:|---:|---:|---:|
| single | 4 702 | 1 991 | 1 161 | 427 | 1 123 |
| mas | 8 518 | 2 509 | 2 862 | 2 075 | 1 072 |

`tool_calls` entries are `str` in 100 % of cases (4 702 + 8 518) — the dict variant does
not occur in this sweep, though my parser handles both.

Node liveness by the declared tool-name partition — **I reproduce the seal check
exactly**:

| arm | node | dead runs | rate |
|---|---|---|---:|
| single | data | 1/1150 | 0.09 % |
| single | policy_risk | 28/1150 | 2.43 % |
| mas | **data** | **16/1150** | **1.39 %** |
| mas | **policy_risk** | **78/1150** | **6.78 %** |

Zero-tool runs: single 1/1150 (the infra-error run), MAS 7/1150. ✅ matches.

**Why those runs have no call — classified from evidence, not assumed:**

*MAS `policy_risk` dead (78 runs) — articulate conditional refusal, not truncation:*
- 74/78 contain explicit refusal or tool-unavailable language.
- Node output is **present and long** on every one: length min 1864, median 2946, max
  4023 chars; **0/78 empty**. Live runs median 3224. Not a silent node.
- `completion_tokens` median **3028 on dead runs vs 3729 on live** — dead runs produce
  *fewer* tokens. **This is the opposite of truncation.** No node output approaches a
  character cap (policy_risk max 6019 chars ≈ well under a 2048-token budget).
- Representative tail: *"…once those tool results are available, re-run
  `calculate_risk_score` with documented factors and reassess…"* — the node declines to
  score because it judges the upstream evidence insufficient.
- **Classification: model behaviour — conditional refusal on insufficient upstream
  evidence.** Not refusal-to-help, not error, not truncation.

*MAS `data` dead (16 runs) — conversational hand-back:*
- Node output present on all 16 (min 464, median 1796, max 2656 chars), 0 empty.
- 9 clean-output-no-call, 4 refusal language, 3 tool-unavailable language.
- `agent_messages` median **5 on dead runs vs 11 on live** — the run terminates with
  half the turns.
- Representative tails: *"Please confirm if you want me to proceed with the tool calls,
  or provide the entity legal names…"*, *"Please confirm if you want me to proceed with
  those tool calls, or provide the tool outputs for me to summarize."*
- **Classification: the data agent addresses the orchestrator as a human and requests
  permission instead of calling its tools.** A pipeline-role failure, not a refusal and
  not truncation.

*Single arm `policy_risk` dead (28 runs):* accuracy 0.2143 vs 0.3904 live; mean
completion tokens 578 vs 1008. 21 decide `investigate`, 6 `escalate`, 1 malformed
(the infra error). 5 of the 28 are all five repeats of `TXN-2025-009` at t0-fixed —
i.e. deterministic for that case, and the model emits a bare `FINAL DECISION:
investigate` with a single `search_precedents` call. Same family of behaviour: it
skips scoring and defaults to `investigate`.

**The finding the liveness check misses entirely:**

| MAS node | empty `node_outputs` text | median length |
|---|---:|---:|
| orchestrator | 0/1150 | 2048 |
| **data** | **226/1150 (19.7 %)** | 1103 |
| policy_risk | 0/1150 | 3212 |
| reporting | 0/1150 | 1683 |

**226 MAS runs have a completely empty `data` node output while having called the data
tools (mean 8.69 calls/run).** These are disjoint from the 16 "dead" runs. The evidence
is gathered and then silently dropped before it reaches the downstream nodes. Counting
tool calls cannot see this.

Union of broken evidence channels in MAS:

| failure combination | runs |
|---|---:|
| empty data text only | 155 |
| empty data text + no risk score | 71 |
| no data call only | 9 |
| no data call + no risk score | 7 |
| **total ≥1 broken channel** | **242/1150 = 21.04 %** |

Consequence, and it is the mechanism behind §2.5:

| set | n | accuracy | decisions |
|---|---:|---:|---|
| broken channel | 242 | **0.1446** | investigate 240, dismiss 1, escalate 1 |
| intact channel | 908 | **0.2753** | investigate 693, escalate 212, dismiss 3 |

**99.2 % of broken-channel runs answer `investigate`,** at half the accuracy of intact
runs. Both dead-node subsets are 100 % `investigate` (16/16 and 78/78). The degenerate
`investigate` mode is not (only) a model preference — **one fifth of MAS runs are
deciding with a severed evidence channel, and severance mechanically produces
`investigate`.** The seal check marks node liveness **[PASS]** on the 16- and 78-run
counts and never inspects the 226.

---

## 3. Reconciliation vs committed reports

Compared against `seal-checks.txt` (2026-08-15) and `experiments/CHANGELOG.md`
(2026-08-15 seal entry, 2026-08-14 deviation entry). **No `analysis-report.md` exists
for this sweep.**

### Agreements — exact

| quantity | committed | mine | status |
|---|---|---|---|
| single runs / MAS runs | 1150 / 1150 | 1150 / 1150 | ✅ |
| single tool calls/run min/median/max | 0 / 4 / 7 | 0 / 4 / 7 | ✅ |
| MAS tool calls/run min/median/max | 0 / 8 / 11 | 0 / 8 / 11 | ✅ |
| single zero-tool runs | 1/1150 | 1/1150 | ✅ |
| MAS zero-tool runs | 7/1150 | 7/1150 | ✅ |
| MAS `data` node dead | 16/1150 (1.4 %) | 16/1150 (1.39 %) | ✅ |
| MAS `policy_risk` node dead | 78/1150 (6.8 %) | 78/1150 (6.78 %) | ✅ |
| modal rates, single (5 cells) | 74.0/72.4/50.0/54.0/50.0 % | identical | ✅ |
| modal rates, MAS (5 cells) | 82.4/80.8/84.0/78.0/80.0 % | identical | ✅ |
| MV-acc, single (5 cells) | 0.360/0.380/0.400/0.300/0.400 | identical | ✅ |
| MV-acc, MAS (4 of 5 cells) | 0.320/0.240/0.100/0.100 | identical | ✅ |
| constant baselines | 0.520 primary / 0.600 perturbation | identical | ✅ |
| degeneracy flagged in all 10 cells | yes | yes | ✅ |
| "stopped at MAS 653" | 653/1150 | plan position 653 confirmed | ✅ |
| "resumed losslessly" | claimed | verified (4 independent checks) | ✅ |
| "no second infra context (0.32.9 throughout)" | claimed | verified uniform | ✅ |
| "single sealed 1150/1150, finished 11:52 UTC" | claimed | `max(started_at)` = 11:52:47Z | ✅ |
| "1 journalled error, single arm, outcome category not excluded" | claimed | verified | ✅ |
| "resume-point run key identifiable from the timestamp gap" | claimed | identified: `mas:TXN-2025-027:t07-varied:13` | ✅ |

### Disagreements

**D1 — `MAS pert-t10` majority-vote accuracy: committed 0.000, correct value 0.100.**
*This is the number the CHANGELOG headlines* ("Worst: MAS pert-t10 MV accuracy **0.000**
vs 0.600 baseline — the perturbation instrument check fails hard in the MAS arm").

Root cause: an undeclared tie-breaking rule in the seal check.
`analysis/seal_checks_muse_glimmer.py:94` uses `v.most_common(1)[0][0]`, whose tie-break
is **Counter insertion order (first-observed decision)**. The project's *locked*
convention is **canonical outcome order**, implemented in
`analysis/metrics.py:majority_vote` ("ties broken by canonical OUTCOMES order") and
documented in `analysis/report.py:175` ("escalate > dismiss > investigate >
malformed").

The single affected cell is **PERT-001 at MAS/pert-t10**: decisions are
`{investigate: 2, escalate: 2, dismiss: 1}` — a genuine 2–2 tie — with ground truth
`escalate`. Canonical order → `escalate` → correct → MV-acc 0.100. First-observed →
`investigate` → wrong → MV-acc 0.000.

Note the CHANGELOG entry of 2026-08-14 explicitly fixed this exact caption defect and
asserted *"no number changes — the conventions agree in every cell of both thinking
sweeps"*. That assertion was true of those sweeps; **it is false for this one**, and the
seal check written afterwards reintroduced the non-canonical convention. The
qualitative conclusion (degenerate, far below the 0.600 baseline) is unaffected; the
headline figure is not.

**D2 — `progress.json` mean wall clock does not reconcile with the journals.**
MAS `mean_wall_clock_s: 85.08` vs recomputed **95.830** (+12.6 %); single `39.41` vs
recomputed **39.548**. `progress.json` is timestamped after the seal with `done: 2300`.
Not attributable to any prefix/suffix/session window. Not referenced by
`seal-checks.txt`, but it is a committed artefact in the sealed directory.

**D3 — `seal-checks.txt` prints a pooled label prior beside per-block baselines.**
It reports `label prior: {'investigate': 9, 'dismiss': 32, 'escalate': 19} (modal
dismiss 53.3%)` — that is the **60-case union** of the primary (50) and perturbation
(10) blocks. It then prints per-condition baselines of 0.520 and 0.600, which are the
correct **per-block** priors. The 53.3 % figure is the baseline for no cell in the
table and appears once per arm directly above the cells it does not describe. My
per-block priors: primary {dismiss 26, escalate 15, investigate 9} → 0.5200;
perturbation {dismiss 6, escalate 4} → 0.6000.

**D4 — the seal check's degeneracy criterion is `modal_rate > 0.80 OR mv_acc <
baseline`; only the second disjunct ever fires meaningfully.** 7 of 10 cells fail the
modal-rate test (rates 0.50–0.78) and are flagged solely on the baseline comparison.
The CHANGELOG's prose — "Modal `investigate` 72–74 % (single) / 78–84 % (MAS) against a
53 % dismiss prior" — compares modal rates to the *pooled* 53.3 % prior (D3), which is
a category error: a modal *decision* rate and a modal *label* rate are not comparable
quantities, and the correct comparison (majority accuracy vs constant baseline) is the
one that actually carries the finding.

**D5 — an undeclared interruption is absent from the deviation record.** The
simultaneous 458 s / 457 s excess stall in both arms resuming at
`2026-08-14T05:25:45Z` (§2.2b) appears in no committed document. Benign in the journals,
but the deviation record is presented as complete.

**D6 — corpus summary-table cost figures are gate probes, not sweep values, and differ
substantially.** `CHANGELOG.md:399` lists muse-glimmer:30b as `A/B wall s = 15.9 / 76.4`
and `A/B compl. tok = 637 / 3604`, ETA 24.4 h. Journal-derived sweep values:
**wall 39.55 / 95.83 s**, **completion tokens 997.3 / 3746.2**, actual span
2026-08-13T23:05:57Z → 2026-08-15T06:07:37Z = **31.0 h**. The table's column headers do
not state these are pilot-gate measurements. Single-arm wall clock is understated 2.5×
and completion tokens 1.6× relative to the sweep. If the dissertation cites this table
as sweep cost, it is wrong.

**D7 — "determ. PASS 8/8" in the corpus table does not hold for the MAS arm.** Gate G1
(`harness/gates.py:109`) tests T=0 fixed-seed byte identity on **direct single calls
with an explicit warm-up**. The MAS arm of this sweep is byte-identical in **0/60**
fixed-seed groups (§2.4). The table presents determinism as a per-model admission
property; it is a per-endpoint property that does not survive the 4-node pipeline.

---

## 4. Ranked threats (severity order) with mitigations

**T1 — CRITICAL. Repeats within a group are not independent draws; the prompt-prefix
cache is a hidden factor in every repeatability metric.**
The plan is case-major and `cache_policy="none"`, so repeat 0 of every case runs cold
and repeats 1–4 run warm. Evidence: single per-repeat byte-deviation r0=2/50,
r1–r4=0/50; MAS pairwise byte identity r3↔r4 37/50 versus ≤3/50 for any pair involving
r0 or r1; MAS α moves **+0.130** (0.7802 → 0.9101) on dropping repeat 0 alone. DAR, α,
flip rate and pass^k for the T=0 conditions are all partly measuring server cache state.
The most vivid case: single/TXN-2025-001 repeat 0 emits a 448-char rationale and repeats
1–4 emit a bare 23-char decision line — **the rationale itself is cache-state
dependent**, which contaminates any rationale-quality analysis downstream.
*Not acknowledged for this sweep.* The project documents a "first-evaluation cache-state
mechanism" and ships the fix (`cache_policy="prewarm"`, `PREWARM_CONDITIONS`), but this
sweep ran with `none`, and the CHANGELOG asserts the residual is "confined to the first
scored run after resume" — which understates a per-case, sweep-wide effect.
*Mitigation:* (a) report T=0 metrics with repeats {0,1} excluded as primary and the full
set as sensitivity, stating both; (b) for any future sweep, enable
`cache_policy="prewarm"`; (c) state explicitly that MAS needs ≥2 warm repeats, not 1.

**T2 — CRITICAL. One fifth of MAS runs decide with a severed evidence channel, and the
declared liveness check cannot see it.**
242/1150 (21.04 %) MAS runs have ≥1 broken evidence channel — dominated by **226 runs
whose `data` node emits zero characters despite averaging 8.69 tool calls**. 240/242
answer `investigate`; accuracy 0.1446 vs 0.2753 for intact runs. The seal check counts
only tool-call absence (16 + 78) and returns **[PASS]**.
*Not acknowledged.* The project acknowledges empty-node-output as a phenomenon, but only
for the `reporting` node in other sweeps and attributed to `num_predict` exhaustion —
which is refuted here (dead/empty runs produce *fewer* tokens than live ones, and no
node output approaches a length cap).
*Mitigation:* add `len(node_outputs[node]) == 0` to the seal checks as a first-class
liveness criterion; re-report MAS metrics conditional on an intact channel; treat the
MAS degeneracy finding as *at least partly* a pipeline defect rather than a model
property, and say so.

**T3 — HIGH. A committed headline number is wrong because the seal check uses a
tie-break the project explicitly retired.**
MAS pert-t10 MV-acc is **0.100**, not the committed **0.000**
(`seal_checks_muse_glimmer.py:94` `Counter.most_common` vs the locked canonical order in
`metrics.py:majority_vote`). Affects exactly one cell (PERT-001, a 2–2 tie), but it is
the cell the CHANGELOG quotes as the worst result in the sweep.
*Mitigation:* import `metrics.majority_vote` in the seal checks rather than
reimplementing; regenerate `seal-checks.txt`; correct the CHANGELOG sentence. Re-run the
same check against the other sweeps sealed under this script.

**T4 — HIGH. Wall-clock cost figures are not comparable across arms or across
conditions within the MAS arm.**
The two arms ran **concurrently on one GPU** from 2026-08-13T23:05:57Z until the single
arm finished at 2026-08-14T11:52:47Z. MAS wall clock: **139.40 s** under co-residency
(n=327) vs **78.52 s** solo (n=823) — a **1.775× inflation**. The single arm was 100 %
contended. Worse, the regimes align with condition boundaries: **MAS `t0-fixed` is
250/250 contended (138.6 s); MAS `pert-t0`/`pert-t05`/`pert-t10` are 50/50 solo
(80.0/84.7/82.3 s)**. So a within-arm wall-clock comparison across conditions measures
scheduling, not workload. The reported MAS/single ratio of 2.423× mixes regimes; the
matched-contention ratio is 3.52×; a matched-solo ratio is unmeasurable because the
single arm has no solo runs. Decision distributions do not differ meaningfully across
the regimes, so *decision* metrics are unaffected.
*Partially acknowledged*: the CHANGELOG says "wall-clock remains indicative only under
co-residency; tokens are the cost metric" — but only in the @think launch paragraph, and
it does not note that the contention regime changes *within* this sweep and correlates
perfectly with condition.
*Mitigation:* drop wall clock from all cost claims for this sweep; use the token ratio
(**2.372×**, contention-invariant); if latency is needed, report the solo-only MAS mean
and mark all single-arm latency as contended.

**T5 — MEDIUM. The admission gate certifies determinism the sweep does not have.**
`determ. PASS 8/8` is a direct-endpoint property measured with an explicit warm-up; the
MAS arm is byte-identical in 0/60 fixed-seed groups and flips *decisions* in 9/60. A
model admitted on "determinism PASS" can be fully nondeterministic in the arm that the
dissertation's central comparison depends on.
*Mitigation:* add a MAS-arm determinism probe to the gate (n repeats of one case at
T=0/seed 42 through the full graph), and relabel the table column as
"single-call determinism".

**T6 — MEDIUM. `progress.json` is a sealed artefact that does not reconcile with the
raw journals** (MAS mean wall clock 85.08 vs 95.830, +12.6 %). Any figure sourced from
it is wrong by an unknown mechanism.
*Mitigation:* regenerate `progress.json` from the journals at seal time, or delete it
from the sealed set and mark the journals as the sole source of truth.

**T7 — MEDIUM. An infrastructure fault is scored as a model outcome.**
The sweep's only `malformed` outcome is an Ollama 0.32.9 HTTP 500 tool-parse fault with
zero tokens generated. It is included per pre-registration, which is defensible, but it
means "malformed rate" for `single/t07-varied` is 100 % infrastructure-caused and 0 %
model-caused. Reporting a malformed rate without that annotation misattributes a server
defect to the model.
*Mitigation:* report `error != null` and `decision == malformed` as separate columns
everywhere; keep the run in the denominator but annotate the cause.

**T8 — MEDIUM. The perturbation instrument does not discriminate in the MAS arm.**
Ground truth flips on 10/10 perturbed pairs; the MAS majority answer moves on **2/10**
in every perturbation condition (single: 7/10, 5/10, 5/10). Combined with MAS's near-
total loss of the `dismiss` class (4/1150), the perturbation block has close to zero
power to detect MAS sensitivity. Any claim of the form "MAS is/is not robust to
perturbation" is unsupported by this instrument at n=10.
*Mitigation:* state the perturbation block as underpowered for MAS; do not report MAS
perturbation pass^k as a robustness measure without the 2/10 movement figure beside it.

**T9 — LOW. The interruption detector is mis-calibrated and the deviation record is
incomplete by one event.**
A 600 s absolute threshold caught the 1009 s reboot and missed a synchronous 599 s /
502 s dual-arm stall (458 s / 457 s in excess of the preceding run's wall clock)
resuming at 2026-08-14T05:25:45Z. No data loss is detectable from it.
*Mitigation:* switch the detector to "gap minus preceding `wall_clock_s` > 120 s", which
flags both events and nothing else in this sweep; add the 05:25 event to the deviation
record as benign-but-declared.

**T10 — LOW. `completion_tokens ≥ num_predict` is a broken truncation proxy for
multi-node arms** and fires on 1150/1150 MAS runs (run-summed tokens against a per-call
cap). The project retracted one classifier for exactly this error on 2026-08-14; the
trap remains available in the journal schema, which records no per-node token counts.
*Mitigation:* record per-node `prompt_tokens`/`completion_tokens` in `node_outputs` for
future sweeps; until then, do not attempt per-node truncation attribution.

**T11 — LOW here, but a latent CRITICAL process defect: a sealed directory was written
to by the next sweep.** 882 652 bytes were appended to
`results-muse-glimmer-30b/serve-armB-postreboot.log` after seal commit `9be3958`, by the
`@think` pair launched on the same arm-B server path (§2.1 caveat 3). Every analysis
input is hash-identical to the seal, so this sweep's numbers are unaffected — but the
mechanism (successor sweep reusing a predecessor's output path) would corrupt a journal
just as easily as a log, and would do so invisibly. The abstract's claim that sweeps are
"sealed" is, as implemented, a claim about a git commit, not about the directory.
*Mitigation:* make sealed directories read-only (`chmod -R a-w`) at seal time; give each
sweep's server log a path namespaced by results-dir; add a post-seal hash manifest
(`SHA256SUMS`) to each sealed directory and re-verify it before any analysis; bring
`runner-*.log` inside the seal instead of gitignoring it.

---

## 5. What I did NOT verify

Explicitly out of scope or impossible without violating the constraints:

1. **Anything requiring model execution.** Zero LLM calls were made. I cannot verify
   that `raw_output` was actually produced by `muse-glimmer:30b` at digest
   `de878ce33ad8…`, that the recorded seeds were the seeds passed to the server, or
   that the outputs are reproducible.
2. **Tool correctness.** I did not verify that `harness/dfah_tools.py` returns correct
   sanctions/profile/precedent/risk data. A systematically wrong tool oracle would
   produce exactly the journals I audited and would fully explain the degeneracy. This
   is the single largest unverified alternative explanation for §2.5.
3. **Ground-truth label validity.** `ground_truth` in `alerts.json` and
   `perturbation_cases.json` was taken as given. The `investigate` class is only 9/50;
   I did not assess whether the rulebook and the labels are mutually consistent — a
   rulebook that over-licenses `investigate` would also produce these results.
4. **Per-node token accounting.** The journal records only run-level `prompt_tokens` and
   `completion_tokens`. All per-node truncation reasoning is inferential (via output
   lengths and total-token comparisons), not measured.
5. **The runner and server logs.** `runner-mas.log` (1.2 MB), `runner-single.log`
   (0.7 MB) and `serve-armB-postreboot.log` (35 MB) were not audited. They may contain
   retries, non-fatal errors, or prewarm activity invisible in the journals. The
   05:25 dual-arm stall (T9) would most likely be explained there. Note the two runner
   logs are gitignored and so have no sealed baseline to audit *against* even if read,
   and the server log has provably been appended to since the seal (T11).
6. **`git_sha` / `config_hash` correspondence.** I did not verify that
   `41de08925f37…` / `a720737f7798…` correspond to the code that actually executed, nor
   that the current working tree matches them.
7. **Gate evidence.** `gates/mini-gates.json` was not audited; gate claims (8/8 pilot,
   determinism PASS, think-probe clean) are taken from the CHANGELOG at face value
   except where the sweep itself contradicts them (D7).
8. **Prompt integrity.** I read the system prompts in `manifest.config.prompts` but did
   not verify that the strings sent at run time matched them.
9. **Cross-sweep comparisons.** No other results directory was recomputed. Statements
   about deepseek-r1, granite4.1 or the qwen sweeps are quoted from the CHANGELOG, not
   independently verified.
10. **`results-muse-glimmer-30b-thinking/`** — untouched by design (sweep in flight).
11. **Statistical multiplicity.** The two arm-difference p-values (0.0121, 0.0036) are
    unadjusted; I did not apply a family-wise correction across the full metric set,
    and the perturbation test has n=10 cases.
