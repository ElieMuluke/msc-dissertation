# OWNER'S MASTER DATA REPORT — every experiment run, recomputed from the journals

*Generated 2026-08-18 10:30 UTC by `backend/experiments/analysis/master_report_gen.py`. Every number in this document was recomputed directly from `results*/journal-{single,mas}.jsonl` using the locked conventions in `analysis/metrics.py`; nothing is copied from derived documents. Zero LLM calls, no GPU, journals read-only. The budget track is IN FLIGHT: all `@b32` numbers are PARTIAL snapshots taken at generation time.*

**Conventions.** pass^k = C(c,k)/C(n,k), agreement with benchmark authors' labels (never "correctness"); malformed is an outcome category and is never excluded; DAR = fraction of identical unordered repeat pairs; alpha = Krippendorff (nominal), cases as units, repeats as coders; majority ties break by canonical OUTCOMES order (escalate > dismiss > investigate > malformed); entropy normalised by log2(4); best-constant baselines 0.520 (primary, constant-dismiss over 50 cases) and 0.600 (perturbation, constant-dismiss over 10 cases). MV movement: perturbed-case majority vote vs same-arm base-case majority vote, t0-fixed base for pert-t0 and t07-varied base for pert-t05/pert-t10. Wall clock is contention-contaminated wherever the two arms co-ran on one GPU (flagged per sweep); tokens are the cost metric.

## 1. Corpus map

| registry key | results dir | served tag | think | infra ctx | harness | status | runs (single+mas) | dates |
|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | `results` | qwen3.5:9b | off (false) | 1 · Ollama 0.31.1 | v1 | SEALED | 1150+1150 | 2026-08-06 → 2026-08-06 |
| `qwen2.5:7b-instruct` | `results-qwen2.5-7b` | qwen2.5:7b-instruct | n/a (omit) | 1 · Ollama 0.31.1 | v1 | SEALED | 1150+1150 | 2026-08-06 → 2026-08-07 |
| `qwen2.5:14b-instruct` | `results-qwen2.5-14b` | qwen2.5:14b-instruct | n/a (omit) | 1 · Ollama 0.31.1 | v1 | SEALED | 1150+1150 | 2026-08-07 → 2026-08-07 |
| `gemma4:latest` | `results-gemma4` | gemma4:latest | n/a (omit) | 2 · Ollama 0.32.6 | v1 | SEALED | 1150+1150 | 2026-08-07 → 2026-08-08 |
| `qwen2.5:7b-instruct@0.32.6` | `results-qwen2.5-7b-ollama0326` | qwen2.5:7b-instruct | n/a (omit) | 2 · Ollama 0.32.6 | v1 | SEALED | 1150+1150 | 2026-08-08 → 2026-08-10 |
| `qwen3.5:9b@0.32.6` | `results-qwen3.5-9b-ollama0326` | qwen3.5:9b | off (false) | 2 · Ollama 0.32.6 | v1 | SEALED | 1150+1150 | 2026-08-10 → 2026-08-10 |
| `qwen2.5:14b-instruct@0.32.6` | `results-qwen2.5-14b-ollama0326` | qwen2.5:14b-instruct | n/a (omit) | 2 · Ollama 0.32.6 | v1 | SEALED | 1150+1150 | 2026-08-10 → 2026-08-11 |
| `lfm2.5:8b@think` | `results-lfm2.5-8b-thinking` | lfm2.5:8b | ON | 3 · Ollama 0.32.9 | v2 | SEALED | 1150+1150 | 2026-08-11 → 2026-08-12 |
| `deepseek-r1:14b@think` | `results-deepseek-r1-14b-thinking` | deepseek-r1:14b | ON | 3 · Ollama 0.32.9 | v2 | SEALED — EXCLUDED | 1150+1150 | 2026-08-13 → 2026-08-13 |
| `qwen3.5:9b@think-budget` | `results-qwen3.5-9b-thinking-budget` | qwen3.5:9b | ON | 3 · Ollama 0.32.9 | v2 | SEALED | 1150+1150 | 2026-08-12 → 2026-08-13 |
| `granite4.1:8b` | `results-granite4.1-8b` | granite4.1:8b | n/a (omit) | 3 · Ollama 0.32.9 | v2 | SEALED | 1150+1150 | 2026-08-13 → 2026-08-13 |
| `muse-glimmer:30b` | `results-muse-glimmer-30b` | muse-glimmer:30b | off (false) | 3 · Ollama 0.32.9 | v2 | SEALED | 1150+1150 | 2026-08-13 → 2026-08-15 |
| `muse-glimmer:30b@think` | `results-muse-glimmer-30b-thinking` | muse-glimmer:30b | ON | 3 · Ollama 0.32.9 | v2 | CLOSED — single-arm-only | 1150+201 | 2026-08-15 → 2026-08-18 |
| `qwen2.5:7b-instruct@b32` | `results-budget-qwen2.5-7b` | qwen2.5:7b-instruct | n/a (omit) | b32 · Ollama 0.32.9 | v2b | LIVE | 491+96 | 2026-08-18 → 2026-08-18 |
| `granite4.1:8b@b32` | `results-budget-granite4.1-8b` | granite4.1:8b | n/a (omit) | b32 · Ollama 0.32.9 | v2b | QUEUED | 0+0 | — |
| `qwen3.5:9b@b32` | `results-budget-qwen3.5-9b` | qwen3.5:9b | off (false) | b32 · Ollama 0.32.9 | v2b | QUEUED | 0+0 | — |
| `lfm2.5:8b@b32-think` | `results-budget-lfm2.5-8b-thinking` | lfm2.5:8b | ON | b32 · Ollama 0.32.9 | v2b | QUEUED | 0+0 | — |
| `qwen3.5:9b@b32-think-budget` | `results-budget-qwen3.5-9b-thinking` | qwen3.5:9b | ON | b32 · Ollama 0.32.9 | v2b | QUEUED | 0+0 | — |
| `gemma4:latest@b32` | `results-budget-gemma4` | gemma4:latest | n/a (omit) | b32 · Ollama 0.32.9 | v2b | QUEUED | 0+0 | — |

**Corpus totals (everything journalled, including excluded, closed and live partial dirs; live dirs counted by UNIQUE run key — see §4): 29,538 runs — 28,951 sealed/closed + 587 live-partial — 200,888,938 tokens (prompt+completion), 191.4 GPU-busy hours (sum of per-run wall clocks; arms co-resident on one GPU, so this is model-busy time, not elapsed span).**

Empty registry dirs with no journals (gate-failed / never launched): `results-gemma3-27b`, `results-gemma4-thinking`, `results-gpt-oss-20b`, `results-gpt-oss-20b-thinking`, `results-granite4`, `results-lfm2.5-8b`, `results-llama3.1-8b`, `results-mistral-nemo`, `results-mistral-small3.2`, `results-qwen3.5-9b-thinking` (gate FAIL 6/8). Archived partials (never counted): `results-qwen2.5-7b/partial-run-aborted-2026-08-07/`, `results-gemma4/partial-run-aborted-2026-08-07/`.

## 2. Headline cross-model tables and the six analytical findings

### 2.0 Cross-model Tier-1 — `t07-varied` (realistic setting; the committed primary comparison condition)

| sweep | arm | runs | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | entropy | malf% | tok/run | wall s* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | single | 750 | 0.364 | 0.078 | 0.040 | 0.618 | 0.205 | 0.920 | 0.360 | 0.409 | 0.4% | 4,241 | 6.5 |
| `qwen3.5:9b` | mas | 750 | 0.253 | 0.110 | 0.060 | 0.802 | 0.203 | 0.760 | 0.220 | 0.223 | 0.0% | 7,760 | 16.3 |
| `qwen2.5:7b-instruct` | single | 750 | 0.293 | 0.089 | 0.000 | 0.719 | 0.102 | 0.880 | 0.200 | 0.312 | 1.1% | 2,074 | 2.6 |
| `qwen2.5:7b-instruct` | mas | 750 | 0.449 | 0.107 | 0.020 | 0.647 | 0.279 | 0.900 | 0.540 | 0.364 | 0.5% | 6,458 | 9.4 |
| `qwen2.5:14b-instruct` | single | 750 | 0.248 | 0.149 | 0.060 | 0.893 | 0.382 | 0.460 | 0.220 | 0.121 | 0.3% | 2,128 | 7.5 |
| `qwen2.5:14b-instruct` | mas | 750 | 0.221 | 0.145 | 0.100 | 0.914 | 0.340 | 0.320 | 0.220 | 0.094 | 0.3% | 5,903 | 16.4 |
| `gemma4:latest` | single | 750 | 0.552 | 0.185 | 0.080 | 0.594 | 0.387 | 0.900 | 0.600 | 0.430 | 1.3% | 3,931 | 18.7 |
| `gemma4:latest` | mas | 750 | 0.297 | 0.113 | 0.040 | 0.705 | 0.406 | 0.840 | 0.320 | 0.304 | 0.0% | 9,491 | 42.9 |
| `qwen2.5:7b-instruct@0.32.6` | single | 750 | 0.299 | 0.095 | 0.020 | 0.715 | 0.106 | 0.840 | 0.200 | 0.313 | 1.1% | 2,086 | 2.7 |
| `qwen2.5:7b-instruct@0.32.6` | mas | 750 | 0.456 | 0.139 | 0.040 | 0.661 | 0.276 | 0.860 | 0.560 | 0.345 | 0.3% | 6,469 | 10.0 |
| `qwen3.5:9b@0.32.6` | single | 750 | 0.339 | 0.079 | 0.040 | 0.655 | 0.241 | 0.900 | 0.300 | 0.368 | 0.4% | 4,272 | 6.5 |
| `qwen3.5:9b@0.32.6` | mas | 750 | 0.255 | 0.108 | 0.040 | 0.809 | 0.191 | 0.800 | 0.220 | 0.223 | 0.0% | 7,761 | 18.3 |
| `qwen2.5:14b-instruct@0.32.6` | single | 750 | 0.248 | 0.149 | 0.060 | 0.893 | 0.382 | 0.460 | 0.220 | 0.121 | 0.3% | 2,128 | 7.6 |
| `qwen2.5:14b-instruct@0.32.6` | mas | 750 | 0.221 | 0.145 | 0.100 | 0.914 | 0.340 | 0.320 | 0.220 | 0.094 | 0.3% | 5,903 | 16.9 |
| `lfm2.5:8b@think` | single | 750 | 0.491 | 0.065 | 0.020 | 0.434 | 0.159 | 0.980 | 0.680 | 0.643 | 4.4% | 4,332 | 6.7 |
| `lfm2.5:8b@think` | mas | 750 | 0.344 | 0.047 | 0.020 | 0.421 | 0.130 | 0.980 | 0.360 | 0.691 | 10.7% | 10,029 | 19.4 |
| `qwen3.5:9b@think-budget` | single | 750 | 0.548 | 0.177 | 0.020 | 0.631 | 0.413 | 0.940 | 0.640 | 0.411 | 1.9% | 9,550 | 28.1 |
| `qwen3.5:9b@think-budget` | mas | 750 | 0.264 | 0.067 | 0.000 | 0.724 | 0.277 | 0.880 | 0.220 | 0.308 | 1.7% | 17,318 | 75.6 |
| `granite4.1:8b` | single | 750 | 0.299 | 0.171 | 0.120 | 0.830 | 0.328 | 0.620 | 0.240 | 0.186 | 0.0% | 4,343 | 4.5 |
| `granite4.1:8b` | mas | 750 | 0.289 | 0.180 | 0.160 | 0.845 | 0.297 | 0.500 | 0.220 | 0.165 | 0.0% | 8,380 | 11.4 |
| `muse-glimmer:30b` | single | 750 | 0.392 | 0.175 | 0.140 | 0.753 | 0.435 | 0.640 | 0.380 | 0.250 | 0.1% | 7,063 | 38.8 |
| `muse-glimmer:30b` | mas | 750 | 0.264 | 0.153 | 0.100 | 0.882 | 0.619 | 0.340 | 0.240 | 0.121 | 0.0% | 17,180 | 84.3 |
| `muse-glimmer:30b@think` | single | 750 | 0.311 | 0.205 | 0.160 | 0.822 | 0.613 | 0.620 | 0.320 | 0.201 | 3.9% | 12,866 | 44.7 |

*Wall clock contention-contaminated in every sweep (arms co-ran); primary baseline = 0.520. `deepseek-r1:14b@think` is excluded from comparison and appears in §5 only; budget-track partials appear in §4 only.*

### 2.0b Cross-model Tier-1 — `t0-fixed` (determinism setting)

