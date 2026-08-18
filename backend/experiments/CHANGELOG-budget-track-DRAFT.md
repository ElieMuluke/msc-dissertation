# DRAFT pre-registration — budget-sensitivity track (v2b)

> **Status: DRAFT — not yet registered.** This entry lives on branch
> `budget-track-v2b` only. At launch ("GO" from the owner) it is copied into
> `backend/experiments/CHANGELOG.md` as a dated entry on `main`, BEFORE any
> manifest is stamped and before run 1. Until then nothing in this track is
> registered and no run may be journalled under it.

## Pre-stated question

**Does the arm difference survive when the binding constraint is removed and
disclosed?** The v2 sweeps ran a uniform `max_iterations = 8` per agent —
8 LLM turns for the monolith versus a pooled 4 x 8 = 32 for the 4-node MAS
pipeline, with the per-role caps sized to nothing and disclosed to no one.
The 2026-08-17 audit established that per-node cap exhaustion (data node at
exactly 8 while still requesting tools) is the dominant mechanism behind
empty MAS node outputs, that decomposition is a necessary co-factor, and
that detectability is asymmetric across arms. This track equalises the
pooled turn budget across arms (32 vs 32), sizes the per-role budgets to
role demand, and tells every agent its exact budget so it can ration. If
the single-vs-MAS differences in repeatability, accuracy, and failure
structure persist under an equalised, disclosed budget, they are properties
of decomposition; if they vanish, v2's arm difference was (at least partly)
an artefact of the binding, undisclosed constraint.

## Design

### Iteration budgets (LLM-turn budgets, the existing `max_iterations` semantics — NOT tool-call counts)

| Agent                  | v2 (uniform) | v2b budget | Rationale                          |
|------------------------|--------------|------------|------------------------------------|
| single (monolith)      | 8            | **32**     | pooled parity with the pipeline    |
| MAS orchestrator       | 8            | **4**      | no tools; plan only                |
| MAS data               | 8            | **16**     | the only multi-tool node           |
| MAS policy_risk        | 8            | **8**      | one tool                           |
| MAS reporting          | 8            | **4**      | no tools; report only              |
| **MAS pooled**         | 32           | **32**     | equal to the single arm            |

Enforcement: `MasAgent` now accepts a per-node budget mapping
(`config.MAS_ITERATION_BUDGETS`); the single arm gets
`config.SINGLE_ITERATION_BUDGET`. An int still behaves exactly as v2 did
(uniform), and every non-b32 registry key still constructs byte-identically
to v2 (regression-guarded by `tests/test_budget_track.py` and the pinned
config hashes in `tests/test_replication.py`).

### Budget disclosure (one added sentence per prompt, verbatim)

Each arm's prompt gains EXACTLY one sentence stating that agent's budget.
The v2 prompt constants are untouched (sealed manifests embed them); the
b32 variants (`SYSTEM_PROMPT_B32`, `MAS_PROMPTS_B32`) are built from the
originals plus the sentence, and are embedded and hashed in b32 manifests.

- **single** (before the output contract):
  "You have a budget of at most 32 tool-use steps; plan your investigation
  so the most decisive checks come first, and stop to state your final
  decision before the budget runs out."
- **MAS orchestrator** (appended): "You have a budget of at most 4 steps
  for this stage."
- **MAS data** (appended): "You have a budget of at most 16 tool-use steps;
  plan your screening so the most decisive checks come first, and stop to
  write your evidence summary before the budget runs out."
- **MAS policy_risk** (appended): "You have a budget of at most 8 tool-use
  steps; plan your scoring so the most decisive checks come first, and stop
  to write your risk assessment before the budget runs out."
- **MAS reporting** (before the output contract): "You have a budget of at
  most 4 steps for this stage."

### The six sweeps (registry keys, in launch order)

