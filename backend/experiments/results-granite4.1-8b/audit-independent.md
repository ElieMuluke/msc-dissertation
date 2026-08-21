# Independent Audit — `results-granite4.1-8b`

**Auditor:** independent recomputation, blind-first protocol
**Date:** 2026-08-14
**Scope:** 2,300 sealed runs (`journal-single.jsonl` 1,150 + `journal-mas.jsonl` 1,150)
**Method:** pure-Python recomputation from `manifest.json`, the two journals, and the
benchmark label files. Nothing imported from the project's own `analysis/` package.
No LLM calls, no GPU, no network. Scripts:
`backend/experiments/analysis/eval_granite_integrity.py`,
`backend/experiments/analysis/eval_granite_metrics.py`.

**Blindness:** all numbers in §1–§4 were derived and written before
`analysis-report.md` or `backend/experiments/CHANGELOG.md` were opened. §5 is the
reconciliation performed afterwards.

---

## 0. Headline

Primary block (50 labelled cases), independently recomputed:

| Arm | Condition | reps | pass^1 | pass^5 | pass^15 | DAR | Kripp. α | flip-rate (case) | MV-acc | norm. entropy | tok/run | wall/run |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| single | t0-fixed (T=0, seed 42) | 5 | 0.2880 | 0.2200 | – | 0.9600 | 0.848 | 0.100 | 0.300 | 0.046 | 4,373 | 4.10 s |
| single | t07-varied (T=0.7) | 15 | 0.2987 | 0.1708 | 0.1200 | 0.8299 | 0.328 | 0.620 | 0.240 | 0.234 | 4,343 | 4.45 s |
| mas | t0-fixed (T=0, seed 42) | 5 | 0.3360 | 0.2200 | – | 0.8680 | 0.511 | 0.280 | 0.340 | 0.143 | 7,667 | 13.81 s |
| mas | t07-varied (T=0.7) | 15 | 0.2893 | 0.1798 | 0.1600 | 0.8451 | 0.297 | 0.500 | 0.220 | 0.209 | 8,380 | 11.38 s |

Perturbation block (10 cases):

| Arm | Condition | pass^1 | pass^5 | DAR | Kripp. α | flip-rate | MV-acc | norm. entropy |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| single | pert-t0 | 0.2000 | 0.2000 | 0.9600 | 0.886 | 0.100 | 0.200 | 0.046 |
| single | pert-t05 | 0.1200 | 0.0000 | 0.8600 | 0.596 | 0.300 | 0.100 | 0.152 |
| single | pert-t10 | 0.1600 | 0.0000 | 0.7100 | 0.226 | 0.500 | 0.000 | 0.316 |
| mas | pert-t0 | 0.0400 | 0.0000 | 0.8400 | 0.521 | 0.400 | 0.000 | 0.182 |
| mas | pert-t05 | 0.0400 | 0.0000 | 0.8400 | 0.437 | 0.400 | 0.000 | 0.182 |
| mas | pert-t10 | 0.0800 | 0.0000 | 0.7800 | 0.285 | 0.400 | 0.100 | 0.229 |

**The four things that matter:**

1. **The data are clean.** 2,300/2,300 planned runs present, zero duplicates, zero
   missing, zero errors, zero plan deviations, uniform model digest and Ollama
   version. Integrity is not the problem.
2. **The measured system is degenerate.** It answers `investigate` on 85.6 %
   (single) / 86.9 % (mas) of all primary runs, against a label prior of 18 %.
   Majority-vote accuracy (0.22–0.34) is **below the constant-`dismiss` baseline of
   0.520**. Recall is 1.000 on `investigate` and 0.038–0.077 on the other two
   classes. Every agreement/reliability number in this sweep is therefore measuring
   mode collapse, not competence.
3. **T=0 with a fixed seed is not deterministic**, and the MAS byte-determinism
   figure derived from `raw_output` is an artefact (§3.2). Corrected full-trace
   byte-identity: single 14.0 %, **mas 0.0 %**.
4. **MAS buys nothing and costs 1.85× tokens / ≥2.65× wall-clock.** No arm
   difference in accuracy is significant anywhere. The only significant arm effects
   run *against* MAS: at T=0 it is less stable (ΔDAR −0.092, 95 % CI
   [−0.168, −0.020], permutation p = 0.019).

---

## 1. Data integrity — verdict: **SOUND**

### 1.1 Counts and coverage

| Check | Result |
|---|---|
| `journal-single.jsonl` rows | 1,150 (0 unparseable) |
| `journal-mas.jsonl` rows | 1,150 (0 unparseable) |
| Total vs `manifest.totals` (1,150 + 1,150) | 2,300 = 2,300 ✔ |
| `progress.json.done` | 2,300 ✔ |
| Arm purity of each file | 100 % ✔ |
| Duplicate `(arm, case_id, condition, repeat_idx)` keys | **0** |
| Planned-but-missing keys | **0** |
| Run-but-unplanned keys | **0** |
| Duplicate `run_id` | **0** |
| Cell counts (arm × condition), all 10 cells | all match expectation exactly |

Cell design confirmed: primary 50 cases × (5 + 15) + perturbation 10 cases ×
(5 + 5 + 5) = 1,150 per arm.

### 1.2 Conformance to the pre-generated plan

Every run was joined to its manifest entry on the 4-tuple key.

- `seed` mismatches: **0**
- `temperature` mismatches: **0**
- `block` mismatches: **0**
- `temperature` vs the condition contract in `config.conditions`: **0** violations
- `fixed_seed` vs the condition contract: **0** violations

Seed discipline per condition is exactly as designed:

| Condition | n | distinct seeds | seeds per (arm, case) group | config `fixed_seed` |
|---|---:|---:|---|---|
| t0-fixed | 500 | 1 (=42) | 1 | 42 |
| pert-t0 | 100 | 1 (=42) | 1 | 42 |
| t07-varied | 1,500 | 750 | 15 (all distinct) | null |
| pert-t05 | 100 | 50 | 5 (all distinct) | null |
| pert-t10 | 100 | 50 | 5 (all distinct) | null |

### 1.3 Environment uniformity

| Field | Distinct values |
|---|---|
| `model` | `granite4.1:8b` (2,300) |
| `model_digest` | `444af1c4…ba2852` (2,300) — matches manifest |
| **`ollama_version`** | **`0.32.9` (2,300) — uniform, both arms** |
| `num_predict` | 2048 (2,300) |
| `think` | null (2,300) |
| `cache_policy` | `none` (2,300) |
| `env.gpu_name` | NVIDIA RTX PRO 5000 Blackwell (2,300) |
| `env.gpu_driver` | 595.71 (2,300) |
| `env.host_load_high` | `false` (2,300) |

