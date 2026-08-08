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
- `qwen2.5:14b-instruct`: 2300/2300 runs journalled
- `gemma3:27b`: 0/2300 runs journalled
- `gemma4:latest`: 2300/2300 runs journalled
- `granite4:latest`: 0/2300 runs journalled
- `gpt-oss:20b`: 0/2300 runs journalled

## Condition `t0-fixed`

| arm | metric | `qwen3.5:9b` | `qwen2.5:7b-instruct` | `mistral-nemo:latest` | `mistral-small3.2:24b` | `llama3.1:8b` | `qwen2.5:14b-instruct` | `gemma3:27b` | `gemma4:latest` | `granite4:latest` | `gpt-oss:20b` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| single | pass^1 | 0.400 | 0.244 | — | — | — | 0.188 | — | 0.648 | — | — |
| single | pass^5 | 0.400 | 0.220 | — | — | — | 0.160 | — | 0.520 | — | — |
| single | pass^15 | — | — | — | — | — | — | — | — | — | — |
| single | DAR | 1.000 | 0.952 | — | — | — | 0.968 | — | 0.880 | — | — |
| single | krippendorff_alpha | 1.000 | 0.783 | — | — | — | 0.884 | — | 0.819 | — | — |
| single | flip_rate | 0.000 | 0.120 | — | — | — | 0.080 | — | 0.300 | — | — |
| mas | pass^1 | 0.260 | 0.380 | — | — | — | 0.232 | — | 0.312 | — | — |
| mas | pass^5 | 0.260 | 0.200 | — | — | — | 0.220 | — | 0.240 | — | — |
| mas | pass^15 | — | — | — | — | — | — | — | — | — | — |
| mas | DAR | 1.000 | 0.824 | — | — | — | 0.976 | — | 0.804 | — | — |
| mas | krippendorff_alpha | 1.000 | 0.576 | — | — | — | 0.758 | — | 0.609 | — | — |
| mas | flip_rate | 0.000 | 0.380 | — | — | — | 0.060 | — | 0.400 | — | — |

## Condition `t07-varied`

| arm | metric | `qwen3.5:9b` | `qwen2.5:7b-instruct` | `mistral-nemo:latest` | `mistral-small3.2:24b` | `llama3.1:8b` | `qwen2.5:14b-instruct` | `gemma3:27b` | `gemma4:latest` | `granite4:latest` | `gpt-oss:20b` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| single | pass^1 | 0.364 | 0.293 | — | — | — | 0.248 | — | 0.552 | — | — |
| single | pass^5 | 0.078 | 0.089 | — | — | — | 0.149 | — | 0.185 | — | — |
| single | pass^15 | 0.040 | 0.000 | — | — | — | 0.060 | — | 0.080 | — | — |
| single | DAR | 0.618 | 0.719 | — | — | — | 0.893 | — | 0.594 | — | — |
| single | krippendorff_alpha | 0.205 | 0.102 | — | — | — | 0.382 | — | 0.387 | — | — |
| single | flip_rate | 0.920 | 0.880 | — | — | — | 0.460 | — | 0.900 | — | — |
| mas | pass^1 | 0.253 | 0.449 | — | — | — | 0.221 | — | 0.297 | — | — |
| mas | pass^5 | 0.110 | 0.107 | — | — | — | 0.145 | — | 0.113 | — | — |
| mas | pass^15 | 0.060 | 0.020 | — | — | — | 0.100 | — | 0.040 | — | — |
| mas | DAR | 0.802 | 0.647 | — | — | — | 0.914 | — | 0.705 | — | — |
| mas | krippendorff_alpha | 0.203 | 0.279 | — | — | — | 0.340 | — | 0.406 | — | — |
| mas | flip_rate | 0.760 | 0.900 | — | — | — | 0.320 | — | 0.840 | — | — |
