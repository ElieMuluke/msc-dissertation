# Independent audit — `deepseek-r1:14b@think` (results-deepseek-r1-14b-thinking)

Auditor: fresh-context agent, no access to the sweep's analysis code paths.
Recompute script: `backend/experiments/analysis/eval_deepseek_audit.py` (pure Python,
zero LLM calls, zero GPU, read-only over `manifest.json`, the two journals,
`alerts.json` and `perturbation_cases.json`). Metrics were re-implemented from their
pre-registered definitions rather than imported from `experiments.analysis.metrics`.

**Blindness protocol observed.** Every number in the headline table below was derived
and written down before `analysis-report.md` or `experiments/CHANGELOG.md` were opened.
The blind headline is preserved verbatim in the reconciliation section.

Corpus: 2,300 runs (single 1,150 / mas 1,150), model digest
`c333b7232bdb5212366…`, Ollama 0.32.9, `think=true`, `num_predict=2048`,
`cache_policy=none`, executed 2026-08-13 07:27:26Z → 19:03:09Z.

---

## Headline (independently recomputed)

| arm | condition | pass^1 | pass^5 | pass^15 | DAR | α | flip | maj-acc | H_norm | TAR / Jac / nLCS | tok/run | wall s | tok/pass^1 | tok/pass^5 | tok/pass^15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | t0-fixed | 0.616 | 0.520 | — | 0.928 | 0.875 | 0.180 | 0.620 | 0.065 | 1.000 / 1.000 / 1.000 † | 1049.5 | 12.56 | 1703.7 | 2018.3 | — |
| single | t07-varied | 0.628 | 0.377 | 0.300 | 0.684 | 0.425 | 0.700 | 0.640 | 0.332 | 1.000 / 1.000 / 1.000 † | 1009.4 | 11.81 | 1607.3 | 2675.4 | 3364.7 |
| mas | t0-fixed | 0.596 | 0.460 | — | 0.866 | 0.740 | 0.300 | 0.600 | 0.120 | 1.000 / 1.000 / 1.000 † | 4961.6 | 52.41 | 8324.8 | 10786.1 | — |
| mas | t07-varied | 0.571 | 0.267 | 0.100 | 0.633 | 0.304 | 0.900 | 0.600 | 0.402 | 1.000 / 1.000 / 1.000 † | 5041.6 | 29.73 | 8834.6 | 18913.7 | 50416.3 |
| single | pert-t0 | 0.880 | 0.800 | — | 0.960 | 0.909 | 0.100 | 0.900 | 0.036 | vacuous † | 1007.9 | 11.50 | 1145.3 | 1259.9 | — |
| single | pert-t05 | 0.780 | 0.700 | — | 0.900 | 0.814 | 0.200 | 0.800 | 0.085 | vacuous † | 989.6 | 11.15 | 1268.8 | 1413.8 | — |
| single | pert-t10 | 0.800 | 0.700 | — | 0.880 | 0.776 | 0.200 | 0.800 | 0.112 | vacuous † | 976.5 | 10.88 | 1220.6 | 1395.0 | — |
| mas | pert-t0 | 0.720 | 0.500 | — | 0.820 | 0.664 | 0.400 | 0.800 | 0.157 | vacuous † | 5358.8 | 32.40 | 7442.8 | 10717.7 | — |
| mas | pert-t05 | 0.700 | 0.400 | — | 0.760 | 0.566 | 0.500 | 0.800 | 0.205 | vacuous † | 5064.6 | 30.22 | 7235.1 | 12661.5 | — |
| mas | pert-t10 | 0.700 | 0.300 | — | 0.670 | 0.405 | 0.700 | 0.800 | 0.298 | vacuous † | 5056.0 | 29.97 | 7222.9 | 16853.4 | — |

† **The trajectory metrics are vacuous.** `tool_calls` is the empty list in
**2,300 / 2,300 runs**, both arms, every condition. TAR / Jaccard / nLCS = 1.000 is the
∅-vs-∅ convention firing, not measured trajectory reproducibility. See Threat 1.

Reference points the report does not carry:

| baseline | value |
|---|---|
| always-`dismiss` on the 50 primary cases | **0.520** |
| always-`dismiss` on the 10 perturbation cases | **0.600** |
| best observed pass^1 (single, t07-varied) | 0.628 (**+0.108** over baseline) |
| mas pass^1 (t07-varied) | 0.571 (**+0.051** over baseline) |

---

## Per-dimension verdicts

### 1. Data integrity — **SOUND**

| check | result |
|---|---|
| journal lines vs manifest plan | 1,150 / 1,150 vs planned 1,150 / 1,150 — exact |
| JSON parse errors | 0 / 2,300 |
| duplicate run keys `(arm, case_id, condition, repeat_idx)` | **0** |
| missing planned keys | **0** |
| unplanned keys in journal | **0** |
| `seed` / `temperature` / `block` / `run_id` vs manifest, per run | **0 mismatches across all 2,300 × 4 fields** |
| seed schedule re-derived independently from `MASTER_SEED=20260805` | **0 mismatches** vs journal, **0** vs manifest |
| `model_digest` | 1 value × 2,300, equals manifest |
| `ollama_version` | `0.32.9` × 2,300, equals manifest |
| `model` / `think` / `num_predict` / `cache_policy` | `deepseek-r1:14b` / `True` / `2048` / `none`, uniform × 2,300 |
| `error` non-null | **0** |
| empty `raw_output` | **0** |
| null values in any scored field | **0** |
| decision value domain | `{dismiss 1409, investigate 606, escalate 282, malformed 3}` — no out-of-domain values |
| `agent_messages` | single = 1 × 1,150; mas = 4 × 1,150 (no partial pipelines) |
| `node_outputs` | present on 1,150/1,150 mas, null on 1,150/1,150 single; all four node keys present; **0** empty node strings |
| GPU fingerprint | single value (`NVIDIA RTX PRO 5000 Blackwell`) × 2,300; `host_load_high` false × 2,300 |

Seeds behave exactly as designed: `t0-fixed` and `pert-t0` are seed 42 throughout;
`t07-varied` draws 750 distinct seeds; the two arms are **seed-paired on all 1,150
case×condition×repeat cells** (0 divergent pairs), which is what licenses the paired
statistics.

**Timestamp discontinuity — one, and it is worth naming.** Exactly one gap > 10 min in
the whole sweep: **1,592 s (26.5 min)** on the mas arm between
`mas:TXN-2025-039:t07-varied:2` (15:53:17Z) and `…:3` (16:19:49Z). No error was
journalled, run count and seeds are intact, digest and version unchanged. Implication:
repeats 3–4 of that case executed against a different server/cache state than repeats
0–2. TXN-2025-039 is the **worst-entropy mas case** in the report — the stall and the
outlier sit on the same case, which is at minimum a coincidence the report should name.
The single arm has zero gaps.

Malformed accounting: 3 / 2,300 (0.13 %). I read all three. **All three are genuine
violations of the pre-registered last-line contract, not extractor false negatives:**

- `single:TXN-2025-045:t07-varied:0` — `…not high enough for escalation. FINAL DECISION: dismiss` (prose and label on one line).
- `mas:TXN-2025-005:t07-varied:8` — `**DECISION**: Dismiss` (wrong keyword).
- `mas:TXN-2025-039:t07-varied:3` — `**Final Decision:**` then `escalate` on the next line (bare label, no contract line). This is also the run immediately following the 26.5-min stall.

The extraction rule is applied faithfully; format compliance is 99.87 %.

### 2. Thinking-track separation — **SOUND** (with a stated limit)

Counted in both directions over all 2,300 runs, over `raw_output` **and** every
`node_outputs` string, case-insensitively, matching `<think…>` / `<thinking…>` and
`</think>` / `</thinking>`:

| surface | opening tags | closing tags | runs w/ orphan open | runs w/ orphan close |
|---|---|---|---|---|
| `raw_output` | **0** | **0** | **0** | **0** |
| `node_outputs.*` (4 nodes × 1,150) | **0** | **0** | — | — |

Also **0** runs carrying harmony/channel markers (`<\|channel\|>`, `<\|message\|>`, …).
`raw_output` begins with `\n\n` in **2,300 / 2,300** runs — the signature of an answer
channel emitted after a separately-routed reasoning block, consistent with
`reasoning_content` routing.