**No Ollama-version split exists inside this sweep.** The confound the audit brief
anticipated is *not* present in the journals. It is present only in the directory's
provenance (§1.6).

### 1.4 Decision domain and error accounting

- Decision domain: exactly `{escalate, dismiss, investigate}` — no nulls, no
  out-of-domain values.
- Rows with non-null `error`: **0**
- Rows with empty `raw_output`: **0**
- Rows with zero `completion_tokens`: **0**
- Recorded `decision` vs decision re-parsed from `raw_output` by an independent
  parser: **0 mismatches** on all 2,294 rows where a strict `FINAL DECISION:` tail
  parses.
- The 6 remaining rows use markdown-bolded `**Final Decision**: investigate`, which
  splits the literal `FINAL DECISION:` token. The recorded decision is correct in all
  6. **Not a defect** — the harness parser is more robust than a naive tail match.
  Listed for completeness: `single:TXN-2025-013:t07-varied:0`,
  `single:TXN-2025-047:t07-varied:8`, `mas:TXN-2025-006:t0-fixed:0`,
  `mas:TXN-2025-004:t07-varied:3`, `mas:TXN-2025-019:t07-varied:2`,
  `mas:PERT-007:pert-t05:3`.

### 1.5 Timeline

| Arm | First run | Last run | Span | Gaps > 10 min | Non-monotonic steps |
|---|---|---|---:|---:|---:|
| single | 2026-08-13 19:09:29 Z | 2026-08-13 20:37:05 Z | 1.46 h | **0** | 0 |
| mas | 2026-08-13 19:09:29 Z | 2026-08-13 22:58:58 Z | 3.82 h | **0** | 0 |

No stalls, no retro-dated rows, no interleaving anomalies. **But the two arms ran
concurrently on one GPU** — see §6, threat T3.

### 1.6 The two-manifest finding — verdict: **SOUND-WITH-CAVEATS**

`manifest.json` and `manifest-ollama0326.json` are the same size (576,848 bytes) but
different files:

| Field | `manifest.json` | `manifest-ollama0326.json` |
|---|---|---|
| `created_at` | 2026-08-11T19:12:26Z | 2026-08-11T18:12:19Z |
| `ollama_version` | **0.32.9** | **0.32.6** |
| `git_sha` | `41de0892…` (commit 2026-08-11 19:58 +0100) | `d712ef13…` (commit 2026-08-11 15:28 +0100) |
| `config_hash` | `c3658d08…` | `c3658d08…` — **identical** |
| `runs` array | 2,300 entries | 2,300 entries — **byte-for-byte identical plan** |

**Interpretation.** This is *not* a within-sweep infrastructure split. It is a
**re-pinning of the same experimental plan against a new Ollama runtime**. One hour
apart, the plan was regenerated after an Ollama 0.32.6 → 0.32.9 upgrade. The
experimental design (`config_hash`, all 2,300 run specs) is bit-identical across
both; only the runtime provenance stamp changed. This is corroborated by
`gates/`, which contains the matching pair:

- `gates/mini-gates.json` — dated 2026-08-11T18:12:41Z, no `ollama_version` field
  (pre-upgrade schema), 22 s after the 0326 manifest.
- `gates/mini-gates-ollama0329.json` — dated 2026-08-11T19:14:32Z, records
  `ollama_version: {single: 0.32.9, mas: 0.32.9}`, 126 s after `manifest.json`.

Both gate batteries report the identical determinism SHA
(`92dbf515…f914c31`, 5/5 identical, `output_len` 586) — i.e. the upgrade did not
change the canary output.

**Significance for the audit (three points):**

1. **The journals unambiguously correspond to `manifest.json`.** All 2,300 rows carry
   `ollama_version = 0.32.9`. `manifest-ollama0326.json` is a **superseded artefact**
   with no runs attached to it. No results are contaminated.
2. **It is nevertheless a provenance hazard.** The directory ships two manifests with
   no `SUPERSEDED` marker, no README, and no field inside either file pointing at the
   other. A reader — or a downstream script that globs `manifest*.json` — can trivially
   bind results to the wrong runtime stamp. The filename is the only disambiguator,
   and it is a naming convention, not a machine-checkable one.
3. **A real, unclosed provenance gap sits underneath it.** Both manifests were
   generated on **2026-08-11**; the sweep executed on **2026-08-13**, two days later.
   The `git_sha` recorded in `manifest.json` (`41de0892…`) is the plan-generation SHA,
   **not the execution SHA**. Two commits touching experiment code landed in between
   (`722a9ce` "thinking-on track + inverted gate criterion; 0.32.9 gate battery",
   `c64495c` "pre-register qwen3.5:9b@think-budget"). Neither obviously alters the
   granite thinking-off path — `think` is null in all 2,300 rows and `config_hash`
   matches — but **nothing in the sealed artefact proves the harness that ran on
   Aug 13 is the harness described by the Aug 11 SHA.**

**Recommended (non-destructive) mitigation:** add a `PROVENANCE.md` to this directory
stating that `manifest-ollama0326.json` is superseded, and record an *execution*
git SHA in `progress.json` on future sweeps. Do not delete the second manifest — it
is the evidence of the upgrade.

---

## 2. Recomputed metrics — verdict: **SOUND (computation) / see §4 for interpretation**

### 2.1 Estimator definitions used

Stated explicitly so any disagreement in §5 can be attributed.

- **pass^k** — repeatability, *not* pass@k. Unbiased hypergeometric estimator
  `C(c, k) / C(n, k)` where `c` = correct repeats out of `n`, averaged over cases.
  Reported for k ≤ n only.
- **DAR** — mean over cases of within-case pairwise decision agreement,
  `Σ_v C(n_v, 2) / C(n, 2)`.
- **Krippendorff's α (nominal)** — units = cases, observations = repeats; coincidence
  matrix with `1/(m−1)` weighting; `α = 1 − D_o/D_e`. Undefined when `D_e = 0`
  (no between-case variation). No cell was undefined here.
- **Flip rate** — fraction of cases exhibiting ≥ 2 distinct decisions across repeats
  (case-level). Pairwise flip rate is `1 − DAR`.
- **Normalised entropy** — Shannon entropy of the within-case decision distribution
  divided by `ln 3`, averaged over cases.
- **Trajectory metrics** — over `tool_calls` *name sequences*, all within-case pairs:
  exact-order agreement (sequences identical), Jaccard over the call *sets*, and
  normalised LCS (`LCS / max(len)`).