| # | Registry key                  | Served tag           | think | num_predict | Results dir                          | ETA    |
|---|-------------------------------|----------------------|-------|-------------|--------------------------------------|--------|
| 1 | `qwen2.5:7b-instruct@b32`     | qwen2.5:7b-instruct  | omit  | 2048        | `results-budget-qwen2.5-7b`          | ~5 h   |
| 2 | `granite4.1:8b@b32`           | granite4.1:8b        | omit  | 2048        | `results-budget-granite4.1-8b`       | ~5 h   |
| 3 | `qwen3.5:9b@b32`              | qwen3.5:9b           | false | 2048        | `results-budget-qwen3.5-9b`          | ~8 h   |
| 4 | `lfm2.5:8b@b32-think`         | lfm2.5:8b            | true  | 2048        | `results-budget-lfm2.5-8b-thinking`  | ~8 h   |
| 5 | `qwen3.5:9b@b32-think-budget` | qwen3.5:9b           | true  | **8192**    | `results-budget-qwen3.5-9b-thinking` | ~34 h  |
| 6 | `gemma4:latest@b32`           | gemma4:latest        | omit  | 2048        | `results-budget-gemma4`              | ~20 h  |

The **muse-glimmer:30b pair** (`muse-glimmer:30b` thinking-off and
`@think`, under equalised budgets) is queued AFTER all six complete; its
keys will be registered in a follow-up dated entry before its launch.

## What changes vs v2

1. Per-role iteration budgets (table above) instead of the uniform scalar.
2. One budget-disclosure sentence per prompt (verbatim above).
3. Six new registry keys with isolated `results-budget-*` dirs.
4. b32 manifests hash the budgets (`iteration_budgets`) and the B32 prompt
   text; every b32 `config_hash` is new by design (pinned pre-launch in
   `tests/test_replication.py`).
5. Every b32 journal line stamps `iteration_budgets` (the single scalar or
   the per-node mapping actually enforced on that run) for audit.

## What stays locked (unchanged from v2)

Cases (100 primary + 15 perturbation), conditions and repeats, the seed
schedule (same `MASTER_SEED = 20260805` derivation — `planned_runs()` is
model-independent, so per-(condition, case, repeat) seeds are identical to
every sealed sweep), `num_predict = 2048` (sole exception below),
`num_ctx = 16384`, `cache_policy = "none"`, strict v2 parsing
(`FINAL DECISION:` contract), `run_timeout_s = 900`, tool partition, arm
topology, one-Ollama-server-per-arm ports, malformed-never-excluded and
never-retried semantics, journal/manifest discipline.

## Pre-declared confound: `qwen3.5:9b@b32-think-budget` runs num_predict 8192

The qwen3.5:9b thinking-ON sweep cannot complete a 4-node pipeline within
2048 generated tokens (its reporting node spends the whole budget on
deliberation — see CHANGELOG 2026-08-12); its sealed counterpart
`qwen3.5:9b@think-budget` therefore ran the pre-approved 8192 override, and
this b32 twin carries the SAME override via the existing
`THINKING_BUDGET_OVERRIDES` mechanism. Consequently any comparison of sweep
5 against a 2048 sweep is confounded by the generation budget as well as by
the iteration-budget manipulation, and must be reported as such. Its clean
comparator is `qwen3.5:9b@think-budget` (identical tag, think, and
num_predict; the iteration budgets + disclosure are the only difference).

## Analysis commitments

- Same metrics, gates, and seal checks as v2. Seal checks run via the
  model-agnostic `analysis/seal_checks.py` (generalised 2026-08-18 from
  `seal_checks_muse_glimmer.py`, which is retained for provenance),
  including the severed-channel (empty node output) detector and the
  canonical-order majority tie-break.
- Primary contrast per model: b32 sweep vs its sealed v2 counterpart
  (same tag, same think, same num_predict — budgets + disclosure are the
  only difference; the sole exception is sweep 5's comparator, above).
- Cap-exhaustion accounting (per-node turn counts at budget) is reported
  for every b32 MAS arm, to verify the constraint is in fact non-binding.
