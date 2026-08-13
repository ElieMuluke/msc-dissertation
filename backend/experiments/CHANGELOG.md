# Experiment changelog (pre-registration discipline)

## 2026-08-13 — qwen3.5:9b@think-budget SEALED + audited; confound statement CORRECTED to four factors

Sweep complete (2300/2300, think=true, num_predict=8192, Ollama 0.32.9). Independent
audit (`analysis/independent_check_qwen35_thinking_budget.py`): integrity CLEAN
(seed schedule independently regenerated; 0/2300 decision re-extraction mismatches);
**all 109 published metrics and all 9 statistical quantities reproduce to <=0.0005**.
Channel integrity CLEAN at scale: 0/2300 across 17 markup patterns including orphan
closers (contrast lfm2.5's 3/2300).

**CORRECTION — the confound is FOUR factors, not two.** The 2026-08-12 entry named
`think` and `num_predict`. The artifacts show the sealed thinking-off qwen3.5:9b sweep
also differs in **ollama_version** (0.31.1 vs 0.32.9) and **harness revision** (v1 vs
v2). No thinking-off qwen3.5:9b sweep exists at 0.32.9/v2. The auditor sized the infra
factor alone using two thinking-off sweeps (0.31.1 -> 0.32.6): single t0-fixed pass^1
moves 0.400 -> 0.300, mas 0.260 -> 0.300, single t07 alpha 0.205 -> 0.241 — i.e. an
Ollama-version change alone moves Tier 1 by up to 0.10, comparable to the differences
the cross-condition comparison would be asked to carry. **No attribution to
deliberation is supportable from this pair.** Not "thinking raised single-arm pass^1
from 0.364 to 0.548", not the flip-rate change, not the 4 -> 36 malformed rise. The
within-condition single-vs-MAS contrast remains internally valid (identical model,
digest, seeds, cases, prompts, budget, infra) and is this condition's primary analysis.
The clean within-model thinking contrast remains muse-glimmer's pair, which will be run
adjacently on one infra context and one harness revision.

**The budget raise did NOT fully cure its target.** 34/2300 empty outputs remain
(11 infrastructure errors; 8 with the literal gate signature — three upstream nodes
produce output, the `reporting` node emits 0 chars — of which 5 are DETERMINISTIC
across all seed-42 repeats of PERT-001; 15 single-arm silent empties), plus 2 MAS
truncations mid-sentence after ~13k tokens. Raising 2048 -> 8192 cleared the primary
t0-fixed block (0/500, which unblocked the gate) but the mechanism persists. Report the
residual alongside the gate pass.

**Report prose defect fixed:** `analysis/report.py` caption said majority-vote ties
break by first-observed decision; the code uses canonical outcome order. Caption
corrected and affected reports regenerated (no number changes — the conventions agree
in every cell of both thinking sweeps).

**Interpretation caveat recorded:** `mas/pert-t0` shows DAR 1.000 / flip 0.000 while
PERT-001 was malformed on all 5 repeats. Malformed==malformed agreement is the
pre-registered rule, but the instrument check on that case measures reproducible
failure, not reproducible judgement — state it when citing the perturbation block.

**Within-condition result (internally valid):** single pass^1 0.548 vs MAS 0.264
(paired +0.284, CI [0.172, 0.396], p<0.001); DAR 0.631 vs 0.724 but alpha 0.413 vs
0.277 — MAS agrees with itself more while discriminating less (571 of 750 MAS t07 runs
answered "investigate", 20 answered "dismiss"). Cost: MAS 17,318 tokens and 76 s/run vs
single 9,550 and 28 s.


## 2026-08-12 (afternoon) — full remaining sweep queue APPROVED (owner), pre-registered

Owner approved running every gated-and-ready sweep to completion. Queue, in
execution order, all on infra context 3 (Ollama 0.32.9), harness v2 semantics
on `main` (strict tool parsing, cache_policy="none"):

1. `qwen3.5:9b@think-budget` — RUNNING (thinking-on, num_predict=8192; the
   budget raise and its confound are pre-registered in the 2026-08-12 late entry)
2. `deepseek-r1:14b@think` — thinking-on, gate 8/8, ~10 h. Admissible only in
   this track (structural reasoning; the day-one exclusion from the sealed
   corpus).
3. `granite4.1:8b` — thinking-OFF, gate 8/8, ~4 h. Fifth thinking-off model and
   a redemption test of granite4:latest's documented non-terminating-loop
   failure (same vendor/family, newer release): establishes whether that
   exclusion was a version property rather than a vendor one.
4. `muse-glimmer:30b` — thinking-OFF, gate 8/8, ~24 h.
5. `muse-glimmer:30b@think` — thinking-ON, gate 8/8, ~34 h.

Sweeps 4 and 5 together are the project's ONLY unconfounded within-model
thinking-on/off contrast: same model, same weights digest, same seed schedule,
same harness, same infra context — one changed wire parameter. Every other
thinking-on/off statement in this project is cross-model and must be labelled
as such. They are therefore the scientifically load-bearing pair, and are run
adjacently and analysed as a matched pair.

Note on num_predict for the muse-glimmer thinking-on sweep: it runs at the
LOCKED 2048, not the raised budget, because its gate passed 8/8 at 2048 — so
the pair differs in the `think` parameter alone. (qwen3.5 required the raise
only because its 4-node pipeline starved at 2048; that asymmetry is itself a
reportable finding and does not propagate here.)

Each sweep on completion: verify run-for-run and seed-for-seed against its
manifest, seal and commit, generate its analysis report, and undergo an
independent audit by a fresh-context agent writing its own recomputation code.


## 2026-08-12 (morning) — lfm2.5:8b@think SEALED + audited; pre-registered criterion did NOT fully hold

Sweep `lfm2.5:8b@think` complete (2300/2300, Ollama 0.32.9, think=true on every
run, seeds match manifest, single digest). Independent audit
(`analysis/independent_check_lfm25_thinking.py`): integrity CLEAN on every check
including an independently regenerated seed schedule; **every reported number
reproduces to |diff| <= 0.0005** across Tier 1/2/3, the perturbation block, the
ROUGE-L appendix and the arm-difference statistics. Two defects recorded:

**1. Thinking-channel criterion VIOLATED at 3/2300 (0.13%).** The pre-registered
inverted criterion (2026-08-11 evening) requires the scored answer channel to be
free of inline reasoning markup. The gate passed on a 3-probe pilot; at full
scale, three single-arm t07-varied runs emit a complete reasoning paragraph on
the ANSWER channel terminated by an orphan `</think>` (two of them containing a
competing verdict), and one MAS `data` node leaked similarly into downstream
context. Runs: single:TXN-2025-027:t07-varied:2, single:TXN-2025-042:t07-varied:11,
single:TXN-2025-047:t07-varied:10, mas:TXN-2025-030:t07-varied:12.
No metric changes (the extraction rule reads the last non-empty line; 0/2300
extraction mismatches), but the sweep must be reported as **0.13% channel
contamination, not "content clean"**. Note for future gates: a 3-probe pilot
cannot detect a 0.1%-scale event; scale-appropriate contamination scanning
belongs in the seal step, not only the gate.

**2. Majority-vote tie-break: documentation corrected to match code.**
`analysis/metrics.py::majority_vote` breaks ties by canonical OUTCOMES order
(escalate > dismiss > investigate > malformed) and always has; the metrics
provenance table said "first-observed". The table is corrected — the code is
what produced every published number. Latent corpus-wide; ties cancel to net
zero in the sealed sweeps, so no sealed figure changes. Affects one cell in this
sweep (mas/t07 majority_vote_accuracy 0.360 canonical vs 0.340 first-observed).
Majority-vote accuracy is Tier 2 and is not part of the winner criterion.

**Headline (thinking-on, T=0.7):** single pass^1 0.491 / MAS 0.344 (paired diff
+0.147, CI [0.07, 0.22], p<0.001); DAR 0.434 / 0.421 (diff n.s., p=0.58); flip
rate 0.98 both arms — the lowest repeatability and highest flip rate of any sweep
in the project. 144 malformed (6.3%): 105 MAS "verdict welded onto a prose
paragraph", 27 single-arm empty answers that spent MORE tokens than successful
runs on the same case (the same budget-exhaustion mode that disqualified
qwen3.5:9b@think at gate time), 10 wrong keyword, 2 no decision.
Cross-model comparison against the sealed thinking-off corpus is CONFOUNDED
(lfm2.5 has no admissible thinking-off configuration by construction) — no
"thinking made repeatability worse" claim is supported by this sweep alone.


## 2026-08-12 (late) — `qwen3.5:9b@think-budget` PRE-REGISTERED (budget-raised thinking-on condition, no runs yet)

Written BEFORE run 1 of this condition. Manifest generated
(`results-qwen3.5-9b-thinking-budget/manifest.json`, 2,300 planned runs,
config_hash `15ca01ae0e69`, model_digest `6488c96fa5faab…`, Ollama 0.32.9);
nothing has been executed against it.

**Why.** `qwen3.5:9b@think` failed its gate 6/8 (2026-08-11 late entry): on the
MAS arm the `reporting` node emits EMPTY content after spending 6,108
completion tokens, i.e. deliberation consumes the locked `num_predict=2048`
before any answer is generated. Deterministic across repeats. The owner wants
the qwen family represented in the thinking-on track; that is only possible
with a larger per-call generation budget.

**(a) What changed, and that it is a locked constant.** `num_predict` is a
locked design constant (2048 in every sweep to date, hashed into every
manifest's config record). It is raised to **8192 for this condition and this
condition only**, via a new per-registry-key override
(`config.THINKING_BUDGET_OVERRIDES`, keyed by registry KEY, consulted by
`config_for_model`). No other key's `num_predict` and no other key's
`config_hash` changes — pinned and asserted in
`tests/test_replication.py::test_non_overridden_config_hashes_unchanged`. The
sole reason for the raise is that deliberation demonstrably does not fit in
2048 on a 4-node pipeline: 6,108 tokens observed with no answer emitted. 8192
is the smallest power-of-two headroom above that observed cost; `num_ctx`
stays 16384 so prompt + generation still fit the context window.

**(b) The comparison against the sealed thinking-off `qwen3.5:9b` sweep is
CONFOUNDED.** TWO factors differ between this condition and `results/`:
`think` (false -> true) AND `num_predict` (2048 -> 8192). Any difference
between them is therefore not attributable to deliberation alone. It MUST be
reported as a confounded, two-factor comparison and MUST NOT be presented as a
clean within-model thinking contrast. The only clean within-model
thinking-on/off pair in the corpus remains `muse-glimmer:30b` (both tracks at
the locked 2048). The confound is carried in the artefacts, not just in prose:
the raised budget is inside the hashed config record (this condition's
`config_hash` differs from both `qwen3.5:9b` and `qwen3.5:9b@think`) and is
stamped on every journal line as a new `num_predict` field, so a
budget-raised run can never be pooled with a standard one by accident.

**(c) The budget exhaustion at 2048 is itself a reportable finding.** On a
4-node MAS pipeline under deliberation, the binding constraint is the per-call
generation budget rather than the model: the terminal `reporting` node is
starved of output tokens by the reasoning that precedes it, while the single
agent at the same budget answers fine. That asymmetry — decomposition raising
the per-call generation cost until the last node cannot answer — is a result
about decomposition under deliberation and is reported as such, independently
of whatever this condition produces.

**(d) The primary analysis for this condition is within-condition.** Single vs
MAS at the SAME model, digest, seeds, cases, prompts and the same 8192 budget
is internally valid and unconfounded; it is the pre-registered primary
analysis here, exactly as in every other sweep. Cross-condition statements are
secondary and carry the (b) caveat verbatim.

Registry: `qwen3.5:9b@think-budget` -> served tag `qwen3.5:9b`, `think=true`,
`results-qwen3.5-9b-thinking-budget/`, `num_predict=8192`. Seed schedule
byte-identical to every other sweep (derived from MASTER_SEED only), harness
v2 semantics on `main`, `cache_policy="none"`.


## 2026-08-12 (overnight) — thinking-on sweeps LAUNCHED (infra context 3, Ollama 0.32.9)

Owner-approved launch of the pre-registered thinking-on track (design in the
2026-08-11 evening entry; gate battery results in the 2026-08-11 late entry).
Launch order, sequential on the pinned servers, harness v2 semantics on `main`
(strict tool parsing, cache_policy="none"), think=true:

1. `lfm2.5:8b@think` -> results-lfm2.5-8b-thinking/ (gate 8/8, ETA 5.9 h)
2. `deepseek-r1:14b@think` -> results-deepseek-r1-14b-thinking/ (gate 8/8, ETA 10.0 h)

Both models are admissible ONLY in this track: neither has a valid thinking-off
configuration (lfm2.5 inlines reasoning into content under think:false;
deepseek-r1's reasoning is structural), which is exactly why both were excluded
from the sealed thinking-off corpus. Consequence for analysis, stated before any
run: their comparison against the sealed corpus is CROSS-MODEL and therefore
confounded with model identity. The only within-model thinking-on/off contrast
available is muse-glimmer:30b (passes both tracks, 24.4 h + 34.0 h) — not
launched tonight on time grounds; it remains the designated cross-track pair.

Not launched, with reasons recorded: qwen3.5:9b@think (gate FAIL 6/8 — the MAS
reporting node exhausts the locked num_predict=2048 on deliberation and emits
empty content; a finding, not a defect, and unfixable without breaking a locked
constant), gemma4@think (advertises a thinking capability it does not exercise:
empty channel 3/3), gpt-oss:20b@think (thinking routes cleanly but the
long-standing extraction defect persists, 4/8).

Analysis plan (pre-registered): per-model reports within the thinking-on track;
cross-track statements limited to (a) within-model where available, (b) clearly
labelled cross-model observations against the sealed corpus. Token and wall-clock
costs reported per arm per track — measured deliberation multiplier at gate time
was 1.4-2.1x, not the 3-5x originally assumed.


## 2026-08-11 (evening) — CORPUS SEALED (contexts 1-2); infra context 3 opened; thinking-on track pre-registered

**Seal.** The 7-sweep corpus is closed and final: contexts 1 (Ollama 0.31.1:
qwen3.5:9b headline, qwen2.5:7b, qwen2.5:14b) and 2 (0.32.6: gemma4, plus
0.32.6 re-runs of the three qwen sweeps). 16,100 scored runs, all sealed
against their manifests and independently audited (7 audits, all CONFIRMED).
No further runs will be added to these contexts; nothing below alters them.

**Infra context 3 (Ollama 0.32.9).** Owner upgraded 2026-08-11. All gate
evidence produced under 0.32.6 (granite4.1:8b PASS, lfm2.5:8b FAIL) is
superseded for launch purposes and must be re-produced under 0.32.9 before
any sweep; prior evidence is retained with its version suffix.

**Thinking-on condition (pre-registered, before any run).** Rationale: the
sealed corpus holds deliberation OFF as a control, which maximises internal
validity but excludes the configuration in which reasoning-capable models are
actually deployed (an ecological-validity limitation stated in the
dissertation). This track tests whether the decomposition effect survives
deliberation. Design constants are unchanged EXCEPT the wire ``think``
parameter, which is enabled; every other locked constant (cases, conditions,
repeats, seed schedule, extraction rule, canonical trajectory, metrics)
carries over verbatim, so within-model arm comparisons remain valid.

Gate criterion is INVERTED for this track and pre-registered as such: a
thinking-on model passes only if reasoning is emitted on a SEPARATE channel
(``message.thinking``) and the answer content is free of inline reasoning
markup — a model that inlines ``<think>`` into content (observed on
lfm2.5:8b under ``think: false``) contaminates the measured output and is
excluded. Determinism and pilot-extraction criteria are unchanged.

Thinking-on results are analysed within-model and within-track. Cross-track
comparisons (thinking-on vs the sealed thinking-off corpus) are legitimate
only where the same model appears in both, must be labelled as such, and are
confounded with nothing else by construction (same seeds, same cases, same
harness) — with the caveat that token budgets differ by design and are
reported per arm.

### 2026-08-11 (night) — gate battery under 0.32.9: outcomes

Outcomes only; the design above is unchanged and nothing here re-registers
it. Both pinned servers were restarted and verified at 0.32.9 before the
battery (recorded per evidence file). No sweep was launched. The sealed
corpus was not touched.

Harness support added for `think=True` end-to-end (model factory, hashed
manifest config record, `think` on every journal line, mini-gates), and the
mini-gate think probe now applies the pre-registered INVERTED criterion on
the thinking-on track (`--expect-thinking`, else inferred from
`config.think is True`). Registry keys `"<tag>@think"` → `results-<slug>-
thinking/`; manifests generated with digests, `ollama_version` 0.32.9 and
`think: true` in the hashed config (so a thinking-on `config_hash` can
never collide with its thinking-off twin). Wire path verified in the
installed package: `langchain_ollama/chat_models.py:804` passes `reasoning`
through as the wire `think` field, and reasoning returns on
`additional_kwargs["reasoning_content"]` (`:1268`/`:1350`), never
concatenated into content — so `raw_output`, extraction and every metric
still see the answer channel only.

Per-run cost is now recorded in the gate evidence (wall clock and tokens,
per stage and per arm). ETAs below = 1,150 runs/arm x the slower arm's
observed pilot mean (arms run in parallel, each internally sequential).

| model | thinking cap. | track | think probe | determ. | pilot | A/B wall s | A/B compl. tok | ETA | verdict |
|---|---|---|---|---|---|---|---|---|---|
| granite4.1:8b | no | off (`null`) | PASS clean both surfaces | PASS | 8/8 | 2.6 / 11.6 | 181 / 994 | 3.7 h | **PASS** |
| lfm2.5:8b | yes | off (`null`) | **FAIL** reasoning on `message.thinking` | PASS | 8/8 | 6.2 / 18.7 | 1404 / 4328 | 6.0 h | **FAIL** |
| muse-glimmer:30b | yes | off (`false`) | PASS clean both surfaces | PASS | 8/8 | 15.9 / 76.4 | 637 / 3604 | 24.4 h | **PASS** |
| qwen3.5:9b@think | yes | on | PASS 3/3 separate channel (5,171 ch), content clean | PASS both channels | **6/8** | 14.1 / 50.3 | 1424 / 5267 | 16.1 h | **FAIL** |
| lfm2.5:8b@think | yes | on | PASS 3/3 separate channel (508 ch), content clean | PASS both channels | 8/8 | 6.2 / 18.5 | 1404 / 4328 | 5.9 h | **PASS** |
| gemma4:latest@think | claims yes | on | **FAIL** `think:true` yields an EMPTY thinking channel 3/3 | PASS | 8/8 | 12.2 / 33.6 | 1022 / 3416 | 10.7 h | **FAIL** |
| gpt-oss:20b@think | yes | on | PASS 3/3 separate channel (216 ch), content clean | PASS both channels | **4/8** | 6.6 / 29.4 | 457 / 3075 | 9.4 h | **FAIL** |
| deepseek-r1:14b@think | yes | on | PASS 3/3 separate channel (2,608 ch), content clean | PASS both channels | 8/8 | 7.6 / 31.2 | 664 / 2599 | 10.0 h | **PASS** |
| muse-glimmer:30b@think | yes | on | PASS 3/3 separate channel (668 ch), content clean | PASS both channels | 8/8 | 32.0 / 106.6 | 1441 / 5132 | 34.0 h | **PASS** |

**Thinking-on admissions: `lfm2.5:8b@think`, `deepseek-r1:14b@think`,
`muse-glimmer:30b@think`.** Zero inline-reasoning contamination in any
pilot output on either track (0/8 every model), so the separate-channel
routing holds through the real harness, tools and all — not just the probe.

Findings worth recording:

- **The inversion is real, and it cuts both ways.** `lfm2.5:8b` and
  `deepseek-r1:14b` — excluded from the thinking-off corpus precisely
  because their reasoning is structural — both pass cleanly here. The
  pre-registered criterion admits exactly the models the other track had
  to reject, which is the point of running the track at all.
- **`qwen3.5:9b` fails the thinking-on gate, and the direct cross-track
  comparison is therefore not available.** Not for contamination: its
  probe and determinism are clean (thinking byte-identical at T=0/fixed
  seed). It fails the pilot 6/8 because on the MAS arm the `reporting`
  node returns EMPTY content — `node_outputs` shows orchestrator/data/
  policy_risk all producing text and `reporting` producing 0 characters
  with 6,108 completion tokens spent, i.e. the locked `num_predict=2048`
  budget is consumed by deliberation before any answer is emitted.
  Deterministic (both repeats identical). Raising `num_predict` would fix
  it and is exactly what the pre-registration forbids — it is a locked
  design constant, and changing it would break comparability with the
  sealed corpus, which is the entire value of this model's cross-track
  pair. Recorded as a finding: **on a 4-node pipeline the per-call
  generation budget, not the model, is what binds under deliberation.**
- **`gpt-oss:20b`'s structural thinking IS admissible** — the
  pre-registration's open question is answered yes. It routes reasoning
  cleanly to the separate channel under `think:true`. It still fails, at
  4/8, on the same tool-call/extraction defect that excluded it thinking-
  off on 0.31.1 (5/8) and 0.32.6 (4/8) — version-stable, unrelated to
  deliberation.
- **`gemma4:latest` advertises a capability it does not exercise.**
  `/api/show` lists `thinking`, but `think:true` returns an empty
  `message.thinking` on 3/3 probes while content stays clean. The
  manipulation does not take, so the model cannot be *in* the thinking-on
  condition and is excluded — a capability-metadata caveat worth stating
  in the write-up, since capability flags are how the candidate set was
  drawn.
- **Cost multiplier is 1.4-2.1x, not the anticipated 3-5x.** Same model,
  both tracks: `muse-glimmer:30b` 76.4 -> 106.6 s MAS (1.40x) and 3,604 ->
  5,132 completion tokens (1.42x); `qwen3.5:9b` 7.5 -> 14.1 s single
  (1.89x) and 23.6 -> 50.3 s MAS (2.14x, against its 0.32.6 thinking-off
  gate). Sweep ETAs above are therefore hours, not days, except
  `muse-glimmer:30b@think` at 34 h.

0.32.9 re-gate deltas vs 0.32.6 (thinking-off; evidence retained side by
side as `mini-gates.json` and `mini-gates-ollama0329.json`, and the 0.32.6
manifests archived as `manifest-ollama0326.json` before regeneration):

- `granite4.1:8b` — **no change**, ALL PASS both versions; 8/8 both; wall
  2.39 -> 2.56 s (A) and 10.09 -> 11.57 s (B), i.e. noise.
- `lfm2.5:8b` — **no change**, FAIL both versions with an identical
  signature: `think:false` inlines `<think>` into content on 3/3 probes,
  omitting the parameter routes reasoning to `message.thinking`. There is
  no clean thinking-off configuration for this model; it is only
  admissible on the thinking-on track (where it passes).

`muse-glimmer:30b` pulled successfully under 0.32.9 (the 0.32.6 pull
412'd as "requires newer Ollama") — 18 GB on disk, 27.9B params Q4_K_M,
digest `de878ce33ad81d060001…`. It reports the `thinking` capability, so
the assumption that it is not a thinking model was **wrong**; its
thinking-off entry therefore sends `think: false` explicitly rather than
omitting the parameter (omission would let it think by default, the
qwen3.5 lesson). Two-copy constraint verified live: 15.6 GiB VRAM per
loaded copy, 31.2 GiB for both arms, ~36 GiB total GPU usage against
47.8 GiB — fits with headroom.


## 2026-08-10 — harness v2 (branch `harness-v2`, NOT active on main)

harness v2 — activated only after context-2 chain seals; sweeps 1-7 ran on
harness v1 (main). No v1 sweep result is affected: `main`'s runner, agents
and journal schema are byte-identical to what sweeps 1-7 executed, and
every v2 default reproduces v1 behaviour exactly (`cache_policy="none"`,
additive-only journal keys).

Changes on this branch:

- **MAS inter-node journaling** — `AgentResult` gains an optional
  `node_outputs` field (`None` for the single arm); the MAS graph fills it
  with each node's output text keyed by node name in pipeline order
  (orchestrator, data, policy_risk, reporting), and the runner journals it
  per line as `node_outputs`.
- **Cache-state control** — pre-registrable runner option
  `--cache-policy {none|prewarm|shuffle}` (`ExperimentConfig.cache_policy`,
  default `none` = v1-identical). `prewarm` sends each t0-fixed/pert-t0
  run's exact opening prompt once beforehand and discards it (warm-state
  repeatability); `shuffle` permutes per-repeat case order
  deterministically from `MASTER_SEED` (arm- and model-independent, so
  comparability holds). The policy is recorded in the manifest's hashed
  config record and on every journal line; changing it mid-sweep
  invalidates comparability (documented in the config docstring).
- **Environment fingerprint** — every journal line gains `env`: GPU
  name/driver/VRAM-used snapshot (nvidia-smi, cached per
  `env_fingerprint_every=25` runs) plus host 1-min load and a
  load-high flag; all GPU fields are `null` where nvidia-smi is absent
  (`experiments/harness/env_fingerprint.py`).
- Journal schema doc comments extended (`journal.py`, `runner.execute_run`);
  mocked tests added (`experiments/tests/test_harness_v2.py`).

## 2026-08-08 — infra-context-2 qwen replications (owner-approved, pre-launch)

Purpose: de-confound model family vs Ollama version for the cache-state
determinism findings. The three qwen sweeps completed under Ollama 0.31.1
(infra context 1) are re-run under 0.32.6 (infra context 2) with identical
seeds and design: same 50 + 10 cases, same conditions/repeats, same
2,300-run planned seed schedule (`planned_runs()` depends on `MASTER_SEED`
only), same digest-pinned model blobs.

Mechanism: `config.REPLICATION_MODELS` extended so a registry KEY can
differ from the served MODEL TAG. New keys (each with its own isolated
results dir; runners/manifests/servers use the tag):

- `qwen2.5:7b-instruct@0.32.6` → `results-qwen2.5-7b-ollama0326/` (think=None)
- `qwen3.5:9b@0.32.6` → `results-qwen3.5-9b-ollama0326/` (think=False, as original)
- `qwen2.5:14b-instruct@0.32.6` → `results-qwen2.5-14b-ollama0326/` (think=None)

Existing keys resolve byte-identically (asserted by test); `config_hash`
of each context-2 manifest intentionally equals its original sweep's hash
(same design, same model identity) — the infra context is carried by the
manifest's `ollama_version` and every journal line's `ollama_version`.
Mini-gates re-run per key against the pinned servers before launch;
evidence in each context-2 dir's `gates/`.

The original 0.31.1 results are untouched and remain the pre-registered
results (qwen3.5:9b headline, replications as pre-registered robustness
checks). The context-2 sweeps are exploratory infra replications, analysed
as a separate context, never merged with context-1 journals.

## 2026-08-07 (evening) — infra context 2: Ollama 0.31.1 → 0.32.6; re-gate results; gemma4 admitted

Owner upgraded Ollama to 0.32.6 (all three qwen sweeps were completed and sealed under
0.31.1; per-run `ollama_version` in every journal keeps contexts separable). Prior
0.31.1 gate evidence archived per model as `gates/mini-gates-ollama-0.31.1.json`.
Re-gate under 0.32.6: mistral-nemo FAIL (identical signature, empty output eval=42),
mistral-small3.2 FAIL (identical), llama3.1 FAIL (identical raw-JSON-in-content),
gemma3:27b FAIL (0/8 both arms), granite4 FAIL 6/8 (improved from 5/8, below bar),
gpt-oss:20b FAIL (structural thinking + 4/8). Conclusion: the tool-call parser gap is
version-stable for these models (upstream #17274/#16932 open) — the before/after pair
is recorded as a methodology finding. NEW: gemma4:latest (the model the 0.32.x notes
explicitly fixed) gates ALL PASS 8/8 → admitted as the fourth sweep model, first and
only model of infra context 2. Its results are analyzed within-model (single vs MAS)
and cross-model comparisons note the version difference explicitly.

Any edit to a locked design constant before launch gets a dated note here.
After run 1, changes invalidate the pre-registration (PRD-A).

## 2026-08-07 (00:50) — qwen2.5 replication restarted from zero at owner request

The qwen2.5:7b-instruct sweep had been paused at 135/2300 (to gate mistral-small) and
resumed to 410/2300. Owner requested a fully uninterrupted run instead; the partial
journals (591 runs incl. the resumed segment) were archived untouched to
`results-qwen2.5-7b/partial-run-aborted-2026-08-07/` (never mixed with the fresh run)
and the sweep relaunched from run 1 on the same manifest (identical seed schedule).
Note: resume-vs-restart yields identical planned runs by design; the restart is a
conservatism choice, not a correctness requirement.

## 2026-08-07 (00:30) — llama3.1:8b provisional gate FAIL; audit of headline analysis CONFIRMED

- llama3.1:8b (candidate third model) failed the pilot gate in the same way as both
  mistrals: single arm 0/4 (all malformed, ~1.5 s), MAS 4/4 valid. Probe evidence: with
  the experiment system prompt + bound tools, the model emits its tool call as raw JSON
  in text content which Ollama 0.31.1 fails to parse into a structured call
  (short-system control parses fine). Same class of failure as the mistral family →
  root cause is Ollama-version tool-template robustness, not any single model. Probes
  ran on the dev server (:11434) because the pinned servers were mid-sweep; any future
  launch requires pinned re-gating. Replication set for now: qwen2.5:7b-instruct only.
  Possible path for a third family: Ollama upgrade AFTER all current sweeps, as a
  documented separate infra context, then re-gate.
- Independent audit (fresh-context agent, own code:
  `analysis/independent_check_qwen35.py`) of the sealed qwen3.5:9b analysis:
  ANALYSIS CONFIRMED — integrity clean, all metrics reproduced to 3 d.p., stats match.
  One convention note: single/t07 majority_vote_accuracy 0.360 rests on first-observed
  tie-breaking for two 7–7 tied cases (TXN-2025-017, TXN-2025-048); strict-majority
  rule gives 0.340. Footnote in the dissertation; not corruption.
- Malformed-count clarification: 4 total in the headline sweep = 3 in single/t07-varied
  + 1 in single/pert-t10 (PERT-005 repeat 2). MAS: zero.

## 2026-08-06 (late) — mistral-nemo excluded on failed mini-gate; mistral-small3.2:24b substituted

mistral-nemo:latest failed its mini-gate: single-arm pilot 0/4 valid extractions.
Diagnosis (reproduced; evidence `results-mistral-nemo/gates/mini-gates.json`): with the
experiment's system prompt (~1.7k chars) AND tools bound, the model returns empty
content and no tool calls; short-prompt+tools works, real-prompt-without-tools works.
Accommodating it would require per-model prompt changes — a design fork breaking
cross-model comparability — so the model is excluded, not accommodated. Substitute
third model: `mistral-small3.2:24b` (same family, native function calling; mini-gates
to run before its launch). Decision made after the headline sweep was sealed and before
any nemo sweep run. qwen2.5:7b-instruct replication launched first (mini-gates ALL
PASS: think-probe clean, determinism 5/5 byte-identical, pilot 8/8).

## 2026-08-06 (evening) — replication extension: two additional models

Owner-approved, recorded BEFORE any replication run. After the qwen3.5:9b
sweep is verified and sealed, the ENTIRE pre-registered design is
replicated on two further models:

- `qwen2.5:7b-instruct` (anchor model of arXiv:2511.07585; pulled
  2026-08-06, digest `845dbda0ea48ed749caa…`)
- `mistral-nemo:latest` (already local, digest `e7e06d107c6c86ed0cf4…`)

Identical design: same 50 + 10 cases, same conditions and repeat counts,
same metrics tier table, and the **same planned seed schedule** —
`planned_runs()` derives seeds from `MASTER_SEED` only, independent of
model, so per-(condition, case, repeat) seeds are identical across models
for cross-model comparability (asserted by test).

Each model gets its own sibling results dir (`results-qwen2.5-7b/`,
`results-mistral-nemo/`) with its own manifest (own digest, own
config_hash — the hash pins model identity), journals, progress and gates
evidence; no cross-dir contamination (asserted by test).

Think handling per model: qwen3.5:9b keeps `think: false` on the wire;
the two replication models have no documented thinking mode, so the
parameter is **omitted** (`think=None`; the ollama client serializes with
`exclude_none`) — exact behaviour captured per model by the new
mini-gates (`experiments.harness.mini_gates`) before their launch.

**`qwen3.5:9b` remains the headline pre-registered result; the
replications are analysed as robustness checks** (per-model reports via
`analysis.report --model`, side-by-side Tier 1 via `analysis.compare`).

## 2026-08-06 — gate day: arm-A server port :11434 → :11437 (pre-launch)

Environment constraint found during launch-gate prep: the machine's
systemd Ollama service (runs as user `ollama`, unpinned env, default
KEEP_ALIVE/NUM_PARALLEL) permanently owns :11434 and cannot be stopped
without interactive sudo, which the gate session does not have. Rather
than run arm A on an unpinned server, arm A's dedicated pinned server
moved to **:11437** (`scripts/serve-armA.sh`, `experiments/config.py`,
`scripts/launch-sweep.sh`); arm B stays on :11435 as pre-registered.
The systemd server on :11434 becomes the dev/analysis server (taking the
role PRD-A assigned to :11436) and must receive no sweep traffic.

Both pinned servers read the world-readable system model store
(`OLLAMA_MODELS=/usr/share/ollama/.ollama/models`) — user `el` has no
local store, and the system store holds the exact digest-pinned weights
(verified against the manifest on both servers at gate time).

Port numbers are execution infrastructure, not a locked design row (the
locked constant is "two Ollama servers, one arm each, pinned env"), and
no journalled runs exist; recorded here pre-launch per the
pre-registration discipline.

## 2026-08-06 — manifest re-stamp + ROUGE-L appendix metric (pre-launch)

- **Manifest re-stamped** post pre-registration commit, pre-run-1: the
  recorded `git_sha` (`a1aec5c`) predated the commits that contain the
  reviewed harness; regenerated so it points at the committed code
  (`944b0bd`). Verified: `config_hash` unchanged (`76337b11ca1c…`) and the
  2,300-run plan (seeds, order, totals) plus model digest/show/version are
  byte-identical — only `git_sha` and `created_at` differ. No journals
  existed at re-stamp time.
- **ROUGE-L lexical consistency added** (lecturer-requested, appendix tier,
  pre-registered 2026-08-06 while journals are empty): per-case mean
  pairwise ROUGE-L F1 over the FULL `raw_output` across repeats
  (token-level LCS, lowercase, whitespace tokenization; implemented
  in-repo, no new dependency). Reported per arm × condition in its own
  "Appendix: lexical consistency (ROUGE-L)" report section, labelled as
  surface-form overlap, distinct from decision- and trajectory-level
  metrics. **Does not alter the pre-registered Tier 1 winner criterion.**
  BLEU was rejected: BLEU is precision/reference-oriented and needs a
  designated reference; repeats of one case have none, while pairwise
  ROUGE-L F1 is symmetric and reference-free.

## 2026-08-06 — final pre-launch fix batch (port reviews + goals audit)

- **tokens ÷ pass^k at all k**: `analysis/metrics.py` previously reported a
  single `tokens_per_pass` at k = n_repeats (k=15 would likely be zero →
  empty cell). Now `pass^k` and `tokens_per_pass^k` are reported at every
  supported k ∈ {1, 5, 15} (plus k=n) as separate columns. **Pre-registered
  as all-k reporting, decided 2026-08-06 before any results exist** — no
  post-hoc k choice.
- **Recursion guard** (`app/agents/single.py`): graph recursion limit is now
  `max(1, 2*max_iterations+4)` — adversarial finding: `max_iterations < 1`
  would produce an invalid limit. Unreachable at the locked value (8);
  guarded anyway.
- **Client libs pinned** (`backend/requirements.txt`): ollama==0.6.2,
  langchain-ollama==1.1.0, langchain-core==1.4.9, langgraph==1.2.9 — the
  wire-payload tests mock the client boundary, so an unpinned reinstall
  could change wire serialization invisibly.
- Production-side parity (PRD-B, no experiment-design impact): analysis
  model factory now sends `think:false`/`num_ctx=16384`/`num_predict=2048`
  like the harness factory; audit reports pin the model digest and persist
  injected session context; `.env.example` documents ANALYSIS_* vars incl.
  the :11436 sweep rule.

## 2026-08-06 — arm A ported to LangGraph (owner decision)

Rationale: both arms now execute on the same LangGraph runtime, removing a
framework confound between arms (previously arm A ran a hand-rolled
LangChain loop while arm B ran LangGraph). `app/agents/single.py` now
compiles the tool loop as the idiomatic ReAct graph (agent node + tool node
+ conditional edges); `run_tool_loop` keeps its signature and is still the
single code path used by arm A directly AND by every arm-B node, so the
port covers both arms at once. `langgraph.prebuilt.create_react_agent` was
rejected: its recursion limit raises instead of gracefully returning the
last assistant text, breaking our max-iterations semantics.

- Prompts, case rendering, and wire parameters unchanged: every model call
  still carries `think: false`, `options.seed`, `options.temperature`,
  `num_ctx`, `num_predict` — asserted by a new adversarial wire-payload
  test that mocks `ollama.AsyncClient.chat` and inspects captured payloads
  over a multi-turn tool run (`experiments/tests/test_single_graph.py`).
- Loop semantics byte-preserved: max-iterations cap (final call's tools
  still executed, last text returned), unknown-tool `error:` results,
  requested-call recording order, `SingleAgent` constructor signature (the
  production adapter call site in `app/agents/runner.py` is untouched).
- No observable behavioural deltas: `agent_messages` still counts LLM
  (assistant) messages — one per agent-node invocation, same number as the
  pre-port loop; token accounting and `tool_calls` identical.
- `config_hash` verified UNCHANGED (`76337b11ca1c…`) — prompts and wire
  params are what the manifest hashes, and neither moved; manifest not
  regenerated.

## 2026-08-06 — package relocated to backend/experiments/ (owner decision)

Mechanical move of the whole `experiments/` package (results/, gates
evidence, manifest, CHANGELOG, PILOT-NOTES, perturbation cases included)
from repo root to `backend/experiments/`, so it shares the `backend/`
package tree with `app/` and the `sys.path` shim in `experiments/__init__`
is deleted. Runner/scripts/tests now run from `backend/` (or with
`PYTHONPATH=backend`). Path derivations updated: `config.py` root
constants, `scripts/launch-sweep.sh`, the FastAPI progress route
(`app/api/routes/analysis.py`), tests conftest, PRD-A layout line.
**No locked design constant touched; `config_hash` verified unchanged
(`76337b11ca1c…`) — the hashed config contains no filesystem paths, so
`results/manifest.json` was NOT regenerated.**

## 2026-08-05 — pre-launch review fixes (conformance + adversarial review)

All pre-launch (no journalled runs yet); no locked design constant changed.

- **F1** `harness/journal.py`: torn-tail healing on open-for-append. A
  kill -9 mid-write leaves a partial line with no trailing newline; the
  next append would merge onto it (run lost from resume, later
  JSONDecodeError in both runners). Implemented as truncate-back-to-last-
  complete-line rather than the suggested newline-first write: newline-
  healing would leave the fragment as a corrupt *middle* line, which the
  (deliberately strict) reader then rejects. The torn run simply re-runs.
- **F2** `harness/journal.py` + `harness/runner.py`: `write_progress` now
  uses a unique tmp name per call (pid+uuid) before the atomic rename —
  the two arm runners can no longer race on a shared tmp path; all
  `write_progress` call sites in the runner are wrapped so progress
  reporting can never kill a sweep.
- **F3** `harness/runner.py`: model-digest drift vs the manifest is now a
  hard failure at runner start; `--allow-digest-mismatch` overrides (with
  a mandatory CHANGELOG note). `scripts/launch-sweep.sh` verifies the
  post-pull digest on both servers against the manifest and aborts on
  mismatch.
- **F4** `harness/extraction.py`: docstring (the pre-registration record)
  aligned to the implemented rule — only the last non-empty line is
  examined, earlier `FINAL DECISION:` lines are ignored; the trailing-
  code-fence → malformed mode is documented and accepted.
- **F5** `scripts/launch-sweep.sh`: pre-existing `ollama-armA/B` tmux
  sessions are now a hard error (stale servers can't be verified to carry
  the pinned env); `--recreate` kills and restarts them. Pre-existing
  runner sessions always abort (duplicate writers on one journal).
- **R2** `harness/manifest.py`: sampling section now records top_p/top_k/
  **min_p** numerically (server defaults 0.9/40/0.0, `set_by_harness:
  false`); modelfile overrides remain visible in `model_show`. Config hash
  changed accordingly; `results/manifest.json` regenerated pre-launch.
- Git-sync path bug: runner now threads its `results_dir` into
  `git_sync.sync_results`, so a pilot with `--results-dir` can no longer
  commit the default results directory.
- `results/.gitignore` added: `runner-*.log`, `.git-sync.lock`,
  `.progress-*.tmp` excluded from the 25-run checkpoint commits.

## 2026-08-05 — initial build

- Harness built per PRD-A "Components to build"; no deviations from the
  locked constants table.
- Operationalisations fixed before run 1 (recorded here because the PRD
  leaves them implicit):
  - Decision extraction: label read from the **last non-empty line**,
    markdown emphasis chars stripped, one trailing `.`/`!` tolerated,
    case-insensitive (`experiments/harness/extraction.py`).
  - Varied seeds: drawn from `MASTER_SEED=20260805`; the same seed is
    shared by both arms for a given (condition, case, repeat) so the arm
    comparison is not confounded with the seed schedule.
  - MAS tool partition (union = arm A's full set): data agent →
    `search_precedents`, `get_customer_profile`, `check_sanctions_list`;
    policy&risk → `calculate_risk_score`; orchestrator/reporting → none
    (`experiments/config.py::MAS_TOOL_PARTITION`).
  - Entropy normalised by `log2(4)` (3 decisions + malformed).
  - `num_ctx=16384`, `num_predict=2048`, `max_iterations=8`,
    `run_timeout_s=900` — recorded in the manifest config hash.
- G0 and G1 probed on the dev server: both PASS (see
  `experiments/PILOT-NOTES.md`); model stays `qwen3.5:9b`.