| sweep | arm | runs | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | entropy | malf% | tok/run | wall s* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | single | 250 | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 | 0.000 | 0.0% | 4,219 | 6.2 |
| `qwen3.5:9b` | mas | 250 | 0.260 | 0.260 | — | 1.000 | 1.000 | 0.000 | 0.260 | 0.000 | 0.0% | 7,501 | 19.7 |
| `qwen2.5:7b-instruct` | single | 250 | 0.244 | 0.220 | — | 0.952 | 0.783 | 0.120 | 0.240 | 0.043 | 1.6% | 2,099 | 2.6 |
| `qwen2.5:7b-instruct` | mas | 250 | 0.380 | 0.200 | — | 0.824 | 0.576 | 0.380 | 0.380 | 0.152 | 0.0% | 6,028 | 11.0 |
| `qwen2.5:14b-instruct` | single | 250 | 0.188 | 0.160 | — | 0.968 | 0.884 | 0.080 | 0.180 | 0.029 | 0.0% | 2,138 | 6.6 |
| `qwen2.5:14b-instruct` | mas | 250 | 0.232 | 0.220 | — | 0.976 | 0.758 | 0.060 | 0.220 | 0.022 | 0.0% | 5,833 | 21.4 |
| `gemma4:latest` | single | 250 | 0.648 | 0.520 | — | 0.880 | 0.819 | 0.300 | 0.640 | 0.108 | 0.0% | 3,663 | 17.4 |
| `gemma4:latest` | mas | 250 | 0.312 | 0.240 | — | 0.804 | 0.609 | 0.400 | 0.300 | 0.167 | 0.0% | 8,953 | 50.8 |
| `qwen2.5:7b-instruct@0.32.6` | single | 250 | 0.244 | 0.220 | — | 0.952 | 0.783 | 0.120 | 0.240 | 0.043 | 1.6% | 2,099 | 2.7 |
| `qwen2.5:7b-instruct@0.32.6` | mas | 250 | 0.380 | 0.200 | — | 0.804 | 0.528 | 0.420 | 0.360 | 0.169 | 0.0% | 6,084 | 11.4 |
| `qwen3.5:9b@0.32.6` | single | 250 | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 | 0.000 | 0.0% | 4,384 | 6.6 |
| `qwen3.5:9b@0.32.6` | mas | 250 | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 | 0.000 | 0.0% | 7,492 | 19.5 |
| `qwen2.5:14b-instruct@0.32.6` | single | 250 | 0.188 | 0.160 | — | 0.968 | 0.884 | 0.080 | 0.180 | 0.029 | 0.0% | 2,138 | 6.7 |
| `qwen2.5:14b-instruct@0.32.6` | mas | 250 | 0.232 | 0.220 | — | 0.976 | 0.758 | 0.060 | 0.220 | 0.022 | 0.0% | 5,833 | 21.9 |
| `lfm2.5:8b@think` | single | 250 | 0.520 | 0.520 | — | 1.000 | 1.000 | 0.000 | 0.520 | 0.000 | 2.0% | 4,762 | 6.6 |
| `lfm2.5:8b@think` | mas | 250 | 0.480 | 0.480 | — | 1.000 | 1.000 | 0.000 | 0.480 | 0.000 | 6.0% | 10,270 | 19.4 |
| `qwen3.5:9b@think-budget` | single | 250 | 0.560 | 0.560 | — | 1.000 | 1.000 | 0.000 | 0.560 | 0.000 | 0.0% | 9,092 | 27.6 |
| `qwen3.5:9b@think-budget` | mas | 250 | 0.260 | 0.260 | — | 1.000 | 1.000 | 0.000 | 0.260 | 0.000 | 0.0% | 15,284 | 87.0 |
| `granite4.1:8b` | single | 250 | 0.288 | 0.220 | — | 0.960 | 0.848 | 0.100 | 0.300 | 0.036 | 0.0% | 4,373 | 4.1 |
| `granite4.1:8b` | mas | 250 | 0.336 | 0.220 | — | 0.868 | 0.511 | 0.280 | 0.340 | 0.114 | 0.0% | 7,667 | 13.8 |
| `muse-glimmer:30b` | single | 250 | 0.360 | 0.360 | — | 1.000 | 1.000 | 0.000 | 0.360 | 0.000 | 0.0% | 7,568 | 40.9 |
| `muse-glimmer:30b` | mas | 250 | 0.292 | 0.200 | — | 0.936 | 0.780 | 0.140 | 0.320 | 0.056 | 0.0% | 17,505 | 138.6 |
| `muse-glimmer:30b@think` | single | 250 | 0.344 | 0.340 | — | 0.992 | 0.983 | 0.020 | 0.340 | 0.007 | 4.0% | 13,580 | 58.8 |
| `muse-glimmer:30b@think` ⛔closed@201 | mas | 201 | 0.195 | 0.175 | — | 1.000 | 1.000 | 0.000 | 0.195 | 0.000 | 0.0% | 25,767 | 178.5 |

### Finding 1 — Model-dependence of the arm effect (direction of effect)

| sweep | pass^1 single | pass^1 MAS | Δpass^1 (MAS−single) | DAR single | DAR MAS | ΔDAR (MAS−single) | Δalpha |
|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 0.364 | 0.253 | -0.111 MAS↓ | 0.618 | 0.802 | +0.184 MAS↑ | -0.002 |
| `qwen2.5:7b-instruct` | 0.293 | 0.449 | +0.156 MAS↑ | 0.719 | 0.647 | -0.072 MAS↓ | +0.177 |
| `qwen2.5:14b-instruct` | 0.248 | 0.221 | -0.027 MAS↓ | 0.893 | 0.914 | +0.021 MAS↑ | -0.042 |
| `gemma4:latest` | 0.552 | 0.297 | -0.255 MAS↓ | 0.594 | 0.705 | +0.110 MAS↑ | +0.018 |
| `qwen2.5:7b-instruct@0.32.6` | 0.299 | 0.456 | +0.157 MAS↑ | 0.715 | 0.661 | -0.054 MAS↓ | +0.171 |
| `qwen3.5:9b@0.32.6` | 0.339 | 0.255 | -0.084 MAS↓ | 0.655 | 0.809 | +0.154 MAS↑ | -0.051 |
| `qwen2.5:14b-instruct@0.32.6` | 0.248 | 0.221 | -0.027 MAS↓ | 0.893 | 0.914 | +0.021 MAS↑ | -0.042 |
| `lfm2.5:8b@think` | 0.491 | 0.344 | -0.147 MAS↓ | 0.434 | 0.421 | -0.013 ≈0 | -0.030 |
| `qwen3.5:9b@think-budget` | 0.548 | 0.264 | -0.284 MAS↓ | 0.631 | 0.724 | +0.093 MAS↑ | -0.135 |
| `granite4.1:8b` | 0.299 | 0.289 | -0.009 ≈0 | 0.830 | 0.845 | +0.015 ≈0 | -0.031 |
| `muse-glimmer:30b` | 0.392 | 0.264 | -0.128 MAS↓ | 0.753 | 0.882 | +0.128 MAS↑ | +0.184 |

Grouping at |Δ| ≥ 0.02: decomposition helps some models' agreement and hurts others', and repeatability moves independently of agreement — no universal direction. (Descriptive deltas; the committed significance tests live in the per-sweep audit scripts.)

### Finding 2 — Dismissal collapse under decomposition (t07, dismiss-labelled cases)

| sweep | single: P(dismiss given dismiss-labelled) | MAS: P(dismiss given dismiss-labelled) | single: P(escalate given escalate-labelled) | MAS: P(escalate given escalate-labelled) |
|---|---|---|---|---|
| `qwen3.5:9b` | 0.197 (390 runs) | 0.051 (390 runs) | 0.440 | 0.240 |
| `qwen2.5:7b-instruct` | 0.190 (390 runs) | 0.515 (390 runs) | 0.129 | 0.102 |
| `qwen2.5:14b-instruct` | 0.036 (390 runs) | 0.005 (390 runs) | 0.196 | 0.164 |
| `gemma4:latest` | 0.456 (390 runs) | 0.003 (390 runs) | 0.724 | 0.778 |
| `qwen2.5:7b-instruct@0.32.6` | 0.203 (390 runs) | 0.508 (390 runs) | 0.120 | 0.093 |
| `qwen3.5:9b@0.32.6` | 0.167 (390 runs) | 0.049 (390 runs) | 0.409 | 0.240 |
| `qwen2.5:14b-instruct@0.32.6` | 0.036 (390 runs) | 0.005 (390 runs) | 0.196 | 0.164 |
| `lfm2.5:8b@think` | 0.482 (390 runs) | 0.197 (390 runs) | 0.489 | 0.520 |
| `qwen3.5:9b@think-budget` | 0.613 (390 runs) | 0.051 (390 runs) | 0.364 | 0.373 |
| `granite4.1:8b` | 0.174 (390 runs) | 0.177 (390 runs) | 0.129 | 0.076 |
| `muse-glimmer:30b` | 0.210 (390 runs) | 0.003 (390 runs) | 0.440 | 0.444 |
| `muse-glimmer:30b@think` | 0.031 (390 runs) | — | 0.596 | — |

### Finding 3 — Degeneracy / mode collapse league table (t07 modal share; cells below best-constant baseline across all 5 conditions)

| sweep | arm | modal decision (t07) | modal share | MV acc (t07) | baseline | conditions below baseline |
|---|---|---|---|---|---|---|
| `qwen2.5:14b-instruct` | mas | investigate | 93.1% | 0.220 | 0.520 | 5/5 |
| `qwen2.5:14b-instruct@0.32.6` | mas | investigate | 93.1% | 0.220 | 0.520 | 5/5 |
| `qwen2.5:14b-instruct` | single | investigate | 90.7% | 0.220 | 0.520 | 5/5 |
| `qwen2.5:14b-instruct@0.32.6` | single | investigate | 90.7% | 0.220 | 0.520 | 5/5 |
| `granite4.1:8b` | mas | investigate | 87.7% | 0.220 | 0.520 | 5/5 |
| `qwen3.5:9b@0.32.6` | mas | investigate | 86.8% | 0.220 | 0.520 | 5/5 |
| `qwen3.5:9b` | mas | investigate | 86.0% | 0.220 | 0.520 | 5/5 |
| `granite4.1:8b` | single | investigate | 85.7% | 0.240 | 0.520 | 5/5 |
| `qwen2.5:7b-instruct` | single | investigate | 81.9% | 0.200 | 0.520 | 5/5 |
| `qwen2.5:7b-instruct@0.32.6` | single | investigate | 81.5% | 0.200 | 0.520 | 5/5 |
| `muse-glimmer:30b` | mas | investigate | 80.8% | 0.240 | 0.520 | 5/5 |
| `qwen3.5:9b@think-budget` | mas | investigate | 76.1% | 0.220 | 0.520 | 5/5 |
| `muse-glimmer:30b` | single | investigate | 72.4% | 0.380 | 0.520 | 5/5 |
| `qwen3.5:9b@0.32.6` | single | investigate | 70.5% | 0.300 | 0.520 | 5/5 |
| `muse-glimmer:30b@think` | single | investigate | 68.9% | 0.320 | 0.520 | 5/5 |
| `qwen3.5:9b` | single | investigate | 68.3% | 0.360 | 0.520 | 5/5 |
| `qwen2.5:7b-instruct@0.32.6` | mas | investigate | 66.9% | 0.560 | 0.520 | 4/5 |
| `qwen2.5:7b-instruct` | mas | investigate | 64.5% | 0.540 | 0.520 | 4/5 |
| `gemma4:latest` | mas | investigate | 54.9% | 0.320 | 0.520 | 5/5 |
| `qwen3.5:9b@think-budget` | single | investigate | 47.7% | 0.640 | 0.520 | 0/5 |
| `lfm2.5:8b@think` | mas | investigate | 46.8% | 0.360 | 0.520 | 5/5 |
| `lfm2.5:8b@think` | single | investigate | 42.7% | 0.680 | 0.520 | 1/5 |
| `gemma4:latest` | single | investigate | 41.6% | 0.600 | 0.520 | 0/5 |

Label prior (primary block): dismiss 26/50, escalate 15/50, investigate 9/50 — a modal-`investigate` share far above the 18% investigate prior is mode collapse, whatever the DAR says.

### Finding 4 — Cache-state (non-)determinism at T=0, fixed seed (byte-identical groups /50; decision-flipping groups /50)

| sweep | arm | t0-fixed byte-identical | t0-fixed decision-flipping | pert-t0 byte-identical | pert-t0 decision-flipping |
|---|---|---|---|---|---|
| `qwen3.5:9b` | single | 50/50 | 0/50 | 10/10 | 0/10 |
| `qwen3.5:9b` | mas | 50/50 | 0/50 | 10/10 | 0/10 |
| `qwen2.5:7b-instruct` | single | 4/50 | 6/50 | 0/10 | 3/10 |
| `qwen2.5:7b-instruct` | mas | 0/50 | 19/50 | 0/10 | 4/10 |
| `qwen2.5:14b-instruct` | single | 2/50 | 4/50 | 1/10 | 1/10 |
| `qwen2.5:14b-instruct` | mas | 0/50 | 3/50 | 0/10 | 1/10 |
| `gemma4:latest` | single | 1/50 | 15/50 | 1/10 | 3/10 |
| `gemma4:latest` | mas | 0/50 | 20/50 | 0/10 | 7/10 |
| `qwen2.5:7b-instruct@0.32.6` | single | 4/50 | 6/50 | 0/10 | 4/10 |
| `qwen2.5:7b-instruct@0.32.6` | mas | 0/50 | 21/50 | 0/10 | 3/10 |
| `qwen3.5:9b@0.32.6` | single | 50/50 | 0/50 | 10/10 | 0/10 |
| `qwen3.5:9b@0.32.6` | mas | 50/50 | 0/50 | 10/10 | 0/10 |
| `qwen2.5:14b-instruct@0.32.6` | single | 2/50 | 4/50 | 1/10 | 1/10 |
| `qwen2.5:14b-instruct@0.32.6` | mas | 0/50 | 3/50 | 0/10 | 1/10 |
| `lfm2.5:8b@think` | single | 50/50 | 0/50 | 10/10 | 0/10 |
| `lfm2.5:8b@think` | mas | 49/50 | 0/50 | 10/10 | 0/10 |
| `qwen3.5:9b@think-budget` | single | 50/50 | 0/50 | 10/10 | 0/10 |
| `qwen3.5:9b@think-budget` | mas | 49/50 | 0/50 | 10/10 | 0/10 |
| `granite4.1:8b` | single | 7/50 | 5/50 | 1/10 | 1/10 |
| `granite4.1:8b` | mas | 12/50 | 14/50 | 3/10 | 4/10 |
| `muse-glimmer:30b` | single | 48/50 | 0/50 | 10/10 | 0/10 |
| `muse-glimmer:30b` | mas | 0/50 | 7/50 | 0/10 | 2/10 |
| `muse-glimmer:30b@think` | single | 49/50 | 1/50 | 10/10 | 0/10 |
| `muse-glimmer:30b@think` | mas | 2/40 | 0/40 | 0/0 | 0/0 |

#### Version-replication deltas (qwen trio, Ollama 0.31.1 → 0.32.6, identical seeds/cases/design)

| model | arm | t07 pass^1 (0.31.1→0.32.6) | t07 DAR | t07 alpha | t0 flipping groups | t0 byte-identical groups |
|---|---|---|---|---|---|---|
| `qwen3.5:9b` | single | 0.364 → 0.339 (-0.025) | 0.618 → 0.655 (+0.038) | 0.205 → 0.241 (+0.037) | 0 → 0 | 50 → 50 |
| `qwen3.5:9b` | mas | 0.253 → 0.255 (+0.001) | 0.802 → 0.809 (+0.007) | 0.203 → 0.191 (-0.012) | 0 → 0 | 50 → 50 |
| `qwen2.5:7b-instruct` | single | 0.293 → 0.299 (+0.005) | 0.719 → 0.715 (-0.003) | 0.102 → 0.106 (+0.004) | 6 → 6 | 4 → 4 |
| `qwen2.5:7b-instruct` | mas | 0.449 → 0.456 (+0.007) | 0.647 → 0.661 (+0.014) | 0.279 → 0.276 (-0.003) | 19 → 21 | 0 → 0 |
| `qwen2.5:14b-instruct` | single | 0.248 → 0.248 (+0.000) | 0.893 → 0.893 (+0.000) | 0.382 → 0.382 (+0.000) | 4 → 4 | 2 → 2 |
| `qwen2.5:14b-instruct` | mas | 0.221 → 0.221 (+0.000) | 0.914 → 0.914 (+0.000) | 0.340 → 0.340 (+0.000) | 3 → 3 | 0 → 0 |

### Finding 5 — Budget starvation / severed channels in the MAS pipeline (per-node dead and empty-output census)