**Limit:** the journal has no reasoning field (`has_thinking_field = false`; the 25 keys
present are the documented schema). I can therefore certify that no reasoning markup
leaked into any stored surface; I **cannot** certify from the journal that reasoning was
produced per run. Indirect evidence that it was: median `completion_tokens ÷ visible
answer words` = **10.8** (single) and **46.9** (mas), i.e. roughly 90–98 % of billed
completion tokens never appear in `raw_output`.

### 3. Metrics — **SOUND** (values), **FLAWED** (trajectory tier)

All Tier 1/2/3, perturbation and appendix values reproduce to the reported precision
(reconciliation table below), including a from-scratch ROUGE-L recompute of all ten cells.

The trajectory tier is not sound as reported. `tool_calls` is empty in every one of the
2,300 runs. For contrast, every other completed sweep in this repo:

| sweep | runs | runs with ≥1 tool call | total tool calls |
|---|---|---|---|
| **results-deepseek-r1-14b-thinking** | 2,300 | **0** | **0** |
| results-qwen2.5-7b | 2,300 | 2,300 | 16,851 |
| results-qwen2.5-14b | 2,300 | 2,299 | 11,564 |
| results-qwen3.5-9b-thinking-budget | 2,300 | 2,274 | 11,103 |
| results-granite4.1-8b | 2,300 | 2,300 | 10,267 |
| results-gemma4 | 2,300 | 2,293 | 9,382 |
| results-lfm2.5-8b-thinking | 2,300 | 2,160 | 9,316 |

The accumulation path is correct (`app/agents/mas.py` uses an `Annotated[…, _extend]`
reducer; `single.py` accumulates per loop iteration), and it demonstrably records calls
for six other models on the same harness. This is a **model-level capability failure**,
not an instrumentation bug — and it makes TAR/Jaccard/nLCS = 1.000 uninterpretable.

### 4. Arm-difference statistics — **SOUND**

10,000-resample paired bootstrap over cases and 10,000-draw paired sign-flip permutation,
computed as (mas − single); the report's convention is (single − mas).

| condition | metric | mas | single | diff (mas−single) | 95 % CI | perm p |
|---|---|---|---|---|---|---|
| t07-varied | pass^1 | 0.5707 | 0.6280 | **−0.0573** | [−0.107, −0.011] | **0.024** |
| t07-varied | DAR | 0.6326 | 0.6840 | **−0.0514** | [−0.098, −0.006] | **0.034** |
| t07-varied | entropy | 0.4016 | 0.3323 | **+0.0693** | [+0.022, +0.119] | **0.008** |
| t07-varied | flip rate | 0.900 | 0.700 | +0.200 | [+0.060, +0.340] | 0.013 |
| t07-varied | majority-vote acc | 0.600 | 0.640 | −0.040 | [−0.140, +0.060] | 0.689 |
| t0-fixed | pass^1 | 0.596 | 0.616 | −0.020 | [−0.148, +0.104] | 0.809 |
| t0-fixed | DAR | 0.866 | 0.928 | −0.062 | [−0.132, +0.006] | 0.111 |
| t0-fixed | entropy | 0.120 | 0.065 | +0.055 | [−0.007, +0.117] | 0.109 |
| pert-t10 | DAR | 0.670 | 0.880 | −0.210 | [−0.370, −0.030] | 0.105 |

Directionally consistent everywhere: **MAS is worse on label agreement and worse on
repeatability, at ~5x the token cost.** Only the t07-varied cell has the case count to
resolve it (n=50); the perturbation cells (n=10) are underpowered and should not be read
as null results.

### 5. T=0 fixed-seed behaviour — **FLAWED as reported** (the finding is real; its cause is misattributed)

At `temperature=0.0, seed=42, cache_policy=none`, byte-level identity across the 5 repeats
is **0/50 cases in both arms** — matching the "not byte-deterministic" reading. But the
structure of the divergence is completely systematic and the report does not contain it:

**Single arm — repeat 0 is the only source of divergence.** Pairwise byte-identity counts
across the 50 t0-fixed cases:

```
0-1: 0/50   0-2: 0/50   0-3: 0/50   0-4: 0/50
1-2: 50/50  1-3: 50/50  1-4: 50/50  2-3: 50/50  2-4: 50/50  3-4: 50/50
```