- **Arm difference** — paired over cases; 10,000-resample bootstrap over cases for the
  95 % CI, 10,000-relabelling paired permutation test for p. Seed 20260814.

### 2.2 Trajectory metrics

| Arm | Condition | exact-order | Jaccard | norm. LCS | mean tool calls |
|---|---|---:|---:|---:|---:|
| single | t0-fixed | 0.9440 | 0.9913 | 0.9853 | 3.53 |
| single | t07-varied | 0.4438 | 0.8837 | 0.7735 | 3.47 |
| single | pert-t0 | 1.0000 | 1.0000 | 1.0000 | 4.40 |
| single | pert-t05 | 0.5500 | 0.8800 | 0.8620 | 4.08 |
| single | pert-t10 | 0.3500 | 0.8567 | 0.7572 | 4.14 |
| mas | t0-fixed | 0.8720 | 0.9980 | 0.9714 | 5.31 |
| mas | t07-varied | 0.4067 | 0.9940 | 0.8639 | 5.31 |
| mas | pert-t0 | 0.9200 | 1.0000 | 0.9876 | 5.44 |
| mas | pert-t05 | 0.4100 | 1.0000 | 0.8878 | 5.62 |
| mas | pert-t10 | 0.3200 | 1.0000 | 0.8683 | 5.74 |

Note the metric-choice sensitivity: on **Jaccard**, MAS looks *more* stable
(0.994 vs 0.884 at T=0.7); on **exact-order**, MAS looks *less* stable
(0.407 vs 0.444). MAS's tool *set* is nearly fixed by the pipeline's static
tool partition (`data` node owns 3 tools, `policy_risk` owns 1), so Jaccard is close
to structurally guaranteed and is a weak reliability signal for that arm. Only 18
distinct tool sequences occur across all 1,150 MAS runs versus 56 across single.
**Jaccard should not be used to compare architectures with different tool
partitions.**

### 2.3 Cost

| Arm | Condition | prompt tok | completion tok | total tok | wall s |
|---|---|---:|---:|---:|---:|
| single | t0-fixed | 4,120.4 | 252.6 | 4,373.0 | 4.10 |
| single | t07-varied | 4,059.9 | 283.5 | 4,343.4 | 4.45 |
| single | pert-t0 | 5,168.2 | 303.0 | 5,471.2 | 4.87 |
| single | pert-t05 | 4,805.0 | 328.3 | 5,133.3 | 5.12 |
| single | pert-t10 | 4,879.3 | 348.1 | 5,227.4 | 5.37 |
| mas | t0-fixed | 6,672.4 | 994.9 | 7,667.3 | 13.81 |
| mas | t07-varied | 7,360.5 | 1,019.6 | 8,380.1 | 11.38 |
| mas | pert-t0 | 7,897.5 | 1,006.2 | 8,903.7 | 10.62 |
| mas | pert-t05 | 7,723.7 | 1,045.7 | 8,769.4 | 10.92 |
| mas | pert-t10 | 7,671.5 | 1,072.1 | 8,743.6 | 11.16 |

Sweep totals — single: 4,817,633 prompt + 324,739 completion = **5,142,372** tokens,
1.43 h summed wall. mas: 8,353,102 + 1,169,606 = **9,522,708** tokens, 3.78 h summed
wall. **MAS/single = 1.85× tokens, 2.65× wall-clock** (see §6 T3: 2.65× is a
*lower bound*).

### 2.4 Cost of reliability (tokens ÷ pass^k)

t07-varied, primary block:

| Arm | k | pass^k | tok/run | tok ÷ pass^k |
|---|---:|---:|---:|---:|
| single | 1 | 0.2987 | 4,343 | 14,543 |
| single | 5 | 0.1708 | 4,343 | 25,429 |
| single | 15 | 0.1200 | 4,343 | 36,195 |
| mas | 1 | 0.2893 | 8,380 | 28,963 |
| mas | 5 | 0.1798 | 8,380 | 46,616 |
| mas | 15 | 0.1600 | 8,380 | 52,375 |

t0-fixed: single 15,184 (k=1) / 19,877 (k=5); mas 22,819 / 34,851.

MAS is **1.45×–2.0× more expensive per unit of repeatable correctness** at every k.
Caveat: because both arms sit below the constant-class baseline (§4), this ratio
prices a product neither arm actually delivers.

### 2.5 Arm difference (MAS − single), paired over cases

10,000-resample bootstrap CI; 10,000-relabelling paired permutation p.

| Condition | Metric | Δ | CI95 low | CI95 high | perm p |
|---|---|---:|---:|---:|---:|
| t0-fixed | pass^1 | +0.0480 | −0.0400 | +0.1360 | 0.333 |
| t0-fixed | **DAR** | **−0.0920** | **−0.1680** | **−0.0200** | **0.019** |
| t0-fixed | **flip-rate** | **+0.1800** | **+0.0200** | **+0.3400** | **0.047** |
| t0-fixed | **norm-entropy** | **+0.0977** | **+0.0185** | **+0.1769** | **0.018** |
| t0-fixed | MV-accuracy | +0.0400 | −0.0600 | +0.1600 | 0.720 |
| t0-fixed | mean-accuracy | +0.0480 | −0.0360 | +0.1360 | 0.334 |
| t0-fixed | traj-exact | −0.0720 | −0.1440 | 0.0000 | 0.079 |
| t07-varied | pass^1 | −0.0093 | −0.0467 | +0.0267 | 0.674 |
| t07-varied | DAR | +0.0152 | −0.0297 | +0.0604 | 0.532 |
| t07-varied | flip-rate | −0.1200 | −0.2600 | +0.0200 | 0.176 |
| pert-t05 | MV-accuracy | −0.1000 | −0.3000 | 0.0000 | 1.000 |
| pert-t10 | MV-accuracy | +0.1000 | 0.0000 | +0.3000 | 1.000 |

**Reading.** No accuracy difference is significant in any condition. The three
significant effects all appear in `t0-fixed` and all favour **single**: MAS is less
agreeing, flips on more cases, and has higher decision entropy at temperature 0.
These three are not independent tests — they are three views of the same underlying
quantity — so treat them as one finding, not three. With 35 comparisons run in this
table and no multiplicity correction, p = 0.019/0.047/0.018 would not individually
survive Bonferroni (α/35 ≈ 0.0014); the finding is **suggestive, corroborated by the
§3 determinism counts, and should be reported as such rather than as a confirmed
effect**.

---

## 3. T=0 fixed-seed behaviour — verdict: **FLAWED (as an instrument, per §3.2)**