| sweep (MAS arm) | runs | data node call-dead | policy node call-dead | data output EMPTY | policy output empty | reporting output empty | data empty *with* calls (severed channel) |
|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 1150 | 12 (1.0%) | 6 (0.5%) | n/a (v1) | n/a | n/a | n/a |
| `qwen2.5:7b-instruct` | 1150 | 0 (0.0%) | 1 (0.1%) | n/a (v1) | n/a | n/a | n/a |
| `qwen2.5:14b-instruct` | 1150 | 2 (0.2%) | 9 (0.8%) | n/a (v1) | n/a | n/a | n/a |
| `gemma4:latest` | 1150 | 0 (0.0%) | 3 (0.3%) | n/a (v1) | n/a | n/a | n/a |
| `qwen2.5:7b-instruct@0.32.6` | 1150 | 0 (0.0%) | 0 (0.0%) | n/a (v1) | n/a | n/a | n/a |
| `qwen3.5:9b@0.32.6` | 1150 | 11 (1.0%) | 4 (0.3%) | n/a (v1) | n/a | n/a | n/a |
| `qwen2.5:14b-instruct@0.32.6` | 1150 | 2 (0.2%) | 9 (0.8%) | n/a (v1) | n/a | n/a | n/a |
| `lfm2.5:8b@think` | 1150 | 93 (8.1%) | 470 (40.9%) | 20 (1.7%) | 20 | 0 | 19 |
| `deepseek-r1:14b@think` | 1150 | 1150 (100.0%) | 1150 (100.0%) | 0 (0.0%) | 0 | 0 | 0 |
| `qwen3.5:9b@think-budget` | 1150 | 72 (6.3%) | 167 (14.5%) | 6 (0.5%) | 94 | 8 | 5 |
| `granite4.1:8b` | 1150 | 3 (0.3%) | 0 (0.0%) | 0 (0.0%) | 0 | 0 | 0 |
| `muse-glimmer:30b` | 1150 | 16 (1.4%) | 78 (6.8%) | 226 (19.7%) | 0 | 0 | 226 |
| `muse-glimmer:30b@think` | 201 | 0 (0.0%) | 6 (3.0%) | 191 (95.0%) | 0 | 0 | 191 |
| `qwen2.5:7b-instruct@b32` 🔶LIVE | 96 | 0 (0.0%) | 0 (0.0%) | 2 (2.1%) | 2 | 0 | 2 |

- `muse-glimmer:30b` empty-data-node runs decide: {'investigate': 224, 'dismiss': 1, 'escalate': 1} (of which 226 made ≥8 data-tool calls — the per-node iteration-cap-exhaustion signature).
- `muse-glimmer:30b@think` empty-data-node runs decide: {'investigate': 191} (of which 191 made ≥8 data-tool calls — the per-node iteration-cap-exhaustion signature).

v1 journals (contexts 1–2) have no `node_outputs` field, so empty-output detection is only possible for harness-v2 sweeps; call-dead detection (via the tool-name partition) covers everything.

### Finding 6 — Thinking on/off contrasts

**Clean within-model pair (single arm only): `muse-glimmer:30b` off vs ON** — same model, digest, seeds, harness, infra; one wire parameter changed. The MAS @think arm was stopped at 201 (§5) so only the monolith contrast is valid.

| condition | pass^1 off | pass^1 ON | DAR off | DAR ON | alpha off | alpha ON | flip off | flip ON | malformed | tok/run | wall s* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.360 | 0.344 | 1.000 | 0.992 | 1.000 | 0.983 | 0.000 | 0.020 | 0 → 10 | 7,568 → 13,580 | 41 → 59 |
| t07-varied | 0.392 | 0.311 | 0.753 | 0.822 | 0.435 | 0.613 | 0.640 | 0.620 | 1 → 29 | 7,063 → 12,866 | 39 → 45 |

**Confounded qwen3.5 pair** — `qwen3.5:9b` (0.31.1/v1) and `qwen3.5:9b@0.32.6` (0.32.6/v1) vs `qwen3.5:9b@think-budget` (0.32.9/v2, num_predict 8192): FOUR factors differ (think, num_predict, ollama_version, harness revision — CHANGELOG 2026-08-13). No attribution to deliberation is supportable; the table is descriptive only.

| sweep | arm | t07 pass^1 | DAR | alpha | flip | malformed | tok/run |
|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | single | 0.364 | 0.618 | 0.205 | 0.920 | 3 | 4,241 |
| `qwen3.5:9b` | mas | 0.253 | 0.802 | 0.203 | 0.760 | 0 | 7,760 |
| `qwen3.5:9b@0.32.6` | single | 0.339 | 0.655 | 0.241 | 0.900 | 3 | 4,272 |
| `qwen3.5:9b@0.32.6` | mas | 0.255 | 0.809 | 0.191 | 0.800 | 0 | 7,761 |
| `qwen3.5:9b@think-budget` | single | 0.548 | 0.631 | 0.413 | 0.940 | 14 | 9,550 |
| `qwen3.5:9b@think-budget` | mas | 0.264 | 0.724 | 0.277 | 0.880 | 13 | 17,318 |

`lfm2.5:8b@think` and `deepseek-r1:14b@think` have no admissible thinking-off twin by construction — any contrast against the sealed corpus is cross-model.

### Cost ratios (t07-varied means, MAS ÷ single)

| sweep | single tok/run | MAS tok/run | token ratio | single wall s* | MAS wall s* | wall ratio* |
|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 4,241 | 7,760 | 1.83× | 6.5 | 16.3 | 2.50× |
| `qwen2.5:7b-instruct` | 2,074 | 6,458 | 3.11× | 2.6 | 9.4 | 3.65× |
| `qwen2.5:14b-instruct` | 2,128 | 5,903 | 2.77× | 7.5 | 16.4 | 2.19× |
| `gemma4:latest` | 3,931 | 9,491 | 2.41× | 18.7 | 42.9 | 2.29× |
| `qwen2.5:7b-instruct@0.32.6` | 2,086 | 6,469 | 3.10× | 2.7 | 10.0 | 3.73× |
| `qwen3.5:9b@0.32.6` | 4,272 | 7,761 | 1.82× | 6.5 | 18.3 | 2.83× |
| `qwen2.5:14b-instruct@0.32.6` | 2,128 | 5,903 | 2.77× | 7.6 | 16.9 | 2.23× |
| `lfm2.5:8b@think` | 4,332 | 10,029 | 2.32× | 6.7 | 19.4 | 2.91× |
| `qwen3.5:9b@think-budget` | 9,550 | 17,318 | 1.81× | 28.1 | 75.6 | 2.69× |
| `granite4.1:8b` | 4,343 | 8,380 | 1.93× | 4.5 | 11.4 | 2.56× |
| `muse-glimmer:30b` | 7,063 | 17,180 | 2.43× | 38.8 | 84.3 | 2.17× |

*Wall-clock ratios are contention-contaminated (arms co-resident on one GPU in every sweep); token ratios are the reliable cost signal.*

### Tool-channel health census (all journalled sweeps, both arms)

| sweep | arm | runs | zero-tool runs | zero-tool % | mean calls/run | max calls |
|---|---|---|---|---|---|---|
| `qwen3.5:9b` | single | 1150 | 0 | 0.0% | 3.71 | 6 |
| `qwen3.5:9b` | mas | 1150 | 5 | 0.4% | 5.20 | 8 |
| `qwen2.5:7b-instruct` | single | 1150 | 0 | 0.0% | 3.03 | 6 |
| `qwen2.5:7b-instruct` | mas | 1150 | 0 | 0.0% | 11.62 | 671 |
| `qwen2.5:14b-instruct` | single | 1150 | 0 | 0.0% | 3.69 | 12 |
| `qwen2.5:14b-instruct` | mas | 1150 | 1 | 0.1% | 6.36 | 22 |
| `gemma4:latest` | single | 1150 | 7 | 0.6% | 2.05 | 5 |
| `gemma4:latest` | mas | 1150 | 0 | 0.0% | 6.11 | 9 |
| `qwen2.5:7b-instruct@0.32.6` | single | 1150 | 0 | 0.0% | 3.04 | 6 |
| `qwen2.5:7b-instruct@0.32.6` | mas | 1150 | 0 | 0.0% | 11.95 | 438 |
| `qwen3.5:9b@0.32.6` | single | 1150 | 0 | 0.0% | 3.74 | 8 |
| `qwen3.5:9b@0.32.6` | mas | 1150 | 4 | 0.3% | 5.20 | 8 |
| `qwen2.5:14b-instruct@0.32.6` | single | 1150 | 0 | 0.0% | 3.69 | 12 |
| `qwen2.5:14b-instruct@0.32.6` | mas | 1150 | 1 | 0.1% | 6.36 | 22 |
| `lfm2.5:8b@think` | single | 1150 | 97 | 8.4% | 2.77 | 6 |
| `lfm2.5:8b@think` | mas | 1150 | 43 | 3.7% | 5.34 | 11 |
| `deepseek-r1:14b@think` | single | 1150 | 1150 | 100.0% | 0.00 | 0 |
| `deepseek-r1:14b@think` | mas | 1150 | 1150 | 100.0% | 0.00 | 0 |
| `qwen3.5:9b@think-budget` | single | 1150 | 0 | 0.0% | 4.65 | 10 |
| `qwen3.5:9b@think-budget` | mas | 1150 | 26 | 2.3% | 5.01 | 14 |
| `granite4.1:8b` | single | 1150 | 0 | 0.0% | 3.58 | 6 |
| `granite4.1:8b` | mas | 1150 | 0 | 0.0% | 5.35 | 9 |
| `muse-glimmer:30b` | single | 1150 | 1 | 0.1% | 4.09 | 7 |
| `muse-glimmer:30b` | mas | 1150 | 7 | 0.6% | 7.41 | 11 |
| `muse-glimmer:30b@think` | single | 1150 | 3 | 0.3% | 5.69 | 8 |
| `muse-glimmer:30b@think` | mas | 201 | 0 | 0.0% | 8.98 | 10 |
| `qwen2.5:7b-instruct@b32` | single | 491 | 0 | 0.0% | 3.01 | 6 |
| `qwen2.5:7b-instruct@b32` | mas | 96 | 0 | 0.0% | 9.43 | 16 |

## 3. Per-sweep detail (full arm × condition dumps)

### `qwen3.5:9b` — qwen3.5:9b, think off (false), 1 · Ollama 0.31.1, harness v1 — **SEALED**

*headline pre-registered sweep. Arms co-ran (wall clock contaminated): yes (overlap ≈ 2.1 h).*

#### single arm (1150 runs, 2026-08-06T16:28 → 2026-08-06T18:33)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:45 (18.0%) | d:20 (8.0%) | i:185 (74.0%) | m:0 (0.0%) | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 vs 0.520 |
| t07-varied | 750/750 | 0 | e:153 (20.4%) | d:82 (10.9%) | i:512 (68.3%) | m:3 (0.4%) | 0.364 | 0.078 | 0.040 | 0.618 | 0.205 | 0.920 | 0.360 vs 0.520 (2 ties) |
| pert-t0 | 50/50 | 0 | e:15 (30.0%) | d:5 (10.0%) | i:30 (60.0%) | m:0 (0.0%) | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:17 (34.0%) | d:6 (12.0%) | i:27 (54.0%) | m:0 (0.0%) | 0.320 | 0.100 | — | 0.760 | 0.593 | 0.500 | 0.400 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:13 (26.0%) | d:4 (8.0%) | i:32 (64.0%) | m:1 (2.0%) | 0.240 | 0.000 | — | 0.650 | 0.335 | 0.700 | 0.300 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 3,845 | 374 | 4,219 | 6.2 | 3.78 | 4.0 | 6 | 0 |
| t07-varied | 0.409 | 3,848 | 393 | 4,241 | 6.5 | 3.65 | 4.0 | 6 | 0 |
| pert-t0 | 0.000 | 3,644 | 330 | 3,974 | 5.7 | 3.90 | 4.0 | 5 | 0 |
| pert-t05 | 0.205 | 3,803 | 390 | 4,194 | 6.4 | 3.96 | 4.0 | 5 | 0 |
| pert-t10 | 0.310 | 3,667 | 418 | 4,084 | 6.7 | 3.78 | 4.0 | 5 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 50/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 5/10; pert-t05: 6/10; pert-t10: 5/10.