Identical structure on pert-t0 (0/10 vs 10/10). `completion_tokens` for repeat 0 differs
from repeats 1–4 in **50/50** cases while repeats 1–4 are equal in 50/50. All **9/9**
decision flips in single t0-fixed have repeat 0 as the singleton minority. Execution is
case-major (5 consecutive repeats of one prompt), so this is the classic
**prompt-prefix KV-cache warm-state effect**: repeat 0 prefills cold, repeats 1–4 reuse
the cached prefix and land on different arithmetic. The harness ships
`cache_policy="prewarm"` whose docstring describes exactly this scenario; this sweep ran
`none`.

Sensitivity analysis (drop repeat 0, recompute on repeats 1–4):

| cell | byte-identical cases | DAR | α | flip | pass^1 |
|---|---|---|---|---|---|
| single t0-fixed, all 5 | 0/50 | 0.928 | 0.875 | 0.180 | 0.616 |
| single t0-fixed, drop r0 | **50/50** | **1.000** | **1.000** | **0.000** | 0.620 |
| single pert-t0, all 5 | 0/10 | 0.960 | 0.909 | 0.100 | 0.880 |
| single pert-t0, drop r0 | **10/10** | **1.000** | **1.000** | **0.000** | 0.900 |
| mas t0-fixed, all 5 | 0/50 | 0.866 | 0.740 | 0.300 | 0.596 |
| mas t0-fixed, drop r0 | **0/50** | 0.930 | 0.864 | 0.140 | 0.595 |
| mas pert-t0, all 5 | 0/10 | 0.820 | 0.664 | 0.400 | 0.720 |
| mas pert-t0, drop r0 | **0/10** | 0.833 | 0.684 | 0.300 | 0.700 |

**The single arm is exactly deterministic at T=0 once the prefix cache is warm — 100 % of
its observed T=0 nondeterminism is the first repeat of each case.** The MAS arm is not:
it retains 0/50 byte identity and 14 % flips after removing the artefact, and its
distinct-output histogram is `{4 distinct: 38 cases, 3: 11, 5: 1}` (single is `{2: 50}`,
i.e. exactly {repeat 0} ∪ {repeats 1–4}). The report's 0.928 vs 0.866 therefore mixes a
harness cache artefact into both arms and **understates** the true determinism gap, which
is 1.000 vs 0.930.

Corroboration from the sweep's own gate evidence: `gates/mini-gates.json` shows the
first probe call at 27.67 s / `thinking_len` 2438 and every subsequent call at
~8.2 s / 2608 — the same first-call divergence, at model-load scale.

**Flipping groups at T=0 fixed seed.** Single (9/50), all with repeat 0 as the minority:

| case | label | decisions (r0…r4) |
|---|---|---|
| TXN-2025-004 | escalate | investigate, escalate ×4 |
| TXN-2025-006 | escalate | investigate, escalate ×4 |
| TXN-2025-007 | dismiss | dismiss, investigate ×4 |
| TXN-2025-016 | dismiss | dismiss, investigate ×4 |
| TXN-2025-029 | escalate | escalate, investigate ×4 |
| TXN-2025-035 | escalate | escalate, investigate ×4 |
| TXN-2025-039 | escalate | investigate, escalate ×4 |
| TXN-2025-044 | dismiss | investigate, dismiss ×4 |
| TXN-2025-049 | escalate | investigate, escalate ×4 |

MAS (15/50) — TXN-2025-001, -002, -003, -004, -008, -009, -013, -033, -035, -036, -039,
-043, -045, -047, -050; only 9 of the 15 have repeat 0 as the singleton minority, and
TXN-2025-039 spans three distinct decisions (`escalate, dismiss, investigate ×3`).
Perturbation T=0: single flips on PERT-001 only; mas flips on PERT-004, -005, -006, -008.

### 6. Degeneracy — **SOUND-WITH-CAVEATS** (not mode collapse; is majority-class-carried)

Decision distribution vs label distribution:

| cell | dismiss | investigate | escalate | modal share |
|---|---|---|---|---|
| **labels (primary)** | **0.520** | **0.180** | **0.300** | 0.520 |
| single t0-fixed | 0.564 | 0.304 | 0.132 | 0.564 |
| single t07-varied | 0.600 | 0.276 | 0.123 | 0.600 |
| mas t0-fixed | 0.640 | 0.256 | 0.104 | 0.640 |
| mas t07-varied | 0.620 | 0.281 | 0.096 | 0.620 |

Not mode collapse: all three decisions are emitted in every cell, modal share
0.56–0.70 against a 0.52 label prior, and only 15/50 (single) and 4/50 (mas) cases are
unanimous on the global mode at t07-varied. **But the agreement is carried almost entirely
by the majority class**, and the model badly under-escalates:

| cell | dismiss agreement | investigate agreement | escalate agreement |
|---|---|---|---|
| single t0-fixed | 0.815 | 0.444 | **0.373** |
| single t07-varied | 0.874 | 0.363 | **0.360** |
| mas t0-fixed | 0.877 | 0.289 | **0.293** |
| mas t07-varied | 0.813 | 0.378 | **0.267** |

Dominant error is `escalate → investigate`: 110/750 runs (single t07) and 92/750
(mas t07), plus `escalate → dismiss` 33 and 72. A pass^1 of 0.628 against a 0.520
always-dismiss baseline is a **+0.108** margin, and the MAS arm's 0.571 is **+0.051**.
Neither the baseline nor the per-label breakdown appears in the report; without them
the headline reads far stronger than it is.

Perturbation instrument, per case (hit rate = fraction of repeats matching the flipped
target). The battery passes in aggregate while failing systematically in one direction:

| case | flip direction | single t0 / t05 / t10 | mas t0 / t05 / t10 |
|---|---|---|---|
| PERT-001 | dismiss→escalate | 0.8 / 1.0 / 1.0 | 1.0 / 0.6 / 0.8 |
| PERT-006 | dismiss→escalate | **0.0 / 0.0 / 0.2** | **0.0 / 0.0 / 0.2** |
| PERT-009 | dismiss→escalate | 1.0 / **0.0 / 0.0** | **0.0 / 0.0 / 0.0** |
| PERT-005 | investigate→escalate | 1.0 / 0.8 / 0.8 | 0.6 / 0.8 / 0.6 |
| PERT-002/003/008 | escalate→dismiss | 1.0 everywhere | 1.0 / 1.0 / 0.8 avg |
| PERT-004/007/010 | investigate→dismiss | 1.0 everywhere | 0.8–1.0 |

Every risk-**decreasing** edit is tracked at 0.8–1.0. Two of the four risk-**increasing**
edits are missed near-totally in both arms at every temperature.

### 7. Cost — **SOUND (tokens) / FLAWED (wall clock)**

Token cost reproduces exactly. Wall clock does not survive scrutiny. The CHANGELOG
records that arms run in parallel (documented design), but the measurement consequence
is not carried into the report:

| slice | n | mean wall s | mean completion tokens |
|---|---|---|---|
| mas runs inside the single-arm window | 263 | **52.43** | 2,494 |
| mas runs after the single arm finished | 887 | **29.58** | 2,516 |
| single arm (entirely inside the overlap) | 1,150 | 11.89 | — |

**1.77x wall-clock inflation for statistically identical token output.** GPU VRAM
confirms two co-resident models: 23–24 GB for all 1,150 single runs and the early mas
conditions, dropping to 11–12 GB once the single arm finished. Consequently the report's
`mas t0-fixed 52.410 s` vs `mas t07-varied 29.728 s` is a **contention artefact, not a
condition effect** — the two cells are not comparable, and neither is the single-vs-mas
wall-clock ratio (single was contended 1,150/1,150; mas only 263/1,150).

One more cost observation the report does not draw: MAS spends **4.80x** the tokens
(5,041.6 vs 1,009.4 per run) to produce a final answer of the **same length** — mean 57
vs 59 visible words. tokens ÷ pass^15 is 50,416 vs 3,365, a **15x** efficiency gap.

---

## Reconciliation vs `analysis-report.md`

Opened only after the table above was fixed. **Every reported value reproduces exactly at
the reported precision. Zero numerical discrepancies, not even at rounding scale.**

