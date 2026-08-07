# Cross-model comparison — Tier 1 (pre-registered metrics)

Headline pre-registered result: `qwen3.5:9b`. Other models are
robustness replications of the identical design (same cases, seed
schedule, conditions, metrics). pass^k is agreement with benchmark
authors' labels; malformed outputs are included in every metric.

## Sweep status

- `qwen3.5:9b`: 2300/2300 runs journalled
- `qwen2.5:7b-instruct`: 2300/2300 runs journalled
- `mistral-nemo:latest`: 0/2300 runs journalled
- `mistral-small3.2:24b`: 0/2300 runs journalled
- `llama3.1:8b`: 0/2300 runs journalled

## Condition `t0-fixed`

| arm | metric | `qwen3.5:9b` | `qwen2.5:7b-instruct` | `mistral-nemo:latest` | `mistral-small3.2:24b` | `llama3.1:8b` |
|---|---|---|---|---|---|---|
| single | pass^1 | 0.400 | 0.244 | — | — | — |
| single | pass^5 | 0.400 | 0.220 | — | — | — |
| single | pass^15 | — | — | — | — | — |
| single | DAR | 1.000 | 0.952 | — | — | — |
| single | krippendorff_alpha | 1.000 | 0.783 | — | — | — |
| single | flip_rate | 0.000 | 0.120 | — | — | — |
| mas | pass^1 | 0.260 | 0.380 | — | — | — |
| mas | pass^5 | 0.260 | 0.200 | — | — | — |
| mas | pass^15 | — | — | — | — | — |
| mas | DAR | 1.000 | 0.824 | — | — | — |
| mas | krippendorff_alpha | 1.000 | 0.576 | — | — | — |
| mas | flip_rate | 0.000 | 0.380 | — | — | — |

## Condition `t07-varied`

| arm | metric | `qwen3.5:9b` | `qwen2.5:7b-instruct` | `mistral-nemo:latest` | `mistral-small3.2:24b` | `llama3.1:8b` |
|---|---|---|---|---|---|---|
| single | pass^1 | 0.364 | 0.293 | — | — | — |
| single | pass^5 | 0.078 | 0.089 | — | — | — |
| single | pass^15 | 0.040 | 0.000 | — | — | — |
| single | DAR | 0.618 | 0.719 | — | — | — |
| single | krippendorff_alpha | 0.205 | 0.102 | — | — | — |
| single | flip_rate | 0.920 | 0.880 | — | — | — |
| mas | pass^1 | 0.253 | 0.449 | — | — | — |
| mas | pass^5 | 0.110 | 0.107 | — | — | — |
| mas | pass^15 | 0.060 | 0.020 | — | — | — |
| mas | DAR | 0.802 | 0.647 | — | — | — |
| mas | krippendorff_alpha | 0.203 | 0.279 | — | — | — |
| mas | flip_rate | 0.760 | 0.900 | — | — | — |