#### mas arm (1150 runs, 2026-08-06T16:28 → 2026-08-06T21:59)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:20 (8.0%) | d:0 (0.0%) | i:230 (92.0%) | m:0 (0.0%) | 0.260 | 0.260 | — | 1.000 | 1.000 | 0.000 | 0.260 vs 0.520 |
| t07-varied | 750/750 | 0 | e:79 (10.5%) | d:26 (3.5%) | i:645 (86.0%) | m:0 (0.0%) | 0.253 | 0.110 | 0.060 | 0.802 | 0.203 | 0.760 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:0 (0.0%) | d:0 (0.0%) | i:50 (100.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 1.000 | 1.000 | 0.000 | 0.000 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:5 (10.0%) | d:2 (4.0%) | i:43 (86.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.760 | 0.055 | 0.500 | 0.000 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:12 (24.0%) | d:0 (0.0%) | i:38 (76.0%) | m:0 (0.0%) | 0.180 | 0.100 | — | 0.740 | 0.302 | 0.600 | 0.100 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 6,089 | 1,413 | 7,501 | 19.7 | 5.18 | 5.0 | 6 | 0 |
| t07-varied | 0.223 | 6,292 | 1,468 | 7,760 | 16.3 | 5.11 | 5.0 | 8 | 5 |
| pert-t0 | 0.000 | 6,271 | 1,538 | 7,809 | 17.0 | 5.80 | 6.0 | 6 | 0 |
| pert-t05 | 0.205 | 6,298 | 1,414 | 7,711 | 16.3 | 5.66 | 6.0 | 7 | 0 |
| pert-t10 | 0.229 | 6,810 | 1,572 | 8,382 | 17.9 | 5.56 | 6.0 | 8 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 50/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 1/10; pert-t05: 0/10; pert-t10: 1/10.
Node health: data call-dead 12, policy call-dead 6; node_outputs not journalled (harness v1).

### `qwen2.5:7b-instruct` — qwen2.5:7b-instruct, think n/a (omit), 1 · Ollama 0.31.1, harness v1 — **SEALED**

*replication; restarted from zero 2026-08-07 (partial archived). Arms co-ran (wall clock contaminated): yes (overlap ≈ 0.9 h).*

#### single arm (1150 runs, 2026-08-06T22:37 → 2026-08-06T23:29)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:12 (4.8%) | d:14 (5.6%) | i:220 (88.0%) | m:4 (1.6%) | 0.244 | 0.220 | — | 0.952 | 0.783 | 0.120 | 0.240 vs 0.520 |
| t07-varied | 750/750 | 0 | e:38 (5.1%) | d:90 (12.0%) | i:614 (81.9%) | m:8 (1.1%) | 0.293 | 0.089 | 0.000 | 0.719 | 0.102 | 0.880 | 0.200 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:0 (0.0%) | d:6 (12.0%) | i:44 (88.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.880 | 0.443 | 0.300 | 0.100 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:2 (4.0%) | d:15 (30.0%) | i:33 (66.0%) | m:0 (0.0%) | 0.120 | 0.000 | — | 0.640 | 0.254 | 0.700 | 0.200 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:2 (4.0%) | d:4 (8.0%) | i:44 (88.0%) | m:0 (0.0%) | 0.060 | 0.000 | — | 0.820 | 0.189 | 0.400 | 0.000 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.043 | 1,888 | 211 | 2,099 | 2.6 | 3.02 | 3.0 | 6 | 0 |
| t07-varied | 0.312 | 1,867 | 207 | 2,074 | 2.6 | 3.01 | 3.0 | 6 | 0 |
| pert-t0 | 0.108 | 1,961 | 216 | 2,177 | 2.7 | 3.12 | 3.0 | 5 | 0 |
| pert-t05 | 0.302 | 1,961 | 219 | 2,180 | 2.8 | 3.10 | 3.0 | 5 | 0 |
| pert-t10 | 0.157 | 2,052 | 235 | 2,287 | 2.9 | 3.14 | 3.0 | 5 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 4/50 groups, decision-flipping 6/50; pert-t0 byte-identical 0/10, flipping 3/10.
Perturbation MV movement: pert-t0: 1/10; pert-t05: 3/10; pert-t10: 0/10.

#### mas arm (1150 runs, 2026-08-06T22:37 → 2026-08-07T01:51)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:5 (2.0%) | d:65 (26.0%) | i:180 (72.0%) | m:0 (0.0%) | 0.380 | 0.200 | — | 0.824 | 0.576 | 0.380 | 0.380 vs 0.520 |
| t07-varied | 750/750 | 0 | e:34 (4.5%) | d:228 (30.4%) | i:484 (64.5%) | m:4 (0.5%) | 0.449 | 0.107 | 0.020 | 0.647 | 0.279 | 0.900 | 0.540 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:1 (2.0%) | d:16 (32.0%) | i:33 (66.0%) | m:0 (0.0%) | 0.100 | 0.100 | — | 0.800 | 0.575 | 0.400 | 0.100 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:1 (2.0%) | d:11 (22.0%) | i:38 (76.0%) | m:0 (0.0%) | 0.060 | 0.000 | — | 0.710 | 0.239 | 0.500 | 0.000 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:1 (2.0%) | d:12 (24.0%) | i:37 (74.0%) | m:0 (0.0%) | 0.120 | 0.000 | — | 0.720 | 0.304 | 0.600 | 0.100 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.152 | 5,070 | 959 | 6,028 | 11.0 | 9.03 | 7.0 | 96 | 0 |
| t07-varied | 0.364 | 5,472 | 986 | 6,458 | 9.4 | 10.99 | 7.0 | 311 | 0 |
| pert-t0 | 0.169 | 4,954 | 921 | 5,876 | 8.7 | 8.80 | 7.0 | 98 | 0 |
| pert-t05 | 0.250 | 7,455 | 1,431 | 8,886 | 13.4 | 28.64 | 7.0 | 671 | 0 |
| pert-t10 | 0.241 | 6,570 | 1,271 | 7,841 | 11.3 | 19.92 | 8.0 | 178 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 19/50; pert-t0 byte-identical 0/10, flipping 4/10.
Perturbation MV movement: pert-t0: 3/10; pert-t05: 2/10; pert-t10: 1/10.
Node health: data call-dead 0, policy call-dead 1; node_outputs not journalled (harness v1).

### `qwen2.5:14b-instruct` — qwen2.5:14b-instruct, think n/a (omit), 1 · Ollama 0.31.1, harness v1 — **SEALED**

*replication. Arms co-ran (wall clock contaminated): yes (overlap ≈ 2.4 h).*

#### single arm (1150 runs, 2026-08-07T02:28 → 2026-08-07T04:49)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:35 (14.0%) | d:5 (2.0%) | i:210 (84.0%) | m:0 (0.0%) | 0.188 | 0.160 | — | 0.968 | 0.884 | 0.080 | 0.180 vs 0.520 |
| t07-varied | 750/750 | 0 | e:54 (7.2%) | d:14 (1.9%) | i:680 (90.7%) | m:2 (0.3%) | 0.248 | 0.149 | 0.060 | 0.893 | 0.382 | 0.460 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:4 (8.0%) | d:0 (0.0%) | i:46 (92.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.960 | 0.734 | 0.100 | 0.100 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:5 (10.0%) | d:0 (0.0%) | i:45 (90.0%) | m:0 (0.0%) | 0.060 | 0.000 | — | 0.840 | 0.129 | 0.300 | 0.000 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:2 (4.0%) | d:2 (4.0%) | i:46 (92.0%) | m:0 (0.0%) | 0.020 | 0.000 | — | 0.880 | 0.218 | 0.200 | 0.000 vs 0.600 (1 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.029 | 1,819 | 318 | 2,138 | 6.6 | 3.72 | 4.0 | 8 | 0 |
| t07-varied | 0.121 | 1,778 | 351 | 2,128 | 7.5 | 3.68 | 4.0 | 12 | 0 |
| pert-t0 | 0.036 | 1,824 | 296 | 2,120 | 6.4 | 3.78 | 4.0 | 5 | 0 |
| pert-t05 | 0.133 | 1,911 | 359 | 2,270 | 7.8 | 3.74 | 4.0 | 8 | 0 |
| pert-t10 | 0.112 | 1,765 | 352 | 2,118 | 7.6 | 3.60 | 3.0 | 6 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 2/50 groups, decision-flipping 4/50; pert-t0 byte-identical 1/10, flipping 1/10.
Perturbation MV movement: pert-t0: 4/10; pert-t05: 1/10; pert-t10: 0/10.

#### mas arm (1150 runs, 2026-08-07T02:28 → 2026-08-07T08:03)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:13 (5.2%) | d:0 (0.0%) | i:237 (94.8%) | m:0 (0.0%) | 0.232 | 0.220 | — | 0.976 | 0.758 | 0.060 | 0.220 vs 0.520 |
| t07-varied | 750/750 | 0 | e:48 (6.4%) | d:2 (0.3%) | i:698 (93.1%) | m:2 (0.3%) | 0.221 | 0.145 | 0.100 | 0.914 | 0.340 | 0.320 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:3 (6.0%) | d:0 (0.0%) | i:47 (94.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 0.940 | 0.479 | 0.100 | 0.000 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:0 (0.0%) | d:1 (2.0%) | i:49 (98.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 0.960 | 0.000 | 0.100 | 0.000 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:1 (2.0%) | d:0 (0.0%) | i:49 (98.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 0.960 | 0.000 | 0.100 | 0.000 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.022 | 4,851 | 982 | 5,833 | 21.4 | 6.16 | 6.0 | 13 | 0 |
| t07-varied | 0.094 | 4,831 | 1,073 | 5,903 | 16.4 | 6.32 | 6.0 | 22 | 1 |
| pert-t0 | 0.049 | 5,088 | 1,012 | 6,100 | 14.3 | 6.94 | 7.0 | 9 | 0 |
| pert-t05 | 0.036 | 5,033 | 1,115 | 6,148 | 15.4 | 6.82 | 7.0 | 12 | 0 |
| pert-t10 | 0.036 | 5,222 | 1,203 | 6,425 | 16.2 | 6.94 | 7.0 | 16 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 3/50; pert-t0 byte-identical 0/10, flipping 1/10.
Perturbation MV movement: pert-t0: 1/10; pert-t05: 0/10; pert-t10: 0/10.
Node health: data call-dead 2, policy call-dead 9; node_outputs not journalled (harness v1).

### `gemma4:latest` — gemma4:latest, think n/a (omit), 2 · Ollama 0.32.6, harness v1 — **SEALED**

*admitted after 0.32.x tool-template fix; aborted partial archived. Arms co-ran (wall clock contaminated): yes (overlap ≈ 6.0 h).*

#### single arm (1150 runs, 2026-08-07T15:46 → 2026-08-07T21:43)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:84 (33.6%) | d:69 (27.6%) | i:97 (38.8%) | m:0 (0.0%) | 0.648 | 0.520 | — | 0.880 | 0.819 | 0.300 | 0.640 vs 0.520 |
| t07-varied | 750/750 | 0 | e:244 (32.5%) | d:184 (24.5%) | i:312 (41.6%) | m:10 (1.3%) | 0.552 | 0.185 | 0.080 | 0.594 | 0.387 | 0.900 | 0.600 vs 0.520 (4 ties) |
| pert-t0 | 50/50 | 0 | e:28 (56.0%) | d:14 (28.0%) | i:8 (16.0%) | m:0 (0.0%) | 0.680 | 0.500 | — | 0.850 | 0.748 | 0.300 | 0.700 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:26 (52.0%) | d:10 (20.0%) | i:14 (28.0%) | m:0 (0.0%) | 0.560 | 0.300 | — | 0.560 | 0.295 | 0.700 | 0.700 vs 0.600 (1 ties) |
| pert-t10 | 50/50 | 0 | e:24 (48.0%) | d:11 (22.0%) | i:12 (24.0%) | m:3 (6.0%) | 0.560 | 0.200 | — | 0.500 | 0.258 | 0.800 | 0.600 vs 0.600 (1 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.108 | 2,290 | 1,373 | 3,663 | 17.4 | 1.86 | 2.0 | 4 | 1 |
| t07-varied | 0.430 | 2,426 | 1,506 | 3,931 | 18.7 | 2.05 | 2.0 | 5 | 6 |
| pert-t0 | 0.141 | 2,724 | 1,561 | 4,286 | 19.5 | 2.30 | 2.0 | 4 | 0 |
| pert-t05 | 0.395 | 2,800 | 1,564 | 4,365 | 19.5 | 2.40 | 2.0 | 4 | 0 |
| pert-t10 | 0.443 | 2,832 | 1,640 | 4,471 | 20.4 | 2.48 | 2.5 | 4 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 1/50 groups, decision-flipping 15/50; pert-t0 byte-identical 1/10, flipping 3/10.
Perturbation MV movement: pert-t0: 9/10; pert-t05: 9/10; pert-t10: 8/10.

#### mas arm (1150 runs, 2026-08-07T15:46 → 2026-08-08T05:56)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:127 (50.8%) | d:0 (0.0%) | i:123 (49.2%) | m:0 (0.0%) | 0.312 | 0.240 | — | 0.804 | 0.609 | 0.400 | 0.300 vs 0.520 |
| t07-varied | 750/750 | 0 | e:337 (44.9%) | d:1 (0.1%) | i:412 (54.9%) | m:0 (0.0%) | 0.297 | 0.113 | 0.040 | 0.705 | 0.406 | 0.840 | 0.320 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:28 (56.0%) | d:0 (0.0%) | i:22 (44.0%) | m:0 (0.0%) | 0.320 | 0.200 | — | 0.660 | 0.324 | 0.700 | 0.300 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:20 (40.0%) | d:0 (0.0%) | i:30 (60.0%) | m:0 (0.0%) | 0.260 | 0.100 | — | 0.720 | 0.428 | 0.500 | 0.300 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:25 (50.0%) | d:0 (0.0%) | i:25 (50.0%) | m:0 (0.0%) | 0.280 | 0.000 | — | 0.600 | 0.216 | 0.800 | 0.300 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.167 | 4,745 | 4,208 | 8,953 | 50.8 | 6.06 | 6.0 | 8 | 0 |
| t07-varied | 0.304 | 5,028 | 4,464 | 9,491 | 42.9 | 6.08 | 6.0 | 9 | 0 |
| pert-t0 | 0.290 | 5,166 | 4,445 | 9,610 | 39.6 | 6.40 | 6.0 | 7 | 0 |
| pert-t05 | 0.230 | 5,118 | 4,502 | 9,619 | 39.9 | 6.42 | 6.0 | 8 | 0 |
| pert-t10 | 0.339 | 5,302 | 4,658 | 9,959 | 41.1 | 6.18 | 6.0 | 8 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 20/50; pert-t0 byte-identical 0/10, flipping 7/10.
Perturbation MV movement: pert-t0: 7/10; pert-t05: 7/10; pert-t10: 7/10.
Node health: data call-dead 0, policy call-dead 3; node_outputs not journalled (harness v1).

### `qwen2.5:7b-instruct@0.32.6` — qwen2.5:7b-instruct, think n/a (omit), 2 · Ollama 0.32.6, harness v1 — **SEALED**

*infra replication of context-1 sweep. Arms co-ran (wall clock contaminated): yes (overlap ≈ 53.3 h).*

#### single arm (1150 runs, 2026-08-08T06:32 → 2026-08-10T11:47)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:12 (4.8%) | d:14 (5.6%) | i:220 (88.0%) | m:4 (1.6%) | 0.244 | 0.220 | — | 0.952 | 0.783 | 0.120 | 0.240 vs 0.520 |
| t07-varied | 750/750 | 0 | e:36 (4.8%) | d:95 (12.7%) | i:611 (81.5%) | m:8 (1.1%) | 0.299 | 0.095 | 0.020 | 0.715 | 0.106 | 0.840 | 0.200 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:0 (0.0%) | d:10 (20.0%) | i:40 (80.0%) | m:0 (0.0%) | 0.020 | 0.000 | — | 0.840 | 0.510 | 0.400 | 0.000 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:3 (6.0%) | d:10 (20.0%) | i:37 (74.0%) | m:0 (0.0%) | 0.120 | 0.000 | — | 0.760 | 0.425 | 0.500 | 0.100 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:1 (2.0%) | d:4 (8.0%) | i:45 (90.0%) | m:0 (0.0%) | 0.020 | 0.000 | — | 0.830 | 0.091 | 0.300 | 0.000 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.043 | 1,888 | 211 | 2,099 | 2.7 | 3.02 | 3.0 | 6 | 0 |
| t07-varied | 0.313 | 1,877 | 209 | 2,086 | 2.7 | 3.03 | 3.0 | 6 | 0 |
| pert-t0 | 0.144 | 1,973 | 224 | 2,197 | 2.9 | 3.12 | 3.0 | 5 | 0 |
| pert-t05 | 0.205 | 1,995 | 212 | 2,207 | 2.8 | 3.14 | 3.0 | 6 | 0 |
| pert-t10 | 0.153 | 1,917 | 230 | 2,147 | 2.9 | 3.10 | 3.0 | 5 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 4/50 groups, decision-flipping 6/50; pert-t0 byte-identical 0/10, flipping 4/10.
Perturbation MV movement: pert-t0: 4/10; pert-t05: 1/10; pert-t10: 1/10.

#### mas arm (1150 runs, 2026-08-08T06:32 → 2026-08-10T14:16)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:5 (2.0%) | d:65 (26.0%) | i:180 (72.0%) | m:0 (0.0%) | 0.380 | 0.200 | — | 0.804 | 0.528 | 0.420 | 0.360 vs 0.520 |
| t07-varied | 750/750 | 0 | e:30 (4.0%) | d:216 (28.8%) | i:502 (66.9%) | m:2 (0.3%) | 0.456 | 0.139 | 0.040 | 0.661 | 0.276 | 0.860 | 0.560 vs 0.520 (1 ties) |
| pert-t0 | 50/50 | 0 | e:0 (0.0%) | d:14 (28.0%) | i:36 (72.0%) | m:0 (0.0%) | 0.120 | 0.100 | — | 0.860 | 0.660 | 0.300 | 0.100 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:1 (2.0%) | d:13 (26.0%) | i:36 (72.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.820 | 0.574 | 0.400 | 0.100 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:0 (0.0%) | d:15 (30.0%) | i:35 (70.0%) | m:0 (0.0%) | 0.160 | 0.100 | — | 0.720 | 0.347 | 0.500 | 0.100 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.169 | 5,125 | 960 | 6,084 | 11.4 | 9.14 | 7.0 | 96 | 0 |
| t07-varied | 0.345 | 5,480 | 989 | 6,469 | 10.0 | 11.40 | 7.0 | 438 | 0 |
| pert-t0 | 0.121 | 6,584 | 1,367 | 7,951 | 12.0 | 28.70 | 8.0 | 114 | 0 |
| pert-t05 | 0.157 | 6,292 | 1,257 | 7,549 | 11.5 | 19.54 | 8.0 | 107 | 0 |
| pert-t10 | 0.230 | 5,600 | 1,017 | 6,618 | 10.1 | 9.88 | 7.0 | 74 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 21/50; pert-t0 byte-identical 0/10, flipping 3/10.
Perturbation MV movement: pert-t0: 2/10; pert-t05: 1/10; pert-t10: 2/10.
Node health: data call-dead 0, policy call-dead 0; node_outputs not journalled (harness v1).

### `qwen3.5:9b@0.32.6` — qwen3.5:9b, think off (false), 2 · Ollama 0.32.6, harness v1 — **SEALED**

*infra replication of headline sweep. Arms co-ran (wall clock contaminated): yes (overlap ≈ 2.1 h).*

#### single arm (1150 runs, 2026-08-10T14:18 → 2026-08-10T16:24)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:35 (14.0%) | d:10 (4.0%) | i:205 (82.0%) | m:0 (0.0%) | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 vs 0.520 |
| t07-varied | 750/750 | 0 | e:152 (20.3%) | d:66 (8.8%) | i:529 (70.5%) | m:3 (0.4%) | 0.339 | 0.079 | 0.040 | 0.655 | 0.241 | 0.900 | 0.300 vs 0.520 (1 ties) |
| pert-t0 | 50/50 | 0 | e:20 (40.0%) | d:0 (0.0%) | i:30 (60.0%) | m:0 (0.0%) | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:15 (30.0%) | d:5 (10.0%) | i:30 (60.0%) | m:0 (0.0%) | 0.280 | 0.100 | — | 0.660 | 0.383 | 0.600 | 0.400 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:15 (30.0%) | d:2 (4.0%) | i:31 (62.0%) | m:2 (4.0%) | 0.240 | 0.100 | — | 0.580 | 0.212 | 0.800 | 0.300 vs 0.600 (1 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 3,983 | 401 | 4,384 | 6.6 | 3.88 | 4.0 | 6 | 0 |
| t07-varied | 0.368 | 3,878 | 393 | 4,272 | 6.5 | 3.67 | 4.0 | 8 | 0 |
| pert-t0 | 0.000 | 3,645 | 354 | 3,999 | 6.0 | 3.90 | 4.0 | 5 | 0 |
| pert-t05 | 0.279 | 3,774 | 390 | 4,164 | 6.4 | 3.94 | 4.0 | 6 | 0 |
| pert-t10 | 0.394 | 3,707 | 418 | 4,125 | 6.6 | 3.80 | 4.0 | 6 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 50/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 4/10; pert-t05: 6/10; pert-t10: 5/10.

#### mas arm (1150 runs, 2026-08-10T14:18 → 2026-08-10T20:14)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:35 (14.0%) | d:5 (2.0%) | i:210 (84.0%) | m:0 (0.0%) | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 vs 0.520 |
| t07-varied | 750/750 | 0 | e:74 (9.9%) | d:25 (3.3%) | i:651 (86.8%) | m:0 (0.0%) | 0.255 | 0.108 | 0.040 | 0.809 | 0.191 | 0.800 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:0 (0.0%) | d:0 (0.0%) | i:50 (100.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 1.000 | 1.000 | 0.000 | 0.000 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:7 (14.0%) | d:1 (2.0%) | i:42 (84.0%) | m:0 (0.0%) | 0.100 | 0.000 | — | 0.770 | 0.179 | 0.400 | 0.100 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:8 (16.0%) | d:2 (4.0%) | i:40 (80.0%) | m:0 (0.0%) | 0.120 | 0.000 | — | 0.740 | 0.234 | 0.600 | 0.100 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 6,076 | 1,416 | 7,492 | 19.5 | 5.18 | 5.0 | 6 | 0 |
| t07-varied | 0.223 | 6,297 | 1,465 | 7,761 | 18.3 | 5.11 | 5.0 | 8 | 4 |
| pert-t0 | 0.000 | 6,180 | 1,436 | 7,616 | 17.3 | 5.80 | 6.0 | 6 | 0 |
| pert-t05 | 0.202 | 6,286 | 1,450 | 7,736 | 17.5 | 5.64 | 6.0 | 7 | 0 |
| pert-t10 | 0.229 | 6,702 | 1,557 | 8,258 | 18.7 | 5.52 | 6.0 | 8 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 50/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 1/10; pert-t05: 1/10; pert-t10: 1/10.
Node health: data call-dead 11, policy call-dead 4; node_outputs not journalled (harness v1).

### `qwen2.5:14b-instruct@0.32.6` — qwen2.5:14b-instruct, think n/a (omit), 2 · Ollama 0.32.6, harness v1 — **SEALED**

*infra replication. Arms co-ran (wall clock contaminated): yes (overlap ≈ 2.4 h).*

#### single arm (1150 runs, 2026-08-10T20:20 → 2026-08-10T22:43)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:35 (14.0%) | d:5 (2.0%) | i:210 (84.0%) | m:0 (0.0%) | 0.188 | 0.160 | — | 0.968 | 0.884 | 0.080 | 0.180 vs 0.520 |
| t07-varied | 750/750 | 0 | e:54 (7.2%) | d:14 (1.9%) | i:680 (90.7%) | m:2 (0.3%) | 0.248 | 0.149 | 0.060 | 0.893 | 0.382 | 0.460 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:4 (8.0%) | d:0 (0.0%) | i:46 (92.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.960 | 0.734 | 0.100 | 0.100 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:5 (10.0%) | d:0 (0.0%) | i:45 (90.0%) | m:0 (0.0%) | 0.060 | 0.000 | — | 0.840 | 0.129 | 0.300 | 0.000 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:2 (4.0%) | d:2 (4.0%) | i:46 (92.0%) | m:0 (0.0%) | 0.020 | 0.000 | — | 0.880 | 0.218 | 0.200 | 0.000 vs 0.600 (1 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.029 | 1,819 | 318 | 2,138 | 6.7 | 3.72 | 4.0 | 8 | 0 |
| t07-varied | 0.121 | 1,778 | 351 | 2,128 | 7.6 | 3.68 | 4.0 | 12 | 0 |
| pert-t0 | 0.036 | 1,824 | 296 | 2,120 | 6.5 | 3.78 | 4.0 | 5 | 0 |
| pert-t05 | 0.133 | 1,911 | 358 | 2,270 | 7.9 | 3.74 | 4.0 | 8 | 0 |
| pert-t10 | 0.112 | 1,765 | 352 | 2,118 | 7.7 | 3.60 | 3.0 | 6 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 2/50 groups, decision-flipping 4/50; pert-t0 byte-identical 1/10, flipping 1/10.
Perturbation MV movement: pert-t0: 4/10; pert-t05: 1/10; pert-t10: 0/10.

#### mas arm (1150 runs, 2026-08-10T20:20 → 2026-08-11T02:04)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:13 (5.2%) | d:0 (0.0%) | i:237 (94.8%) | m:0 (0.0%) | 0.232 | 0.220 | — | 0.976 | 0.758 | 0.060 | 0.220 vs 0.520 |
| t07-varied | 750/750 | 0 | e:48 (6.4%) | d:2 (0.3%) | i:698 (93.1%) | m:2 (0.3%) | 0.221 | 0.145 | 0.100 | 0.914 | 0.340 | 0.320 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:3 (6.0%) | d:0 (0.0%) | i:47 (94.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 0.940 | 0.479 | 0.100 | 0.000 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:0 (0.0%) | d:1 (2.0%) | i:49 (98.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 0.960 | 0.000 | 0.100 | 0.000 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:1 (2.0%) | d:0 (0.0%) | i:49 (98.0%) | m:0 (0.0%) | 0.000 | 0.000 | — | 0.960 | 0.000 | 0.100 | 0.000 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.022 | 4,851 | 982 | 5,833 | 21.9 | 6.16 | 6.0 | 13 | 0 |
| t07-varied | 0.094 | 4,831 | 1,073 | 5,903 | 16.9 | 6.32 | 6.0 | 22 | 1 |
| pert-t0 | 0.049 | 5,088 | 1,012 | 6,100 | 15.0 | 6.94 | 7.0 | 9 | 0 |
| pert-t05 | 0.036 | 5,033 | 1,115 | 6,148 | 16.0 | 6.82 | 7.0 | 12 | 0 |
| pert-t10 | 0.036 | 5,222 | 1,203 | 6,425 | 16.8 | 6.94 | 7.0 | 16 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 3/50; pert-t0 byte-identical 0/10, flipping 1/10.
Perturbation MV movement: pert-t0: 1/10; pert-t05: 0/10; pert-t10: 0/10.
Node health: data call-dead 2, policy call-dead 9; node_outputs not journalled (harness v1).

### `lfm2.5:8b@think` — lfm2.5:8b, think ON, 3 · Ollama 0.32.9, harness v2 — **SEALED**

*thinking track; no admissible thinking-off twin; 0.13% channel contamination. Arms co-ran (wall clock contaminated): yes (overlap ≈ 2.1 h).*

#### single arm (1150 runs, 2026-08-11T23:55 → 2026-08-12T02:04)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:40 (16.0%) | d:95 (38.0%) | i:110 (44.0%) | m:5 (2.0%) | 0.520 | 0.520 | — | 1.000 | 1.000 | 0.000 | 0.520 vs 0.520 |
| t07-varied | 750/750 | 0 | e:168 (22.4%) | d:229 (30.5%) | i:320 (42.7%) | m:33 (4.4%) | 0.491 | 0.065 | 0.020 | 0.434 | 0.159 | 0.980 | 0.680 vs 0.520 (2 ties) |
| pert-t0 | 50/50 | 0 | e:25 (50.0%) | d:15 (30.0%) | i:10 (20.0%) | m:0 (0.0%) | 0.600 | 0.600 | — | 1.000 | 1.000 | 0.000 | 0.600 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:18 (36.0%) | d:21 (42.0%) | i:11 (22.0%) | m:0 (0.0%) | 0.520 | 0.200 | — | 0.550 | 0.317 | 0.800 | 0.500 vs 0.600 (1 ties) |
| pert-t10 | 50/50 | 0 | e:13 (26.0%) | d:22 (44.0%) | i:13 (26.0%) | m:2 (4.0%) | 0.480 | 0.000 | — | 0.370 | 0.078 | 1.000 | 0.700 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 3,225 | 1,536 | 4,762 | 6.6 | 3.12 | 3.5 | 5 | 5 |
| t07-varied | 0.643 | 2,730 | 1,601 | 4,332 | 6.7 | 2.61 | 3.0 | 6 | 79 |
| pert-t0 | 0.000 | 3,487 | 1,459 | 4,947 | 6.4 | 3.10 | 4.0 | 6 | 5 |
| pert-t05 | 0.399 | 3,277 | 1,401 | 4,678 | 6.2 | 3.04 | 3.0 | 5 | 1 |
| pert-t10 | 0.588 | 2,798 | 1,629 | 4,427 | 6.7 | 2.74 | 3.0 | 5 | 7 |

T=0 fixed-seed forensics: t0-fixed byte-identical 50/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 8/10; pert-t05: 6/10; pert-t10: 8/10.

#### mas arm (1150 runs, 2026-08-11T23:55 → 2026-08-12T06:10)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:80 (32.0%) | d:55 (22.0%) | i:100 (40.0%) | m:15 (6.0%) | 0.480 | 0.480 | — | 1.000 | 1.000 | 0.000 | 0.480 vs 0.520 |
| t07-varied | 750/750 | 0 | e:225 (30.0%) | d:94 (12.5%) | i:351 (46.8%) | m:80 (10.7%) | 0.344 | 0.047 | 0.020 | 0.421 | 0.130 | 0.980 | 0.360 vs 0.520 (1 ties) |
| pert-t0 | 50/50 | 0 | e:15 (30.0%) | d:0 (0.0%) | i:35 (70.0%) | m:0 (0.0%) | 0.100 | 0.100 | — | 1.000 | 1.000 | 0.000 | 0.100 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:16 (32.0%) | d:8 (16.0%) | i:21 (42.0%) | m:5 (10.0%) | 0.280 | 0.000 | — | 0.360 | 0.085 | 0.900 | 0.300 vs 0.600 (1 ties) |
| pert-t10 | 50/50 | 0 | e:11 (22.0%) | d:7 (14.0%) | i:28 (56.0%) | m:4 (8.0%) | 0.260 | 0.000 | — | 0.360 | -0.025 | 1.000 | 0.200 vs 0.600 (2 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 5,381 | 4,889 | 10,270 | 19.4 | 5.49 | 6.0 | 11 | 10 |
| t07-varied | 0.691 | 5,218 | 4,811 | 10,029 | 19.4 | 5.34 | 6.0 | 11 | 27 |
| pert-t0 | 0.000 | 4,850 | 4,861 | 9,711 | 19.5 | 5.30 | 5.0 | 7 | 0 |
| pert-t05 | 0.612 | 5,003 | 4,840 | 9,843 | 19.4 | 5.04 | 5.0 | 9 | 2 |
| pert-t10 | 0.611 | 5,147 | 4,994 | 10,141 | 19.9 | 4.86 | 5.0 | 9 | 4 |

T=0 fixed-seed forensics: t0-fixed byte-identical 49/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 6/10; pert-t05: 4/10; pert-t10: 6/10.
Node health: data call-dead 93, policy call-dead 470; empty outputs — orchestrator: 0, data: 20, policy_risk: 20, reporting: 0; severed-channel (empty data WITH calls): 19.

### `deepseek-r1:14b@think` — deepseek-r1:14b, think ON, 3 · Ollama 0.32.9, harness v2 — **SEALED — EXCLUDED**

*tool channel never existed (registry template drops tools); capability-gating negative case. Arms co-ran (wall clock contaminated): yes (overlap ≈ 3.8 h).*

#### single arm (1150 runs, 2026-08-13T07:27 → 2026-08-13T11:17)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:33 (13.2%) | d:141 (56.4%) | i:76 (30.4%) | m:0 (0.0%) | 0.616 | 0.520 | — | 0.928 | 0.875 | 0.180 | 0.620 vs 0.520 |
| t07-varied | 750/750 | 0 | e:92 (12.3%) | d:450 (60.0%) | i:207 (27.6%) | m:1 (0.1%) | 0.628 | 0.377 | 0.300 | 0.684 | 0.425 | 0.700 | 0.640 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:14 (28.0%) | d:35 (70.0%) | i:1 (2.0%) | m:0 (0.0%) | 0.880 | 0.800 | — | 0.960 | 0.909 | 0.100 | 0.900 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:9 (18.0%) | d:32 (64.0%) | i:9 (18.0%) | m:0 (0.0%) | 0.780 | 0.700 | — | 0.900 | 0.814 | 0.200 | 0.800 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:10 (20.0%) | d:32 (64.0%) | i:8 (16.0%) | m:0 (0.0%) | 0.800 | 0.700 | — | 0.880 | 0.776 | 0.200 | 0.800 vs 0.600 (1 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.065 | 430 | 619 | 1,050 | 12.6 | 0.00 | 0.0 | 0 | 250 |
| t07-varied | 0.332 | 430 | 579 | 1,009 | 11.8 | 0.00 | 0.0 | 0 | 750 |
| pert-t0 | 0.036 | 442 | 566 | 1,008 | 11.5 | 0.00 | 0.0 | 0 | 50 |
| pert-t05 | 0.085 | 442 | 547 | 990 | 11.1 | 0.00 | 0.0 | 0 | 50 |
| pert-t10 | 0.112 | 442 | 534 | 976 | 10.9 | 0.00 | 0.0 | 0 | 50 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 9/50; pert-t0 byte-identical 0/10, flipping 1/10.
Perturbation MV movement: pert-t0: 6/10; pert-t05: 8/10; pert-t10: 7/10.

#### mas arm (1150 runs, 2026-08-13T07:27 → 2026-08-13T19:03)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:26 (10.4%) | d:160 (64.0%) | i:64 (25.6%) | m:0 (0.0%) | 0.596 | 0.460 | — | 0.866 | 0.740 | 0.300 | 0.600 vs 0.520 |
| t07-varied | 750/750 | 0 | e:72 (9.6%) | d:465 (62.0%) | i:211 (28.1%) | m:2 (0.3%) | 0.571 | 0.267 | 0.100 | 0.633 | 0.304 | 0.900 | 0.600 vs 0.520 (1 ties) |
| pert-t0 | 50/50 | 0 | e:8 (16.0%) | d:32 (64.0%) | i:10 (20.0%) | m:0 (0.0%) | 0.720 | 0.500 | — | 0.820 | 0.664 | 0.400 | 0.800 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:8 (16.0%) | d:31 (62.0%) | i:11 (22.0%) | m:0 (0.0%) | 0.700 | 0.400 | — | 0.760 | 0.566 | 0.500 | 0.800 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:10 (20.0%) | d:31 (62.0%) | i:9 (18.0%) | m:0 (0.0%) | 0.700 | 0.300 | — | 0.670 | 0.405 | 0.700 | 0.800 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.120 | 2,468 | 2,493 | 4,962 | 52.4 | 0.00 | 0.0 | 0 | 250 |
| t07-varied | 0.402 | 2,537 | 2,504 | 5,042 | 29.7 | 0.00 | 0.0 | 0 | 750 |
| pert-t0 | 0.157 | 2,611 | 2,748 | 5,359 | 32.4 | 0.00 | 0.0 | 0 | 50 |
| pert-t05 | 0.205 | 2,564 | 2,501 | 5,065 | 30.2 | 0.00 | 0.0 | 0 | 50 |
| pert-t10 | 0.298 | 2,582 | 2,474 | 5,056 | 30.0 | 0.00 | 0.0 | 0 | 50 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 15/50; pert-t0 byte-identical 0/10, flipping 4/10.
Perturbation MV movement: pert-t0: 5/10; pert-t05: 5/10; pert-t10: 5/10.
Node health: data call-dead 1150, policy call-dead 1150; empty outputs — orchestrator: 0, data: 0, policy_risk: 0, reporting: 0; severed-channel (empty data WITH calls): 0.

### `qwen3.5:9b@think-budget` — qwen3.5:9b, think ON, 3 · Ollama 0.32.9, harness v2 — **SEALED**

*num_predict 8192 override; 4-factor confound vs sealed qwen3.5 (think, num_predict, ollama, harness). Arms co-ran (wall clock contaminated): yes (overlap ≈ 9.0 h).*

#### single arm (1150 runs, 2026-08-12T06:20 → 2026-08-12T15:21)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:35 (14.0%) | d:85 (34.0%) | i:130 (52.0%) | m:0 (0.0%) | 0.560 | 0.560 | — | 1.000 | 1.000 | 0.000 | 0.560 vs 0.520 |
| t07-varied | 750/750 | 0 | e:118 (15.7%) | d:260 (34.7%) | i:358 (47.7%) | m:14 (1.9%) | 0.548 | 0.177 | 0.020 | 0.631 | 0.413 | 0.940 | 0.640 vs 0.520 (2 ties) |
| pert-t0 | 50/50 | 0 | e:20 (40.0%) | d:10 (20.0%) | i:20 (40.0%) | m:0 (0.0%) | 0.600 | 0.600 | — | 1.000 | 1.000 | 0.000 | 0.600 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:16 (32.0%) | d:15 (30.0%) | i:19 (38.0%) | m:0 (0.0%) | 0.500 | 0.100 | — | 0.530 | 0.305 | 0.800 | 0.700 vs 0.600 (1 ties) |
| pert-t10 | 50/50 | 0 | e:17 (34.0%) | d:14 (28.0%) | i:18 (36.0%) | m:1 (2.0%) | 0.540 | 0.200 | — | 0.590 | 0.406 | 0.700 | 0.600 vs 0.600 (1 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 7,000 | 2,092 | 9,092 | 27.6 | 4.48 | 4.0 | 7 | 0 |
| t07-varied | 0.411 | 7,462 | 2,088 | 9,550 | 28.1 | 4.53 | 4.0 | 10 | 0 |
| pert-t0 | 0.000 | 8,493 | 2,180 | 10,674 | 29.7 | 6.00 | 6.5 | 8 | 0 |
| pert-t05 | 0.411 | 8,127 | 2,139 | 10,266 | 29.3 | 5.34 | 5.0 | 8 | 0 |
| pert-t10 | 0.378 | 7,842 | 2,110 | 9,952 | 28.6 | 5.12 | 5.0 | 9 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 50/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 7/10; pert-t05: 8/10; pert-t10: 9/10.

#### mas arm (1150 runs, 2026-08-12T06:20 → 2026-08-13T07:20)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:50 (20.0%) | d:0 (0.0%) | i:200 (80.0%) | m:0 (0.0%) | 0.260 | 0.260 | — | 1.000 | 1.000 | 0.000 | 0.260 vs 0.520 |
| t07-varied | 750/750 | 10 | e:146 (19.5%) | d:20 (2.7%) | i:571 (76.1%) | m:13 (1.7%) | 0.264 | 0.067 | 0.000 | 0.724 | 0.277 | 0.880 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:15 (30.0%) | d:0 (0.0%) | i:30 (60.0%) | m:5 (10.0%) | 0.200 | 0.200 | — | 1.000 | 1.000 | 0.000 | 0.200 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:15 (30.0%) | d:0 (0.0%) | i:34 (68.0%) | m:1 (2.0%) | 0.180 | 0.100 | — | 0.680 | 0.299 | 0.600 | 0.200 vs 0.600 (1 ties) |
| pert-t10 | 50/50 | 1 | e:11 (22.0%) | d:1 (2.0%) | i:36 (72.0%) | m:2 (4.0%) | 0.120 | 0.000 | — | 0.690 | 0.295 | 0.600 | 0.100 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 8,411 | 6,874 | 15,284 | 87.0 | 4.92 | 5.0 | 10 | 0 |
| t07-varied | 0.308 | 9,346 | 7,972 | 17,318 | 75.6 | 4.85 | 5.0 | 11 | 25 |
| pert-t0 | 0.000 | 8,515 | 8,174 | 16,689 | 71.0 | 5.50 | 6.0 | 7 | 0 |
| pert-t05 | 0.281 | 11,319 | 8,400 | 19,720 | 74.1 | 6.34 | 6.0 | 14 | 0 |
| pert-t10 | 0.289 | 10,827 | 9,136 | 19,963 | 82.2 | 6.00 | 6.0 | 10 | 1 |

T=0 fixed-seed forensics: t0-fixed byte-identical 49/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 5/10; pert-t05: 4/10; pert-t10: 3/10.
Node health: data call-dead 72, policy call-dead 167; empty outputs — orchestrator: 0, data: 6, policy_risk: 94, reporting: 8; severed-channel (empty data WITH calls): 5.

### `granite4.1:8b` — granite4.1:8b, think n/a (omit), 3 · Ollama 0.32.9, harness v2 — **SEALED**

*re-admitted 2026-08-14 as null-result data point w/ degeneracy annotation. Arms co-ran (wall clock contaminated): yes (overlap ≈ 1.5 h).*

#### single arm (1150 runs, 2026-08-13T19:09 → 2026-08-13T20:37)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:13 (5.2%) | d:24 (9.6%) | i:213 (85.2%) | m:0 (0.0%) | 0.288 | 0.220 | — | 0.960 | 0.848 | 0.100 | 0.300 vs 0.520 |
| t07-varied | 750/750 | 0 | e:30 (4.0%) | d:77 (10.3%) | i:643 (85.7%) | m:0 (0.0%) | 0.299 | 0.171 | 0.120 | 0.830 | 0.328 | 0.620 | 0.240 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:0 (0.0%) | d:11 (22.0%) | i:39 (78.0%) | m:0 (0.0%) | 0.200 | 0.200 | — | 0.960 | 0.886 | 0.100 | 0.200 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:4 (8.0%) | d:6 (12.0%) | i:40 (80.0%) | m:0 (0.0%) | 0.120 | 0.000 | — | 0.860 | 0.596 | 0.300 | 0.100 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:5 (10.0%) | d:6 (12.0%) | i:39 (78.0%) | m:0 (0.0%) | 0.160 | 0.000 | — | 0.710 | 0.226 | 0.500 | 0.000 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.036 | 4,120 | 253 | 4,373 | 4.1 | 3.53 | 4.0 | 4 | 0 |
| t07-varied | 0.186 | 4,060 | 284 | 4,343 | 4.5 | 3.47 | 3.0 | 5 | 0 |
| pert-t0 | 0.036 | 5,168 | 303 | 5,471 | 4.9 | 4.40 | 4.0 | 6 | 0 |
| pert-t05 | 0.121 | 4,805 | 328 | 5,133 | 5.1 | 4.08 | 4.0 | 6 | 0 |
| pert-t10 | 0.250 | 4,879 | 348 | 5,227 | 5.4 | 4.14 | 4.0 | 6 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 7/50 groups, decision-flipping 5/50; pert-t0 byte-identical 1/10, flipping 1/10.
Perturbation MV movement: pert-t0: 3/10; pert-t05: 1/10; pert-t10: 0/10.

#### mas arm (1150 runs, 2026-08-13T19:09 → 2026-08-13T22:58)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:5 (2.0%) | d:34 (13.6%) | i:211 (84.4%) | m:0 (0.0%) | 0.336 | 0.220 | — | 0.868 | 0.511 | 0.280 | 0.340 vs 0.520 |
| t07-varied | 750/750 | 0 | e:18 (2.4%) | d:74 (9.9%) | i:658 (87.7%) | m:0 (0.0%) | 0.289 | 0.180 | 0.160 | 0.845 | 0.297 | 0.500 | 0.220 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:1 (2.0%) | d:9 (18.0%) | i:40 (80.0%) | m:0 (0.0%) | 0.040 | 0.000 | — | 0.840 | 0.521 | 0.400 | 0.000 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:2 (4.0%) | d:6 (12.0%) | i:42 (84.0%) | m:0 (0.0%) | 0.040 | 0.000 | — | 0.840 | 0.437 | 0.400 | 0.000 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:1 (2.0%) | d:8 (16.0%) | i:41 (82.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.780 | 0.285 | 0.400 | 0.100 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.114 | 6,672 | 995 | 7,667 | 13.8 | 5.31 | 5.0 | 9 | 0 |
| t07-varied | 0.165 | 7,360 | 1,020 | 8,380 | 11.4 | 5.31 | 5.0 | 8 | 0 |
| pert-t0 | 0.144 | 7,897 | 1,006 | 8,904 | 10.6 | 5.44 | 5.0 | 7 | 0 |
| pert-t05 | 0.144 | 7,724 | 1,046 | 8,769 | 10.9 | 5.62 | 6.0 | 7 | 0 |
| pert-t10 | 0.182 | 7,672 | 1,072 | 8,744 | 11.2 | 5.74 | 6.0 | 7 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 12/50 groups, decision-flipping 14/50; pert-t0 byte-identical 3/10, flipping 4/10.
Perturbation MV movement: pert-t0: 0/10; pert-t05: 1/10; pert-t10: 2/10.
Node health: data call-dead 3, policy call-dead 0; empty outputs — orchestrator: 0, data: 0, policy_risk: 0, reporting: 0; severed-channel (empty data WITH calls): 0.

### `muse-glimmer:30b` — muse-glimmer:30b, think off (false), 3 · Ollama 0.32.9, harness v2 — **SEALED**

*reboot deviation 2026-08-14 (lossless); 19.7% empty MAS data-node outputs. Arms co-ran (wall clock contaminated): yes (overlap ≈ 12.8 h).*

#### single arm (1150 runs, 2026-08-13T23:05 → 2026-08-14T11:52)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:40 (16.0%) | d:25 (10.0%) | i:185 (74.0%) | m:0 (0.0%) | 0.360 | 0.360 | — | 1.000 | 1.000 | 0.000 | 0.360 vs 0.520 |
| t07-varied | 750/750 | 1 | e:124 (16.5%) | d:82 (10.9%) | i:543 (72.4%) | m:1 (0.1%) | 0.392 | 0.175 | 0.140 | 0.753 | 0.435 | 0.640 | 0.380 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:20 (40.0%) | d:5 (10.0%) | i:25 (50.0%) | m:0 (0.0%) | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:16 (32.0%) | d:7 (14.0%) | i:27 (54.0%) | m:0 (0.0%) | 0.380 | 0.100 | — | 0.620 | 0.365 | 0.700 | 0.300 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:19 (38.0%) | d:6 (12.0%) | i:25 (50.0%) | m:0 (0.0%) | 0.420 | 0.100 | — | 0.580 | 0.304 | 0.700 | 0.400 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 6,542 | 1,027 | 7,568 | 40.9 | 4.16 | 4.0 | 6 | 0 |
| t07-varied | 0.250 | 6,081 | 982 | 7,063 | 38.8 | 3.97 | 4.0 | 7 | 1 |
| pert-t0 | 0.000 | 7,240 | 1,037 | 8,276 | 41.7 | 4.50 | 5.0 | 5 | 0 |
| pert-t05 | 0.315 | 6,908 | 1,003 | 7,911 | 40.2 | 4.54 | 5.0 | 6 | 0 |
| pert-t10 | 0.367 | 6,695 | 1,035 | 7,729 | 41.2 | 4.62 | 5.0 | 7 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 48/50 groups, decision-flipping 0/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 7/10; pert-t05: 5/10; pert-t10: 5/10.

#### mas arm (1150 runs, 2026-08-13T23:05 → 2026-08-15T06:07)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:44 (17.6%) | d:0 (0.0%) | i:206 (82.4%) | m:0 (0.0%) | 0.292 | 0.200 | — | 0.936 | 0.780 | 0.140 | 0.320 vs 0.520 |
| t07-varied | 750/750 | 0 | e:143 (19.1%) | d:1 (0.1%) | i:606 (80.8%) | m:0 (0.0%) | 0.264 | 0.153 | 0.100 | 0.882 | 0.619 | 0.340 | 0.240 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:8 (16.0%) | d:0 (0.0%) | i:42 (84.0%) | m:0 (0.0%) | 0.120 | 0.100 | — | 0.900 | 0.635 | 0.200 | 0.100 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:9 (18.0%) | d:2 (4.0%) | i:39 (78.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.740 | 0.287 | 0.600 | 0.100 vs 0.600 |
| pert-t10 | 50/50 | 0 | e:9 (18.0%) | d:1 (2.0%) | i:40 (80.0%) | m:0 (0.0%) | 0.080 | 0.000 | — | 0.860 | 0.581 | 0.200 | 0.100 vs 0.600 (1 ties) |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.056 | 13,779 | 3,726 | 17,505 | 138.6 | 7.74 | 8.0 | 11 | 0 |
| t07-varied | 0.121 | 13,469 | 3,711 | 17,180 | 84.3 | 7.32 | 8.0 | 11 | 5 |
| pert-t0 | 0.085 | 13,805 | 3,834 | 17,639 | 80.0 | 7.48 | 8.0 | 9 | 0 |
| pert-t05 | 0.229 | 13,581 | 4,082 | 17,663 | 84.7 | 7.56 | 8.0 | 10 | 0 |
| pert-t10 | 0.125 | 13,312 | 3,955 | 17,268 | 82.3 | 6.88 | 7.0 | 10 | 2 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/50 groups, decision-flipping 7/50; pert-t0 byte-identical 0/10, flipping 2/10.
Perturbation MV movement: pert-t0: 2/10; pert-t05: 2/10; pert-t10: 2/10.
Node health: data call-dead 16, policy call-dead 78; empty outputs — orchestrator: 0, data: 226, policy_risk: 0, reporting: 0; severed-channel (empty data WITH calls): 226.

### `muse-glimmer:30b@think` — muse-glimmer:30b, think ON, 3 · Ollama 0.32.9, harness v2 — **CLOSED — single-arm-only**

*MAS arm STOPPED at 201/1150 (95% data-node cap exhaustion) and capability-gated out; single arm complete and valid. Arms co-ran (wall clock contaminated): yes (overlap ≈ 61.9 h).*

#### single arm (1150 runs, 2026-08-15T06:32 → 2026-08-18T01:27)

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:70 (28.0%) | d:1 (0.4%) | i:169 (67.6%) | m:10 (4.0%) | 0.344 | 0.340 | — | 0.992 | 0.983 | 0.020 | 0.340 vs 0.520 |
| t07-varied | 750/750 | 3 | e:192 (25.6%) | d:12 (1.6%) | i:517 (68.9%) | m:29 (3.9%) | 0.311 | 0.205 | 0.160 | 0.822 | 0.613 | 0.620 | 0.320 vs 0.520 |
| pert-t0 | 50/50 | 0 | e:20 (40.0%) | d:0 (0.0%) | i:25 (50.0%) | m:5 (10.0%) | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 vs 0.600 |
| pert-t05 | 50/50 | 0 | e:19 (38.0%) | d:1 (2.0%) | i:25 (50.0%) | m:5 (10.0%) | 0.300 | 0.100 | — | 0.700 | 0.506 | 0.600 | 0.400 vs 0.600 (1 ties) |
| pert-t10 | 50/50 | 0 | e:22 (44.0%) | d:0 (0.0%) | i:25 (50.0%) | m:3 (6.0%) | 0.340 | 0.100 | — | 0.740 | 0.539 | 0.600 | 0.400 vs 0.600 |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.007 | 12,098 | 1,482 | 13,580 | 58.8 | 5.78 | 6.0 | 8 | 0 |
| t07-varied | 0.201 | 11,438 | 1,429 | 12,866 | 44.7 | 5.53 | 6.0 | 8 | 3 |
| pert-t0 | 0.000 | 13,605 | 1,684 | 15,289 | 37.6 | 6.20 | 6.0 | 8 | 0 |
| pert-t05 | 0.269 | 14,236 | 1,763 | 15,998 | 39.8 | 6.46 | 7.0 | 8 | 0 |
| pert-t10 | 0.229 | 13,540 | 1,712 | 15,252 | 38.3 | 6.32 | 6.0 | 8 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 49/50 groups, decision-flipping 1/50; pert-t0 byte-identical 10/10, flipping 0/10.
Perturbation MV movement: pert-t0: 4/10; pert-t05: 5/10; pert-t10: 5/10.

#### mas arm (201 runs, 2026-08-15T06:32 → 2026-08-17T20:23) — ⛔STOPPED at 201/1150, capability-gated out

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 201/250 | 0 | e:1 (0.5%) | d:0 (0.0%) | i:200 (99.5%) | m:0 (0.0%) | 0.195 | 0.175 | — | 1.000 | 1.000 | 0.000 | 0.195 vs 0.512 |
| t07-varied | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t0 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t05 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t10 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.000 | 20,983 | 4,785 | 25,767 | 178.5 | 8.98 | 9 | 10 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 2/40 groups, decision-flipping 0/40; pert-t0 byte-identical 0/0, flipping 0/0.
Perturbation MV movement: pert-t0: 0/0; pert-t05: 0/0; pert-t10: 0/0.
Node health: data call-dead 0, policy call-dead 6; empty outputs — orchestrator: 0, data: 191, policy_risk: 0, reporting: 0; severed-channel (empty data WITH calls): 191.

### `qwen2.5:7b-instruct@b32` — qwen2.5:7b-instruct, think n/a (omit), b32 · Ollama 0.32.9, harness v2b — **LIVE**

*budget track sweep 1/6 — IN FLIGHT, all numbers partial. Arms co-ran (wall clock contaminated): yes (overlap ≈ 0.6 h).*

#### single arm (491 runs, 2026-08-18T09:57 → 2026-08-18T10:30) — 🔶LIVE/PARTIAL

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 250/250 | 0 | e:18 (7.2%) | d:37 (14.8%) | i:188 (75.2%) | m:7 (2.8%) | 0.320 | 0.240 | — | 0.876 | 0.696 | 0.280 | 0.300 vs 0.520 |
| t07-varied | 241/750 | 0 | e:24 (10.0%) | d:43 (17.8%) | i:168 (69.7%) | m:6 (2.5%) | 0.325 | 0.061 | 0.000 | 0.640 | 0.243 | 0.875 | 0.235 vs 0.529 |
| pert-t0 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t05 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t10 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.109 | 2,026 | 190 | 2,216 | 3.3 | 2.95 | 3.0 | 6 | 0 |
| t07-varied | 0.408 | 2,040 | 212 | 2,252 | 4.7 | 3.08 | 3 | 6 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 9/50 groups, decision-flipping 14/50; pert-t0 byte-identical 0/0, flipping 0/0.
Perturbation MV movement: pert-t0: 0/0; pert-t05: 0/0; pert-t10: 0/0.

#### mas arm (96 runs, 2026-08-18T09:57 → 2026-08-18T10:30) — 🔶LIVE/PARTIAL

| condition | runs | err | escalate | dismiss | investigate | malformed | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc vs base |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 96/250 | 0 | e:16 (16.7%) | d:43 (44.8%) | i:37 (38.5%) | m:0 (0.0%) | 0.570 | 0.368 | — | 0.832 | 0.733 | 0.368 | 0.600 vs 0.550 |
| t07-varied | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t0 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t05 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |
| pert-t10 | 0 | — | — | — | — | — | — | — | — | — | — | — | — |

| condition | entropy | prompt tok/run | compl tok/run | total tok/run | wall s* | tools mean | tools med | tools max | zero-tool |
|---|---|---|---|---|---|---|---|---|---|
| t0-fixed | 0.146 | 7,288 | 1,156 | 8,444 | 20.6 | 9.43 | 9.0 | 16 | 0 |

T=0 fixed-seed forensics: t0-fixed byte-identical 0/19 groups, decision-flipping 7/19; pert-t0 byte-identical 0/0, flipping 0/0.
Perturbation MV movement: pert-t0: 0/0; pert-t05: 0/0; pert-t10: 0/0.
Node health: data call-dead 0, policy call-dead 0; empty outputs — orchestrator: 0, data: 2, policy_risk: 2, reporting: 0; severed-channel (empty data WITH calls): 2.

## 4. Budget-sensitivity track v2b — status (🔶 LIVE, all numbers partial)

Launched 2026-08-18 (owner GO). Iteration budgets equalised and disclosed: single 32; MAS orchestrator/data/policy_risk/reporting = 4/16/8/4 (pooled 32). Six sweeps queued; muse-glimmer pair queued after. Journals are being appended while this report generates — counts below are a snapshot.

| registry key | status | single runs | MAS runs | sweep progress | note |
|---|---|---|---|---|---|
| `qwen2.5:7b-instruct@b32` | LIVE | 491/1150 | 96/1150 | 25.5% | budget track sweep 1/6 — IN FLIGHT, all numbers partial |
| `granite4.1:8b@b32` | QUEUED | 0/1150 | 0/1150 | 0.0% | budget track sweep 2/6 |
| `qwen3.5:9b@b32` | QUEUED | 0/1150 | 0/1150 | 0.0% | budget track sweep 3/6 |
| `lfm2.5:8b@b32-think` | QUEUED | 0/1150 | 0/1150 | 0.0% | budget track sweep 4/6 |
| `qwen3.5:9b@b32-think-budget` | QUEUED | 0/1150 | 0/1150 | 0.0% | budget track sweep 5/6; num_predict 8192 (pre-declared confound) |
| `gemma4:latest@b32` | QUEUED | 0/1150 | 0/1150 | 0.0% | budget track sweep 6/6 |

### 🚨 LIVE DEFECT FOUND DURING THIS RECOMPUTATION — duplicate writers on `results-budget-qwen2.5-7b`

- **single**: 783 journal lines but only 491 unique run keys — **292 duplicate-key lines**, first duplicate at 2026-08-18T10:08:04Z; in **69** duplicated keys the two copies decide DIFFERENTLY despite identical seed/temperature (T=0 fixed-seed included).
- **mas**: 146 journal lines but only 96 unique run keys — **50 duplicate-key lines**, first duplicate at 2026-08-18T10:08:04Z; in **10** duplicated keys the two copies decide DIFFERENTLY despite identical seed/temperature (T=0 fixed-seed included).

Attribution (from logs, read-only): the first runner pair launched at 09:57:37Z; `budget-track-queue.log` then launched a SECOND pair at 10:07:58Z ("manifest exists — reusing"), and `runner-single.log` shows the second banner `planned=1150 completed=194 todo=956` at 10:08:03Z while the first pair was still appending. Since then two runners per arm share one journal and one Ollama server, re-running the same planned keys interleaved. Consequences: journal unique-run-key discipline is violated from key ~195 onward; T=0 cache-state semantics are destroyed (two concurrent streams interleave each other's KV/cache states — the duplicated fixed-seed runs already disagree); wall clock is double-contended. **This sweep cannot seal as a valid v2b measurement in its current form.** All figures for this sweep in this report use the FIRST occurrence of each run key and are indicative only.

### `qwen2.5:7b-instruct@b32` partial snapshot vs its sealed v2 counterpart `qwen2.5:7b-instruct` (0.31.1) — indicative only

- **single** 491 runs so far: e:42 (8.6%) / d:80 (16.3%) / i:356 (72.5%) / m:13 (2.6%); zero-tool 0.
- **mas** 96 runs so far: e:16 (16.7%) / d:43 (44.8%) / i:37 (38.5%) / m:0 (0.0%); zero-tool 0.
- single t0-fixed (complete groups only): byte-identical 9/50, flipping 14/50; pass^1 0.320 (sealed v2 counterpart: 0.244).

## 5. Excluded and closed arms — the evidence numbers

### `deepseek-r1:14b@think` — EXCLUDED (infra-invalid: tool channel never existed)

- **single**: 1150 runs, zero-tool 1150/1150 (100.0%); decisions e:158 (13.7%) / d:690 (60.0%) / i:301 (26.2%) / m:1 (0.1%).
- **mas**: 1150 runs, zero-tool 1150/1150 (100.0%); decisions e:124 (10.8%) / d:719 (62.5%) / i:305 (26.5%) / m:2 (0.2%).

Root cause (CHANGELOG 2026-08-14): the Ollama registry template (no `.Tools` block) silently drops tool definitions while `/api/show` reports the model tools-capable; the MAS data node asserted tool-derived facts in every run without any retrieval. Retained as a capability-gating negative case only. Tier-1 numbers for this sweep appear in §3 for the record but enter no comparison.

### `muse-glimmer:30b@think` MAS arm — CLOSED at 201/1150 (capability-gated out 2026-08-17)

- Decisions at stop: e:1 (0.5%) / d:0 (0.0%) / i:200 (99.5%) / m:0 (0.0%).
- Empty data-node outputs: 191/201 (95.0%); of the empty-data runs, 191 made ≥8 data-tool calls (per-node iteration-cap exhaustion, the mechanism established in `docs/EMPTY-NODE-VERDICT.md`).
- Empty-data runs' decisions: {'investigate': 191}.
- With zero decision variance the arm measures a starved pipeline, not decomposition: DAR trivially ≈1, alpha undefined/degenerate. The 201 runs are retained as evidence; the single arm completed and remains valid (§3).

## 6. Data-quality appendix — per-sweep integrity notes

| sweep | arm | rows | torn | dup ids | missing vs plan | unexpected ids | errors | malformed | ollama | digest(12) | num_predict | think | gaps >600s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 4 | 0.31.1 | 6488c96fa5fa | None | False | 0 |
| `qwen3.5:9b` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 0 | 0.31.1 | 6488c96fa5fa | None | False | 0 |
| `qwen2.5:7b-instruct` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 12 | 0.31.1 | 845dbda0ea48 | None | None | 0 |
| `qwen2.5:7b-instruct` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 4 | 0.31.1 | 845dbda0ea48 | None | None | 0 |
| `qwen2.5:14b-instruct` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 2 | 0.31.1 | 7cdf5a0187d5 | None | None | 0 |
| `qwen2.5:14b-instruct` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 2 | 0.31.1 | 7cdf5a0187d5 | None | None | 0 |
| `gemma4:latest` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 13 | 0.32.6 | c6eb396dbd59 | None | None | 0 |
| `gemma4:latest` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 0 | 0.32.6 | c6eb396dbd59 | None | None | 0 |
| `qwen2.5:7b-instruct@0.32.6` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 12 | 0.32.6 | 845dbda0ea48 | None | None | 1 |
| `qwen2.5:7b-instruct@0.32.6` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 2 | 0.32.6 | 845dbda0ea48 | None | None | 1 |
| `qwen3.5:9b@0.32.6` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 5 | 0.32.6 | 6488c96fa5fa | None | False | 0 |
| `qwen3.5:9b@0.32.6` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 0 | 0.32.6 | 6488c96fa5fa | None | False | 0 |
| `qwen2.5:14b-instruct@0.32.6` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 2 | 0.32.6 | 7cdf5a0187d5 | None | None | 0 |
| `qwen2.5:14b-instruct@0.32.6` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 2 | 0.32.6 | 7cdf5a0187d5 | None | None | 0 |
| `lfm2.5:8b@think` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 40 | 0.32.9 | 9cf756159fc2 | None | True | 0 |
| `lfm2.5:8b@think` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 104 | 0.32.9 | 9cf756159fc2 | None | True | 0 |
| `deepseek-r1:14b@think` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 1 | 0.32.9 | c333b7232bdb | 2048 | True | 0 |
| `deepseek-r1:14b@think` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 2 | 0.32.9 | c333b7232bdb | 2048 | True | 1 |
| `qwen3.5:9b@think-budget` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 15 | 0.32.9 | 6488c96fa5fa | 8192 | True | 0 |
| `qwen3.5:9b@think-budget` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 11 | 21 | 0.32.9 | 6488c96fa5fa | 8192 | True | 0 |
| `granite4.1:8b` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 0 | 0.32.9 | 444af1c4b2fe | 2048 | None | 0 |
| `granite4.1:8b` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 0 | 0.32.9 | 444af1c4b2fe | 2048 | None | 0 |
| `muse-glimmer:30b` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 1 | 1 | 0.32.9 | de878ce33ad8 | 2048 | False | 0 |
| `muse-glimmer:30b` | mas | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 0 | 0 | 0.32.9 | de878ce33ad8 | 2048 | False | 1 |
| `muse-glimmer:30b@think` | single | 1150 (1150 uniq) | 0 | 0 | 0 | 0 | 3 | 52 | 0.32.9 | de878ce33ad8 | 2048 | True | 1 |
| `muse-glimmer:30b@think` | mas | 201 (201 uniq) | 0 | 0 | 949 | 0 | 0 | 0 | 0.32.9 | de878ce33ad8 | 2048 | True | 1 |
| `qwen2.5:7b-instruct@b32` | single | 783 (491 uniq) | 0 | 292 | 659 | 0 | 0 | 13 | 0.32.9 | 845dbda0ea48 | 2048 | None | 0 |
| `qwen2.5:7b-instruct@b32` | mas | 146 (96 uniq) | 0 | 50 | 1054 | 0 | 0 | 0 | 0.32.9 | 845dbda0ea48 | 2048 | None | 0 |

Notes: v1 journals lack `num_predict`/`cache_policy`/`node_outputs` fields (shown as `None`); 'missing vs plan' > 0 is expected only for LIVE/CLOSED arms. Non-zero 'dup ids' = the live duplicate-writer defect (§4) — every sealed sweep has zero duplicates. Gap and error details:

- `qwen2.5:7b-instruct@0.32.6` / single: gaps: 188,477s before `single:TXN-2025-046:t07-varied:13`
- `qwen2.5:7b-instruct@0.32.6` / mas: gaps: 188,478s before `mas:TXN-2025-046:t0-fixed:1`
- `deepseek-r1:14b@think` / mas: gaps: 1,560s before `mas:TXN-2025-039:t07-varied:3`
- `qwen3.5:9b@think-budget` / mas: errors: 10× 'ResponseError: EOF (status code: -1)'; 1× 'ResponseError: expected element type <function> but have <parameter> ('
- `muse-glimmer:30b` / single: errors: 1× 'ResponseError: parse Glimmer call to calculate_risk_score: unterminate'
- `muse-glimmer:30b` / mas: gaps: 917s before `mas:TXN-2025-027:t07-varied:13`
- `muse-glimmer:30b@think` / single: gaps: 186,694s before `single:TXN-2025-010:t0-fixed:0` | errors: 3× 'ResponseError: parse Glimmer call to calculate_risk_score: unterminate'
- `muse-glimmer:30b@think` / mas: gaps: 186,931s before `mas:TXN-2025-003:t0-fixed:3`

Known/declared deviations reconciled against the CHANGELOG: qwen2.5:7b restart-from-zero (archived partial, 2026-08-07); gemma4 aborted partial (2026-08-07); muse-glimmer:30b MAS reboot at 653/1150 (2026-08-14, audited lossless, plus one undeclared ~458 s dual-arm stall found by audit); muse-glimmer @think pair killed 45 min after launch and resumed after a 2-day gap (2026-08-17). All of these surface as journal gaps above and none removed or altered runs.

**Convention discrepancy found during this recomputation:** `analysis/seal_checks.py` line 44 hardcodes `OUTCOMES = ("escalate", "investigate", "dismiss", "malformed")` while the locked canonical order in `experiments/config.py` (used by `analysis/metrics.py:majority_vote`, the convention the 2026-08-17 correction re-asserted) is `("escalate", "dismiss", "investigate", "malformed")`. The two orders resolve dismiss-vs-investigate majority ties differently. This report uses the canonical `config.OUTCOMES` order throughout.

### Committed-docs verification (recomputed vs published)

| source | claim | committed | recomputed | verdict |
|---|---|---|---|---|
| cross-model-comparison.md | qwen3.5 single t0 pass^1 | 0.4 | 0.400 | ✅ |
| cross-model-comparison.md | qwen3.5 single t07 pass^1 | 0.364 | 0.364 | ✅ |
| cross-model-comparison.md | qwen3.5 MAS t07 DAR | 0.802 | 0.802 | ✅ |
| cross-model-comparison.md | gemma4 single t0 pass^1 | 0.648 | 0.648 | ✅ |
| cross-model-comparison.md | gemma4 single t07 pass^1 | 0.552 | 0.552 | ✅ |
| cross-model-comparison.md | qwen2.5-7b MAS t07 pass^1 | 0.449 | 0.449 | ✅ |
| cross-model-comparison.md | qwen2.5-14b MAS t07 DAR | 0.914 | 0.914 | ✅ |
| cross-model-comparison.md | qwen2.5-7b@0.32.6 MAS t0 DAR | 0.804 | 0.804 | ✅ |
| cross-model-comparison.md | qwen2.5-7b MAS t0 alpha | 0.576 | 0.576 | ✅ |
| FINAL-RESULTS.md | qwen2.5-7b t07 single tok/run | 2074 | 2074 | ✅ |
| FINAL-RESULTS.md | qwen2.5-7b t07 MAS tok/run | 6458 | 6458 | ✅ |
| FINAL-RESULTS.md | qwen2.5-14b t07 MAS tok/run | 5903 | 5903 | ✅ |
| FINAL-RESULTS.md | gemma4 t07 MAS tok/run | 9491 | 9491 | ✅ |
| FINAL-RESULTS.md | token ratio qwen2.5-7b | 3.11 | 3.114 | ✅ |
| FINAL-RESULTS.md | token ratio qwen3.5 | 1.83 | 1.829 | ✅ |
| FINAL-RESULTS.md / INSIGHTS | qwen3.5-MAS t07 modal investigate share | 86.0% | 86.0% | ✅ |
| FINAL-RESULTS.md / INSIGHTS | qwen2.5-14b-MAS t07 modal investigate share | 93.1% | 93.1% | ✅ |
| FINAL-RESULTS.md / INSIGHTS | qwen3.5-MAS t07 MV matches label (cases/50) | 11 | 11 | ✅ |
| FINAL-RESULTS.md | qwen2.5-14b-MAS pert MV moved (pert-t05) | 0 | 0 | ✅ |
| FINAL-RESULTS.md | qwen2.5-14b-MAS pert MV moved (pert-t10) | 0 | 0 | ✅ |
| FINAL-RESULTS.md | qwen3.5 t0 flips (both arms, both versions) | 0 | 0 | ✅ |
| dissertation-v3.tex:779 | qwen2.5-7b flipped 25/100 primary case-groups | 25 | 25 | ✅ |
| dissertation-v3.tex:779 | qwen2.5-14b flipped 7 primary case-groups | 7 | 7 | ✅ |
| dissertation-v3.tex:779 | gemma4 35 flipping case-groups (primary) | 35 | 35 | ✅ |
| dissertation/FINAL-RESULTS | gemma4 45 flips incl. perturbation block | 45 | 45 | ✅ |
| FINAL-RESULTS.md:105 | qwen2.5-7b '~96% of case-groups byte-diverge' | 96 | 96 | ✅ |
| SUPERVISOR-PACK.md:59 | gemma4 99/100 byte-divergent groups | 99 | 99 | ✅ |
| FINAL-RESULTS.md:105 | qwen2.5-7b '23–27 decision flips' (low end, 23) | 23 | 25 | ❌ MISMATCH |
| SUPERVISOR-PACK.md:89 / dissertation:779 | qwen2.5-14b byte-divergent '105/110' (primary both arms = /100) | 105 | 98 | ❌ MISMATCH |
| ANALYSIS-INSIGHTS.md:43 | 'gemma4-single … 35 flipping groups' as a SINGLE-arm number | 35 | 15 | ❌ MISMATCH |
| CHANGELOG 2026-08-17 | muse off: empty MAS data-node outputs | 226 | 226 | ✅ |
| CHANGELOG 2026-08-17 | muse off: MAS data node call-dead | 16 | 16 | ✅ |
| CHANGELOG 2026-08-17 | muse off: MAS policy node call-dead | 78 | 78 | ✅ |
| CHANGELOG 2026-08-17 (corrected) | muse off: MAS pert-t10 MV acc | 0.1 | 0.100 | ✅ |
| CHANGELOG 2026-08-13 | qwen3.5@think-budget single t07 pass^1 | 0.548 | 0.548 | ✅ |
| CHANGELOG 2026-08-13 | qwen3.5@think-budget MAS t07 pass^1 | 0.264 | 0.264 | ✅ |
| CHANGELOG 2026-08-13 | qwen3.5@think-budget single t07 DAR | 0.631 | 0.631 | ✅ |
| CHANGELOG 2026-08-13 | qwen3.5@think-budget MAS t07 DAR | 0.724 | 0.724 | ✅ |
| CHANGELOG 2026-08-13 | qwen3.5@think-budget MAS t07 investigate runs | 571 | 571 | ✅ |
| CHANGELOG 2026-08-13 | qwen3.5@think-budget MAS tok/run (t07) | 17318 | 17318 | ✅ |
| CHANGELOG 2026-08-12 | lfm2.5@think malformed total | 144 | 144 | ✅ |
| CHANGELOG 2026-08-12 | lfm2.5@think single t07 pass^1 | 0.491 | 0.491 | ✅ |
| CHANGELOG 2026-08-12 | lfm2.5@think MAS t07 MV acc (canonical) | 0.36 | 0.360 | ✅ |
| CHANGELOG 2026-08-14 | deepseek zero-tool runs (of 2300) | 2300 | 2300 | ✅ |
| CHANGELOG 2026-08-17 | muse@think MAS runs at stop | 201 | 201 | ✅ |
| CHANGELOG 2026-08-15 (seal) | muse off: single zero-tool runs | 1 | 1 | ✅ |
| CHANGELOG 2026-08-15 (seal) | muse off: MAS zero-tool runs | 7 | 7 | ✅ |
| FINAL-RESULTS.md | gemma4 MAS dismissals on dismiss-labelled t07 runs (of 390) | 1 | 1 | ✅ |
| FINAL-RESULTS.md | gemma4 single dismissals on dismiss-labelled t07 runs | 178 | 178 | ✅ |
| FINAL-RESULTS.md | qwen2.5-14b 0.32.6 replication decision mismatches (of 2300) | 0 | 0 | ✅ |

**47/50 committed claims reproduce; 3 mismatch(es) flagged above.**

Contradiction notes (the ❌ rows, interpreted):

1. **FINAL-RESULTS.md:105 — "qwen2.5:7b … 23–27 decision flips".** Under the convention every other committed figure uses (both arms combined, primary t0-fixed block), the recomputed values are **25 (Ollama 0.31.1) → 27 (0.32.6)** — i.e. 25–27, not 23–27. The low end 23 matches no arm/block combination (closest: MAS-only t0+pert at 0.31.1 = 23, a different universe than the 45-flip gemma4 figure in the same list).

2. **SUPERVISOR-PACK.md:89 and dissertation-v3.tex:779 — "qwen2.5:14b byte-diverged 105 of 110 groups".** Recomputed byte-divergent groups: **98/100** (primary, both arms) or **117/120** including the perturbation block. Neither the numerator 105 nor the denominator 110 is reproducible from the journals under any block/arm combination tried.

3. **ANALYSIS-INSIGHTS.md:43 — "gemma4-single … worst T=0 cache-stability in the experiment (35 flipping groups)".** 35 is the BOTH-ARMS sweep figure (single 15 + MAS 20); the single arm alone flips 15/50. The number is right for the sweep but misattributed to the single-arm config.

---
*End of report. Regenerate at any seal with `python3 backend/experiments/analysis/master_report_gen.py`.*