Both `t0-fixed` and `pert-t0` use `temperature = 0.0, seed = 42`, 5 repeats.
Only one Ollama version (0.32.9) is present in the sweep, so no per-version split is
required or possible.

### 3.1 Observed stability

| Condition | Arm | cases | byte-identical | decision-identical | tool-seq identical | completion_tokens identical |
|---|---|---:|---:|---:|---:|---:|
| t0-fixed | single | 50 | 7/50 (14.0 %) | 45/50 (90.0 %) | 43/50 | 7/50 |
| t0-fixed | mas | 50 | 12/50 (24.0 %) † | 36/50 (72.0 %) | 34/50 | **0/50** |
| pert-t0 | single | 10 | 1/10 (10.0 %) | 9/10 (90.0 %) | 10/10 | 1/10 |
| pert-t0 | mas | 10 | 3/10 (30.0 %) † | 6/10 (60.0 %) | 8/10 | **0/50** |

† artefact — see §3.2.

**Fixed seed and temperature 0 do not produce reproducible generations.** Single-agent
runs are byte-reproducible in only 14 % of cases. Divergence is early, not a
tail effect: median first-differing character index 78, and 5+ cases diverge at
character 0.

Decision-flipping groups at T=0, seed 42 (5 identical requests):

- **single (5/50):** TXN-2025-010 `{dismiss 4, investigate 1}`, TXN-2025-015
  `{escalate 4, investigate 1}`, TXN-2025-021 `{investigate 4, dismiss 1}`,
  TXN-2025-028 `{dismiss 4, investigate 1}`, TXN-2025-037 `{escalate 4, investigate 1}`.
- **mas (14/50):** TXN-2025-003 `{dismiss 3, investigate 2}`, -010 `{investigate 4,
  dismiss 1}`, -012 `{investigate 4, dismiss 1}`, -020 `{dismiss 3, investigate 2}`,
  -024 `{investigate 4, dismiss 1}`, -026 `{investigate 4, dismiss 1}`, -032
  `{investigate 3, dismiss 2}`, -034 `{dismiss 3, investigate 2}`, -036 `{dismiss 4,
  investigate 1}`, -040 `{dismiss 3, investigate 2}`, -042 `{investigate 4, dismiss 1}`,
  -044 `{dismiss 4, investigate 1}`, -046 `{investigate 4, dismiss 1}`, -048
  `{investigate 4, dismiss 1}`.
- **pert-t0 single (1/10):** PERT-001 `{investigate 4, dismiss 1}`.
- **pert-t0 mas (4/10):** PERT-001 `{dismiss 4, investigate 1}`, PERT-002
  `{investigate 4, dismiss 1}`, PERT-005 `{investigate 4, escalate 1}`, PERT-006
  `{dismiss 4, investigate 1}`.

Note the 4-1 / 3-2 shape: the T=0 nondeterminism is a genuine sampling-boundary
wobble on borderline cases, not a uniform scatter.

### 3.2 The MAS byte-determinism figure is invalid — **critical**

`raw_output` does not mean the same thing in the two arms:

| Arm | median `raw_output` length | median chars per completion token |
|---|---:|---:|
| single | 792 chars | 2.93 |
| mas | **27 chars** | **0.03** |

For MAS, `raw_output` is verbatim the `reporting` node's output only — verified equal
to `node_outputs['reporting']` in 200/200 sampled rows, and 740/1,150 MAS rows have
`raw_output` shorter than 60 characters (typically the bare string
`FINAL DECISION: dismiss`). The other ~1,000 generated tokens per MAS run live in
`node_outputs.{orchestrator, data, policy_risk}` and are excluded.

Consequence: **the MAS byte-identity figure is very nearly a restatement of
decision-identity**, and the apparent result "MAS is *more* byte-deterministic than
single (24 % vs 14 %)" is an artefact of comparing a 27-character string against a
792-character one.

Recomputed on the **full trace** (`json.dumps(node_outputs, sort_keys=True)` for MAS,
`raw_output` for single), t0-fixed:

| Arm | full-trace byte-identical |
|---|---|
| single | 7/50 (14.0 %) |
| **mas** | **0/50 (0.0 %)** |

Corroborated by `completion_tokens`, which is arm-neutral: identical across the 5
repeats in 7/50 single groups and **0/50** MAS groups. The direction of the
byte-determinism finding **reverses** once the comparison is made like-for-like.

This is a **granite-specific** phenomenon, not a harness bug. Sampling 400 MAS rows
from each other sealed sweep, the fraction of MAS `raw_output` values under 60
characters is: granite4.1:8b **68.2 %**, deepseek-r1:14b@think 8.2 %,
qwen2.5:7b-ollama0326 3.0 %, qwen2.5:7b 1.5 %, qwen3.5:9b@think-budget 1.2 %,
gemma4 / qwen2.5:14b / qwen2.5:14b-ollama0326 / qwen3.5:9b-ollama0326 / lfm2.5:8b@think
0.0 % (medians 371–1,603 chars). The harness has always journalled the final node's
text as `raw_output`; other models' `reporting` nodes write a narrative, whereas
**granite4.1:8b's reporting node emits the bare verdict line in 740/1,150 runs
(64.3 %)** — 613 × `FINAL DECISION: investigate`, 104 × `dismiss`, 23 × `escalate`.
Only 395 distinct reporting strings exist across the whole MAS arm.

Consequence for the committed ROUGE-L appendix: see §5, disagreement **D2**.

---

## 4. Degeneracy — verdict: **FLAWED (the system, not the measurement)**

### 4.1 Decision distribution vs label distribution

| Population | escalate | dismiss | investigate |
|---|---:|---:|---:|
| **Primary labels (50 cases)** | 15 (30.0 %) | 26 (52.0 %) | 9 (18.0 %) |
| single, primary runs (n=1,000) | 43 (4.3 %) | 101 (10.1 %) | **856 (85.6 %)** |
| mas, primary runs (n=1,000) | 23 (2.3 %) | 108 (10.8 %) | **869 (86.9 %)** |
| **Perturbation labels (10 cases)** | 4 (40.0 %) | 6 (60.0 %) | 0 (0.0 %) |
| single, perturbation runs (n=150) | 9 (6.0 %) | 23 (15.3 %) | **118 (78.7 %)** |
| mas, perturbation runs (n=150) | 4 (2.7 %) | 23 (15.3 %) | **123 (82.0 %)** |

The perturbation block is the sharpest statement: **zero of its 10 cases is labelled
`investigate`, and the system answers `investigate` on ~80 % of those runs.**

### 4.2 Majority vote collapses to one class