| block | cells | max |diff| | verdict |
|---|---|---|---|
| Tier 1 (pass^1/5/15, DAR, α, flip) | 4 arms×conds × 6 | 0.0005 (rounding only) | **agree** |
| Tier 2 (maj-acc, entropy, TAR, Jaccard, nLCS, malformed) | 4 × 6 | 0.0005 | **agree** (values; see caveat) |
| Tier 3 (tokens/run, tokens/pass^k, wall s) | 4 × 5 | exact to 3 dp | **agree** |
| Perturbation block | 6 × 7 | 0.0005 | **agree** |
| ROUGE-L appendix | 10 cells, recomputed from scratch | 0.0005 | **agree** |
| Arm difference (sign convention inverted) | 3 metrics | see below | **agree** |
| Worst-entropy case lists | 2 | identical sets and order | **agree** |
| Journal counts / digest / version / config hash header | — | — | **agree** |

Arm-difference detail (report is single−mas, audit is mas−single; magnitudes compared):

| metric | report | audit (sign-flipped) | note |
|---|---|---|---|
| pass_fraction | 0.057, CI [0.011, 0.107], p 0.024 | 0.0573, CI [0.011, 0.107], p 0.024 | agree |
| DAR | 0.051, CI [0.007, 0.096], p 0.029 | 0.0514, CI [0.006, 0.098], p 0.034 | agree within resampling noise |
| entropy | −0.069, CI [−0.119, −0.021], p 0.007 | −0.0693, CI [−0.119, −0.022], p 0.008 | agree |

CI/p differences are third-decimal resampling variation from an independent RNG seed at
B=10,000; no seed for the report's resampler is recorded, so exact reproduction of the
CI endpoints is not expected and not required.

**Disagreements are entirely interpretive, not numerical.** Seven, ranked:

| # | disagreement | evidence |
|---|---|---|
| D1 | Report presents `TAR/jaccard/nLCS = 1.000` in Tier 2 as measured values with no annotation. They are ∅-vs-∅ conventions over 2,300 empty trajectories. | 0 tool calls in 2,300 runs; 9k–17k in every other sweep |
| D2 | Report gives no majority-class baseline, so pass^1 0.628 reads as a strong result. Margin over always-dismiss is +0.108 (single) and +0.051 (mas). | 26/50 primary labels are `dismiss` |
| D3 | Report reports T=0 DAR 0.928/0.866 without decomposing the repeat-0 prefix-cache artefact. Warm-state single-arm DAR is 1.000; mas is 0.930. | 50/50 cases: r0 differs, r1–r4 byte-identical |
| D4 | Report's wall-clock column mixes contended and uncontended runs across cells. mas t0-fixed 52.41 s vs mas t07 29.73 s is contention, not condition. | 1.77x, identical token output; VRAM 24 GB → 12 GB transition |
| D5 | Report gives no per-label breakdown; escalate agreement is 0.27–0.37 against dismiss 0.81–0.88. | confusion counts, §6 |
| D6 | Report's perturbation block passes in aggregate; it does not surface that PERT-006 and PERT-009 (both dismiss→escalate) fail near-totally in both arms at all three temperatures. | per-case hit rates, §6 |
| D7 | Report does not mention the 26.5-min mid-sweep stall, which lands on TXN-2025-039 — the very case it names as worst-entropy for mas. | one gap > 10 min in 2,300 runs |