| Arm | Condition | MV over 50 primary cases |
|---|---|---|
| single | t0-fixed | investigate 42, dismiss 5, escalate 3 |
| single | t07-varied | investigate 47, dismiss 2, escalate 1 |
| mas | t0-fixed | investigate 42, dismiss 7, escalate 1 |
| mas | t07-varied | **investigate 48**, escalate 1, dismiss 1 |

Per-class recall, t07-varied, majority vote:

| Arm | escalate (n=15) | dismiss (n=26) | investigate (n=9) |
|---|---:|---:|---:|
| single | 0.067 | 0.077 | **1.000** |
| mas | 0.067 | 0.038 | **1.000** |

Perfect recall on the rarest class and near-zero on the other two is the signature of
a constant predictor, not of a classifier.

### 4.3 Below the trivial baseline

| Predictor | Accuracy on primary block |
|---|---:|
| constant `dismiss` | **0.520** |
| constant `escalate` | 0.300 |
| constant `investigate` | 0.180 |
| single, t0-fixed, MV | 0.300 |
| single, t07-varied, MV | 0.240 |
| mas, t0-fixed, MV | 0.340 |
| mas, t07-varied, MV | 0.220 |

**Every arm × condition cell is beaten by the constant-`dismiss` baseline**, and three
of four are beaten by constant-`escalate`. The best cell (mas t0-fixed, 0.340) is
0.18 below the trivial baseline.

### 4.4 The degeneracy control fires

`perturbation_cases.json` exists precisely to test whether the pipeline responds to
decision-relevant input edits. It does not.

| Arm | MV changed vs base case | MV matched the perturbed label |
|---|---:|---:|
| single | 3/10 | 2/10 (PERT-002, PERT-010) |
| **mas** | **0/10** | **0/10** |

**The MAS arm produced an identical majority decision on all ten perturbations**,
including PERT-001, where the destination country is edited *Cayman Islands → North
Korea* and the flag *offshore_destination → sanctioned_destination* — an edit the
system prompt explicitly names as escalation-grounds ("a confirmed sanctions hit on
any party is grounds to escalate"). MAS answered `dismiss` before and `dismiss` after.

### 4.5 Verdict

**The high DAR (0.83–0.96) and moderate-to-high Krippendorff's α (0.23–0.89 depending
on cell) are mode collapse, not reliability.** A system that emits one label ~86 % of
the time will score well on any within-case agreement metric by construction.
The reliability numbers in §0 are **arithmetically correct and substantively
uninformative about triage competence**. They remain valid as a measurement of
*run-to-run stability of a degenerate policy*, which is a legitimate — but much
narrower — claim than "the pipeline is reliable".

Two consequences the write-up must absorb:

1. **Reliability metrics must be reported jointly with the decision-distribution
   table and the constant-class baseline**, never alone. A DAR of 0.96 next to an
   accuracy of 0.30 next to a 0.52 baseline tells a coherent story; a DAR of 0.96
   alone is misleading.
2. **α is doing real work here and should be foregrounded over DAR.** α drops from
   0.848 (single t0-fixed) to 0.226 (single pert-t10) while DAR only drops from 0.960
   to 0.710 — α is chance-corrected and therefore penalises collapse; DAR does not.
   The single largest α gap in the sweep, single 0.848 vs mas 0.511 at t0-fixed, is
   also the clearest arm signal in the dataset.

---

## 5. Reconciliation with `analysis-report.md` — verdict: **SOUND (arithmetic) / FLAWED (framing)**

### 5.1 Numerical agreement

Every quantity the committed report publishes was recomputed from scratch. **All of
them reproduce.**

| Report section | Cells checked | Agreement |
|---|---:|---|
| Tier 1 — pass^1, pass^5, pass^15, DAR, Krippendorff α, flip_rate | 4 cells × 6 metrics | **exact to 3 dp** |
| Tier 2 — majority_vote_accuracy, TAR, jaccard, nLCS, malformed_rate | 4 cells × 5 metrics | **exact to 3 dp** |
| Tier 3 — tokens_per_run, tokens_per_pass^{1,5,15}, mean_wall_clock_s | 4 cells × 5 metrics | **exact to 3 dp** |
| Perturbation block — pass^k, DAR, α, flip_rate | 6 cells × 5 metrics | **exact to 3 dp** |
| ROUGE-L appendix | 10 cells | **exact to 3 dp** |
| Arm difference — mean diff, bootstrap CI, permutation p | 3 metrics | **agrees after sign convention** |
| `malformed_rate = 0.000` everywhere | 10 cells | **confirmed independently** (0 errors, 0 null decisions, 0 unparseable rows, 0 extraction mismatches) |

Notes on the two conventions that initially looked like disagreements and are not:

- **Sign convention.** The report tabulates *single − mas*; this audit tabulates
  *mas − single*. Report pass_fraction +0.009 / DAR −0.015 / entropy +0.020 versus
  audit −0.0093 / +0.0152 / −0.0203. CIs mirror correspondingly
  (report DAR [−0.060, 0.030] ↔ audit [−0.0297, +0.0604]). Permutation p values
  agree within Monte-Carlo noise (0.684 ↔ 0.674; 0.531 ↔ 0.532; 0.401 ↔ 0.405).
- **TAR** in the report is exact-order trajectory agreement; identical to this
  audit's `traj-exact` in all 4 cells.
- **Majority-vote tie-break** (`escalate > dismiss > investigate > malformed`)
  never fired: **0 ties in all 10 cells**. Tie-lenient and tie-strict accuracy are
  identical throughout, so the rule is not load-bearing for any published number.

**Verdict on arithmetic: the committed report is correct.** No discrepancy beyond
rounding exists in anything it reports.

### 5.2 Substantive disagreements

The disagreements are about **what is measured, what is normalised, and what is left
out** — not about arithmetic.

| # | Disagreement | Report | Audit | Severity |
|---|---|---|---|---|
| **D1** | Entropy normalisation base | mean_entropy 0.036 / 0.186 / 0.114 / 0.165 | 0.046 / 0.234 / 0.143 / 0.209 | Low |
| **D2** | ROUGE-L object for MAS | over `raw_output`, documented as "the FULL raw output text" | for granite MAS that is a 27-char median string, not the full output | High |
| **D3** | Degeneracy / baseline | absent | 85.6 % / 86.9 % `investigate`; MV-acc below the 0.520 constant-`dismiss` baseline in all 4 cells | **Critical** |
| **D4** | Perturbation "instrument check" readout | reports only pass^k/DAR/α/entropy on the block | never computes whether the decision *moved*: MAS **0/10**, single 3/10 | **Critical** |
| **D5** | Arm-difference test coverage | t07-varied only (nothing significant) | t0-fixed has three effects at p < 0.05, all favouring single — untested | Medium |
| **D6** | T=0 fixed-seed determinism | no section | 14 % byte-identical (single), 0 % full-trace (mas); 19 decision-flipping groups | High |
| **D7** | Second manifest | not mentioned in the results dir or the report | documented in CHANGELOG only | Low |
| **D8** | Execution provenance | `git_sha` = plan-generation SHA (Aug 11); sweep ran Aug 13 | no execution SHA recorded anywhere | Medium |
| **D9** | Wall-clock confound | `mean_wall_clock_s` published as a cost metric | arms ran concurrently on one GPU; ratio is a lower bound | Medium |

**D1 — resolved, and it is a definitional choice, not an error.** The report's
entropy is this audit's entropy × 0.79248 in **all ten cells** (0.046 → 0.0365,
0.234 → 0.1854, 0.143 → 0.1133, 0.209 → 0.1656, 0.152 → 0.1205, 0.316 → 0.2504,
0.182 → 0.1442, 0.229 → 0.1815). 0.79248 = ln 3 / ln 4 exactly. The report normalises
by **ln 4**, because its outcome domain includes a fourth category, `malformed`, as
documented in its own preamble. That is internally consistent. But `malformed_rate`
is **0.000 in every one of the ten cells** and across all 2,300 runs, so the fourth
category is unreachable in this sweep: the reported entropy is deflated by 20.75 %
and is capped at 0.7925 rather than 1.0. Recommend reporting the base explicitly, or
normalising by the number of *observed* categories.

**D2 — quantified.** Recomputing the ROUGE-L appendix over the full MAS node trace
(`orchestrator ∥ data ∥ policy_risk ∥ reporting`) instead of `raw_output`:

| Arm | Condition | committed (raw_output) | corrected (full trace) | Δ |
|---|---|---:|---:|---:|
| single | all 5 conditions | 0.835 / 0.269 / 0.812 / 0.275 / 0.241 | identical | 0.000 |
| mas | t0-fixed | 0.625 | 0.719 | +0.094 |
| mas | t07-varied | 0.433 | 0.338 | −0.094 |
| mas | pert-t0 | 0.703 | 0.710 | +0.007 |
| mas | pert-t05 | 0.476 | 0.365 | −0.111 |
| mas | pert-t10 | **0.541** | **0.329** | **−0.213** |

Single-arm figures are unaffected (raw_output *is* the full output there). MAS
figures move by up to 0.213 — a 39 % relative change on `pert-t10`. **Being precise
about what does and does not reverse:** the report's implicit t07-varied ordering
(mas 0.433 > single 0.269, i.e. "MAS is more lexically consistent at T=0.7") **survives**
correction (0.338 > 0.269), though the margin shrinks by 58 %. What *does* reverse is
the **byte-identity** comparison in §3.2 (mas 24 % → 0.0 % vs single 14 %). The
appendix numbers as published are therefore not wrong-as-computed but are computed
over an object that differs by ~30× in length between arms, and the report's own
description of them ("the FULL raw output text") does not hold for the MAS arm of this
model.

**D3 and D4 are the audit's central findings.** They are omissions, so no number in
the report contradicts them — which is precisely the problem. A reader of
`analysis-report.md` alone sees DAR 0.83–0.96 and α up to 0.886 and will conclude the
pipeline is highly reliable. The evidence in §4 shows those figures are produced by a
near-constant predictor that is beaten by "always answer dismiss", and that the
project's own purpose-built degeneracy control fired and was never read.

### 5.3 Agreement with `backend/experiments/CHANGELOG.md`

Checked and **confirmed**:

- The two-manifest situation *is* documented: the 2026-08-11 evening entry states
  that the 0.32.6 manifests were "archived as `manifest-ollama0326.json` before
  regeneration", alongside the paired gate evidence
  (`mini-gates.json` / `mini-gates-ollama0329.json`). This audit's independent
  reconstruction in §1.6 matches the CHANGELOG account exactly. **My §1.6 finding is
  therefore a corroboration, not a discovery** — the gap is that the results directory
  and the analysis report carry no trace of it.
- Granite is recorded as gate 8/8, thinking-OFF, `think: null` — confirmed: `think`
  is null in all 2,300 rows.
- The 0.32.9 re-gate delta for granite is recorded as "no change … i.e. noise" —
  consistent with both gate files reporting the identical determinism SHA
  `92dbf515…f914c31`.
- The project has prior form on exactly the D8 defect class: the 2026-08-06 entry
  records re-stamping a manifest because "the recorded `git_sha` … predated the
  commits that contain the reviewed harness", verifying `config_hash` and the
  2,300-run plan were byte-identical. **The same class of gap has recurred here in a
  different form** (plan-generation SHA vs execution SHA, two days apart) and was not
  caught.

Searched and **absent** from the CHANGELOG (0 hits each): `degenerac*`,
`mode collapse`, `baseline`, `majority class`, `contention`, `multiplicity`,
`Bonferroni`. These are the genuinely new threats in §6.

One partial acknowledgement worth crediting: the 2026-08-12 entry already records the
general lesson that *"a 3-probe pilot cannot detect a 0.1 %-scale event;
scale-appropriate contamination scanning belongs in the seal step, not only the
gate."* That lesson is correct and directly applicable to the determinism gate — but
it was drawn for channel contamination only and has not been applied to determinism
(threat T4).

---

## 6. Threats this sweep exposes, ranked

Ranked by severity = (impact on the dissertation's claims) × (likelihood a reader is
misled). Threats already acknowledged in project docs are marked and excluded from the
ranking unless this sweep materially sharpens them.

### T1 — CRITICAL. The measured system is degenerate, so every reliability number means something narrower than it appears

**Evidence.** 85.6 % (single) / 86.9 % (mas) of primary runs answer `investigate`
against an 18 % label prior. Majority vote is `investigate` on 42–48 of 50 cases.
Per-class recall: 1.000 on `investigate`, 0.038–0.077 elsewhere. MV accuracy
0.220–0.340 versus a constant-`dismiss` baseline of **0.520** — every cell loses to a
one-line predictor. DAR is 0.83–0.96 *because* of this, not despite it.

**Why it matters.** The dissertation's repeatability construct is measured by DAR, α,
flip rate and entropy. All four are inflated by collapse. The honest claim is
"run-to-run stability of a degenerate policy", which is much weaker than
"the pipeline is reliable".