Against `experiments/CHANGELOG.md`: the parallel-arm execution ("arms run in parallel,
each internally sequential", 2026-08-12 entry) is documented, as is deepseek-r1's
structural reasoning; the CHANGELOG's gate table records this sweep as think-probe
PASS 3/3, determinism PASS, pilot 8/8. **Neither the report nor the CHANGELOG anywhere
mentions that this model made zero tool calls**, and the gate that cleared it
(`gates/mini-gates.json`) records decisions, wall clock, tokens and inline-reasoning
counts but **has no tool-call assertion at all** — which is why a total tool-calling
failure passed 8/8.

---

## Ranked threats

**T1 — CRITICAL. The tool-calling channel is dead in 2,300/2,300 runs, and nothing caught it.**
`deepseek-r1:14b` never emitted a tool call; six other models on the identical harness
emit 9,316–17,236. Three consequences: (a) TAR/Jaccard/nLCS = 1.000 is an artefact and
must be reported as **N/A**, never as perfect trajectory reproducibility — if any
cross-model table or winner criterion consumes those columns, this model is receiving a
free perfect score on a dimension it did not participate in; (b) the MAS tool partition —
the arm's defining manipulation — never activated, so arm B is four chained LLM calls with
no evidence retrieval, and "single vs MAS" here is not the same contrast as in the other
sweeps; (c) any cross-model comparison of pass^k/DAR against tool-using sweeps compares
different tasks.
*Mitigation:* mark the trajectory tier N/A in this report and in every cross-model table;
add a tool-call assertion to the mini-gate (`pilot.arms[*].tool_calls > 0` for any model
whose registry entry claims tool support) and re-run the gate over the sealed corpus to
find out whether any other admitted model is silently degraded; state in the dissertation
that this sweep measures a tool-free variant of the task.

**T2 — CRITICAL. The MAS `data` node fabricates evidence in 1,150/1,150 runs.**
With zero tool calls, **100 %** of `node_outputs.data` still assert sanctions-screening
outcomes, customer transaction histories and precedent-search results; **394/1,150**
assert a numeric risk score without ever invoking `calculate_risk_score`. Example
(TXN-2025-001): *"ABC Corp and XYZ Holdings were not found on OFAC's SDN list… ABC Corp
has a transaction history averaging $30,000 USD with no prior alerts."* The
`policy_risk` and `reporting` nodes then condition on these fabrications. Every MAS-arm
decision in this sweep is grounded in invented facts — a substantive finding in a
compliance-triage setting, and one that fully explains why MAS is both less accurate
(−0.057 pass^1) and less repeatable (−0.051 DAR) than the single arm here.
*Mitigation:* report this as a first-class result, not a caveat; add a gate check that a
node claiming tool-derived evidence made ≥1 tool call; consider it the strongest available
argument in the dissertation that MAS decomposition without enforced grounding degrades
rather than improves triage.

**T3 — HIGH. T=0 "nondeterminism" is a first-repeat cache artefact in the single arm and only partly real in MAS.**
Dropping repeat 0: single → 50/50 byte-identical, DAR/α = 1.000, flip 0.000; mas → still
0/50 byte-identical, DAR 0.930, flip 0.140. As published, the headline conflates harness
cache state with model stochasticity and understates the arm gap.
*Mitigation:* report T=0 twice — as-run and warm-state — or re-run the T=0 blocks with the
harness's existing `cache_policy="prewarm"`; state plainly that under `cache_policy=none`
the first repeat of every case is a different measurement from the rest.

**T4 — HIGH. Label agreement is majority-class-carried, with a systematic under-escalation bias.**
pass^1 0.628 vs a 0.520 always-dismiss baseline; escalate agreement 0.27–0.37; dominant
error `escalate → investigate` (110/750 single, 92/750 mas). The perturbation block shows
the same asymmetry: risk-decreasing edits tracked at 0.8–1.0, two of four risk-increasing
edits missed near-totally (PERT-006, PERT-009).
*Mitigation:* publish the baseline row alongside pass^k, add the per-label agreement table,
and report the perturbation block per-case rather than as a single mean — the aggregate
hides a directional blind spot that matters far more than the mean.

**T5 — HIGH. Wall-clock cost is unusable as published.**
The entire single arm ran under two-model GPU co-residency; only 263/1,150 mas runs did.
MAS runs inside the overlap are 1.77x slower with identical token output. The
`mas t0-fixed 52.4 s` vs `mas t07 29.7 s` difference in Tier 3 is contention.
*Mitigation:* annotate every wall-clock figure with its contention state, or drop
wall-clock from cost claims for this sweep and use tokens (unaffected — 2,494 vs 2,516
across the boundary). If wall clock is load-bearing anywhere in the dissertation, it must
be re-measured serially.

**T6 — MEDIUM. `think=true` is not a manipulated variable for this model.**
The sweep's own gate evidence shows non-empty reasoning under `think_param: false` **and**
`null` (2,438–2,608 chars). The `think=true` stamp on all 2,300 runs is nominal. No
within-model thinking-on/off contrast is obtainable from deepseek-r1, and its membership
in the "thinking-on track" is a classification, not a treatment.
*Mitigation:* state this explicitly wherever the track is described; keep the
`muse-glimmer:30b` pair as the only genuine within-model contrast, as already planned.

**T7 — MEDIUM. MAS spends 4.80x the tokens for the same-length answer and worse results.**
5,041.6 vs 1,009.4 tokens/run; 57 vs 59 visible words out; pass^1 −0.057 (p=0.024);
tokens/pass^15 50,416 vs 3,365 (15x). The report contains the numbers but states no
conclusion.
*Mitigation:* state the conclusion.

**T8 — MEDIUM. Per-node token accounting is not journalled, so MAS truncation cannot be ruled out.**
1,039/1,150 mas runs exceed 2,048 total completion tokens (max 4,217), but that total is
summed over four calls and the per-call split is not recorded. The qwen3.5 starvation mode
(empty `reporting` node) demonstrably did **not** occur here — 0 empty node strings, 0 empty
`raw_output` — but "no individual node hit the 2,048 cap" is not verifiable from the journal.
*Mitigation:* add per-node `completion_tokens` to the journal schema for future sweeps.

**T9 — LOW-MEDIUM. The 26.5-min stall sits on the worst-entropy MAS case.**
`mas:TXN-2025-039:t07-varied` repeats 0–2 and 3–4 executed against different server states;
repeat 3 is also one of the three malformed runs in the whole sweep.
*Mitigation:* name it in the report; check whether TXN-2025-039's entropy ranking survives
exclusion of repeats 3–14.

**T10 — LOW. The benchmark's own label metadata is wrong.**
`alerts.json` `metadata.ground_truth_distribution` claims escalate 15 / dismiss 25 /
investigate 10; the 50 records are escalate 15 / **dismiss 26 / investigate 9**. The harness
and this audit both key off per-record `ground_truth`, so no metric changes — but any
analysis or write-up quoting the metadata block is wrong by one case in two classes.
*Mitigation:* correct upstream in dfah-repo or quote the derived counts.

**T11 — LOW. Completion-token accounting mixes reasoning and answer.**
~90–98 % of billed completion tokens never surface in `raw_output` (ratio 10.8 single /
46.9 mas). tokens-per-pass^k for a thinking-on sweep is therefore not on the same footing
as a thinking-off sweep.
*Mitigation:* label the units wherever thinking-on and thinking-off cost figures appear
in the same table.

---

## Explicitly NOT verified

1. **That `raw_output` is what the server actually returned.** No model was called; the
   journal is taken as an honest record of the transport layer.
2. **That reasoning text was produced on each of the 2,300 runs.** The reasoning channel is
   not journalled. Verified: no reasoning markup in any stored surface, plus a strong
   token-count inference. Not verified: per-run existence or content of the reasoning.
3. **Per-node token counts and per-call truncation in the MAS pipeline** — not journalled
   (T8).
4. **That the rendered prompt for each case matched the case record.** Prompts were not
   re-rendered or diffed; `prompt_tokens` variance (423–442, single) is consistent with
   per-case rendering but is not proof.
5. **`config_hash` and `git_sha` reproduction.** Not recomputed; the seed schedule *was*
   independently regenerated from `MASTER_SEED` (0 mismatches).
6. **The figures** (`figs/entropy-hist.png`, `figs/perturbation-trend.png`) — not opened or
   checked against the data.
7. **Cross-sweep metric comparisons.** Only tool-call counts were read from other results
   directories; `results-muse-glimmer-30b*` was not touched at all (in flight).
8. **Whether the 26.5-min stall corresponds to a server restart.** `runner-mas.log` was not
   parsed; the inference is from timestamps, and digest/version are unchanged either side.
9. **Semantic quality of the MAS fabricated evidence** — I established that evidence claims
   are made with zero tool calls and that 394/1,150 runs state a numeric risk score. I did
   not grade the fabrications case by case against the true case data.
10. **The bootstrap/permutation resampler used by the committed report.** Its RNG seed is
    not recorded, so CI endpoints are compared for consistency, not identity.

---

*Audit performed 2026-08-14. No existing file was modified. Files written:
this report and `backend/experiments/analysis/eval_deepseek_audit.py`.*