**Mitigation.** (a) Publish the decision-distribution table and the constant-class
baselines adjacent to every reliability table — never a DAR without its accuracy and
baseline. (b) Promote **Krippendorff's α over DAR** as the headline reliability
statistic: α is chance-corrected and does penalise collapse (single pert-t10 α = 0.226
while DAR is still 0.710), whereas DAR does not. (c) Add a pre-registered degeneracy
gate — e.g. reject a sweep for headline use if any single outcome exceeds 60 % of
runs, or if MV accuracy falls below the majority-class baseline. Granite fails both.

### T2 — CRITICAL. The degeneracy control was built, executed, and never read

**Evidence.** `perturbation_cases.json` states its own purpose: "to test that the
measured pipelines respond to decision-relevant input changes (degeneracy control)".
Result: MAS majority vote changed on **0/10** perturbations, single on 3/10. This
includes PERT-001, where the destination is edited *Cayman Islands → North Korea* and
the flag *offshore_destination → sanctioned_destination* — an edit the system prompt
names verbatim as escalation-grounds. MAS answered `dismiss` before and `dismiss`
after. `analysis-report.md` reports pass^k, DAR, α, flip rate and entropy on this
block but never the one number the block exists to produce.

**Why it matters.** This is the strongest single piece of evidence that the pipeline
is not doing compliance triage, and it is the project's own instrument. Publishing
reliability metrics from a sweep whose instrument check failed silently is the most
serious methodological exposure here.

**Mitigation.** Make base-vs-perturbed MV movement the primary perturbation readout,
with a pre-registered pass threshold (e.g. ≥ 7/10 must move, and ≥ 5/10 must move *to
the intended label*). Report it in the headline table, not the appendix. Re-read it
for every already-sealed sweep — it is cheap, requires no re-running, and may change
which sweeps are admissible.

### T3 — HIGH. Text-level metrics are not comparable across arms for this model

**Evidence.** MAS `raw_output` is `node_outputs['reporting']` verbatim (200/200
sampled rows); median 27 chars vs 792 for single; 740/1,150 MAS rows are the bare
verdict line; only 395 distinct reporting strings exist. Corrected byte-identity at
T=0 **reverses** (mas 24 % → 0.0 %, single 14 %). Corrected ROUGE-L moves MAS cells by
up to −0.213. Cross-sweep sampling shows this is **granite-specific** (68.2 % of MAS
rows under 60 chars, versus 0.0–8.2 % for every other sealed model), so it is a
model × harness interaction, not a corpus-wide bug — but it silently corrupts the
comparability of granite's MAS row in any cross-model ROUGE-L table.

**Related, same root:** the trajectory **Jaccard** metric is near-saturated for MAS
(0.994–1.000 in every cell) because the MAS tool partition statically fixes which node
may call which tool. Jaccard is structurally guaranteed to be high for MAS and is a
weak reliability signal; only 18 distinct tool sequences occur in 1,150 MAS runs
versus 56 in single. Jaccard should not be used to compare architectures with
different tool partitions.

**Mitigation.** Compute text-level metrics (ROUGE-L, byte identity) over the full MAS
trace via `node_outputs`, or restrict them to the single arm and say so. Flag
granite's MAS ROUGE-L as not comparable in the cross-model table. Drop Jaccard from
cross-architecture comparisons or report it only within-arm.

### T4 — HIGH. The determinism gate does not scale to the workload

**Evidence.** Both gate batteries report determinism PASS: 5/5 identical SHA-256,
`output_len` 586, on a **69-prompt-token / 106-completion-token / num_predict 512**
canary. At workload scale (≈4,100–7,900 prompt tokens, `num_predict` 2048, multi-turn
tool loop), T=0 with seed 42 yields only **14 % byte-identical** single runs and
**0 %** full-trace-identical MAS runs, with 19 decision-flipping case groups across
the two T=0 conditions. Divergence is early (median first-differing character index
78; several cases diverge at index 0), consistent with KV-cache/batching
nondeterminism that a short single-turn probe cannot reach.

**Why it matters.** `t0-fixed` is a designed condition whose interpretation assumes
T=0 is a controlled reference point. It is not, and the gate that was supposed to
establish this reported PASS.

**Mitigation.** Move the determinism probe into the seal step and run it at workload
scale — real case prompt, real `num_predict`, full tool loop, 5 repeats — and record
byte/decision identity as a first-class sweep result. This is the same lesson the
CHANGELOG already drew for channel contamination on 2026-08-12; apply it to
determinism. Report `t0-fixed` as "low-temperature", not "deterministic", throughout
the dissertation.

### T5 — MEDIUM. Arm-difference testing was run only where nothing is significant, and without multiplicity control

**Evidence.** The report tests three metrics on `t07-varied` only; all
p ≥ 0.401. On `t0-fixed` — untested — three effects reach p < 0.05, all favouring
**single**: DAR −0.092 (95 % CI [−0.168, −0.020], p = 0.019), flip rate +0.180
([+0.020, +0.340], p = 0.047), normalised entropy +0.098 ([+0.019, +0.177], p = 0.018).
Symmetrically, no multiplicity correction is discussed anywhere; across the 35
comparisons this audit ran, none of the three would survive Bonferroni
(α/35 ≈ 0.0014).

**Why it matters.** Two-sided exposure. The sweep's strongest arm signal is
unreported, *and* the framework for judging whether it is real is absent. As it
stands the finding is suggestive and corroborated by the independent §3 determinism
counts (MAS decision-identical 36/50 vs single 45/50), but it is not confirmed.

**Mitigation.** Test all pre-registered conditions symmetrically, not just the one
with most repeats. Pre-register the metric set and either apply a correction or label
the analysis exploratory. Note the three "significant" metrics are three views of one
quantity, not three independent results.

### T6 — MEDIUM. Wall-clock cost is confounded by GPU contention

**Evidence.** Both arms started at 19:09:29 Z on one GPU (separate Ollama servers,
ports 11437/11435). MAS runs that started while the single arm was still running
average **14.01 s**; MAS runs that started after it finished average **10.80 s** —
a **1.30×** inflation — while MAS completion tokens are flat across the same split
(1,002 vs 1,024), confirming contention rather than a workload difference. All 1,150
single-arm runs were contended; only 373/1,150 MAS runs were. The committed
**2.65× MAS/single wall ratio is therefore a lower bound**; deflating single's 4.46 s
by the same 1.30× gives a contention-corrected estimate of ≈**3.15×**.

*Partially acknowledged:* the CHANGELOG states arms run in parallel by design. What is
not acknowledged is that this biases the published `mean_wall_clock_s` comparison, and
biases it *asymmetrically* between arms.

**Mitigation.** Make **tokens** the primary cost metric (contention-free, and already
reported), label wall-clock as measured under contention, or serialise the arms.

### T7 — MEDIUM. No execution provenance

**Evidence.** `manifest.json.git_sha = 41de0892…` corresponds to a commit of
2026-08-11 19:58 +0100; the sweep executed 2026-08-13 19:09–22:58 Z. Two commits
touching `backend/experiments/` landed in between (`722a9ce`, `c64495c`). Neither
appears to alter the granite thinking-off path — `think` is null in all 2,300 rows and
`config_hash` matches — but nothing in the sealed artefact *proves* the harness that
ran is the harness the recorded SHA describes. The project fixed the same defect class
deliberately on 2026-08-06, which shows it is understood to matter.

**Mitigation.** Stamp the *execution* git SHA (and a dirty-worktree flag) into
`progress.json` or a journal header at runner start. Cheap, and it closes the gap for
every future sweep.

### T8 — LOW. Two manifests in one sealed directory with no in-directory marker

**Evidence.** §1.6. Documented in the central CHANGELOG; invisible from the results
directory itself and from `analysis-report.md`. A downstream script globbing
`manifest*.json` binds results to the wrong runtime stamp; the filename is the only
disambiguator and it is a convention, not a machine-checkable field.

**Mitigation.** Add a `PROVENANCE.md` (or a `superseded_by` field inside
`manifest-ollama0326.json`). Do not delete it — it is the evidence of the upgrade.

### T9 — LOW. Entropy is normalised against an unreachable category

**Evidence.** D1. Normalisation by ln 4 including `malformed`, whose rate is 0.000 in
all ten cells, deflates every published entropy by 20.75 % and caps the metric at
0.7925.

**Mitigation.** State the base in the report, or normalise by observed categories.
Do not silently change published numbers — document the convention.

### T10 — LOW. The benchmark label file's own metadata is internally inconsistent

**Evidence.** `alerts.json.metadata.ground_truth_distribution` claims
`{escalate 15, dismiss 25, investigate 10}`; the actual 50 alerts are
`{escalate 15, dismiss 26, investigate 9}`. 50 alerts, 50 unique IDs — the alert list
is fine; the metadata block is stale. This shifts the constant-`dismiss` baseline from
0.500 to 0.520 and the constant-`investigate` baseline from 0.200 to 0.180.

**Mitigation.** Cite computed counts rather than the metadata block, and report the
inconsistency upstream to the benchmark authors. Immaterial to T1's conclusion — the
system loses to the baseline under either figure.

---

## 7. What this audit did NOT verify

Stated explicitly so the scope of the SOUND verdicts is not over-read.

**Excluded by the hard constraints of this audit (no LLM calls, no GPU):**

1. **No run was reproduced.** Determinism claims rest entirely on comparing repeats
   already in the journals. Whether re-executing a run today reproduces its journalled
   output is untested.
2. **No tool behaviour was verified.** Whether `check_sanctions_list` etc. returned
   correct or consistent data for a given case is unknown; only the *names* of calls
   were analysed. A tool returning wrong evidence would present exactly as model
   degeneracy in this analysis, and I cannot separate the two.
3. **The MAS tool partition was not verified as enforced at runtime** — only that the
   observed sequences are consistent with it.

**Not attempted:**

4. **The seed schedule was not re-derived from `MASTER_SEED`.** Verified: every run's
   seed matches the pre-generated plan (0 mismatches). *Not* verified: that the plan's
   750 varied seeds are correctly derived from `master_seed = 20260805`. This audit
   deliberately avoided reading the project's generator to preserve blindness, so a
   systematically wrong-but-consistently-applied seed schedule would not have been
   caught.
5. **Token counts were taken as reported by Ollama**, not recomputed with an
   independent tokenizer. `prompt_tokens`/`completion_tokens` are self-reported by the
   inference server.
6. **`wall_clock_s` measurement methodology was not inspected** (what the timer brackets).
7. **The model digest was not checked against an Ollama registry** — only verified
   uniform across runs and equal to the manifest.
8. **Harness source was not read** (extraction rule, strict tool parsing, MAS graph).
   The extraction rule was instead validated behaviourally: an independent parser
   agrees with the recorded decision on 2,294/2,300 rows, and the 6 exceptions were
   inspected by hand and are correct.
9. **The figures were not regenerated** (`figs/entropy-hist.png`,
   `figs/perturbation-trend.png`); their content is unverified.
10. **No other sweep's published numbers were audited.** The cross-sweep scan in §3.2
    sampled the first 400 MAS rows per directory and measured only `raw_output` length.
    `results-muse-glimmer-30b*` was excluded entirely (in-flight).
11. **Label quality was not assessed.** Whether the 50 ground-truth labels are
    themselves defensible is out of scope; only their internal consistency was checked
    (§T10). If the labels are wrong, the accuracy figures in §4 are wrong — but the
    *degeneracy* finding (85.6 % one class) is label-independent and survives.
12. **No confidence interval was placed on Krippendorff's α itself**, only on DAR,
    entropy, flip rate and accuracy.
13. **`cache_policy` was recorded as `none` but cache state was not independently
    probed.** Whether a warm KV cache leaked across runs is untested and is a
    plausible contributor to the T=0 nondeterminism in §3.

---

## 8. Verdict summary

| Dimension | Verdict |
|---|---|
| Data integrity (counts, keys, plan conformance, environment, errors, timeline) | **SOUND** |
| Two-manifest provenance | **SOUND-WITH-CAVEATS** — superseded artefact correctly archived and documented in the CHANGELOG; no results contaminated; but no in-directory marker and no execution SHA |
| Metric computation (all published numbers) | **SOUND** — every figure reproduces to 3 dp |
| Metric *choice and normalisation* | **SOUND-WITH-CAVEATS** — ln 4 entropy base; Jaccard structurally saturated for MAS |
| T=0 fixed-seed determinism | **FLAWED** — not deterministic at workload scale; gate did not detect it; MAS byte-level figure invalid as published |
| Degeneracy | **FLAWED** — near-constant predictor, below the trivial baseline, and the project's own control fired unread |
| Reconciliation with `analysis-report.md` | **SOUND (arithmetic) / FLAWED (framing)** — no numerical discrepancy beyond rounding; the omissions invert the interpretation |

**Bottom line.** This is a well-run sweep of a model that cannot do the task. The
engineering is sound and the published arithmetic is exactly right; the scientific
framing is not, because it reports reliability without reporting that the thing being
reliably produced is a near-constant answer that loses to a one-line baseline. The
sweep remains usable — as a negative result, as a degeneracy case study, and as
evidence that T=0 is not a deterministic reference point at workload scale. It should
not be used to support any claim that decomposition improves (or preserves)
reliability.
