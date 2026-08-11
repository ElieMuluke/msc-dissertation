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
- `qwen2.5:7b-instruct@0.32.6`: 2300/2300 runs journalled
- `qwen3.5:9b@0.32.6`: 2300/2300 runs journalled
- `qwen2.5:14b-instruct@0.32.6`: 2300/2300 runs journalled

## Condition `t0-fixed`

| arm | metric | `qwen3.5:9b` | `qwen2.5:7b-instruct` | `mistral-nemo:latest` | `mistral-small3.2:24b` | `llama3.1:8b` | `qwen2.5:14b-instruct` | `gemma3:27b` | `gemma4:latest` | `granite4:latest` | `gpt-oss:20b` | `qwen2.5:7b-instruct@0.32.6` | `qwen3.5:9b@0.32.6` | `qwen2.5:14b-instruct@0.32.6` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | pass^1 | 0.400 | 0.244 | — | — | — | 0.188 | — | 0.648 | — | — | 0.244 | 0.300 | 0.188 |
| single | pass^5 | 0.400 | 0.220 | — | — | — | 0.160 | — | 0.520 | — | — | 0.220 | 0.300 | 0.160 |
| single | pass^15 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| single | DAR | 1.000 | 0.952 | — | — | — | 0.968 | — | 0.880 | — | — | 0.952 | 1.000 | 0.968 |
| single | krippendorff_alpha | 1.000 | 0.783 | — | — | — | 0.884 | — | 0.819 | — | — | 0.783 | 1.000 | 0.884 |
| single | flip_rate | 0.000 | 0.120 | — | — | — | 0.080 | — | 0.300 | — | — | 0.120 | 0.000 | 0.080 |
| mas | pass^1 | 0.260 | 0.380 | — | — | — | 0.232 | — | 0.312 | — | — | 0.380 | 0.300 | 0.232 |
| mas | pass^5 | 0.260 | 0.200 | — | — | — | 0.220 | — | 0.240 | — | — | 0.200 | 0.300 | 0.220 |
| mas | pass^15 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| mas | DAR | 1.000 | 0.824 | — | — | — | 0.976 | — | 0.804 | — | — | 0.804 | 1.000 | 0.976 |
| mas | krippendorff_alpha | 1.000 | 0.576 | — | — | — | 0.758 | — | 0.609 | — | — | 0.528 | 1.000 | 0.758 |
| mas | flip_rate | 0.000 | 0.380 | — | — | — | 0.060 | — | 0.400 | — | — | 0.420 | 0.000 | 0.060 |

## Condition `t07-varied`

| arm | metric | `qwen3.5:9b` | `qwen2.5:7b-instruct` | `mistral-nemo:latest` | `mistral-small3.2:24b` | `llama3.1:8b` | `qwen2.5:14b-instruct` | `gemma3:27b` | `gemma4:latest` | `granite4:latest` | `gpt-oss:20b` | `qwen2.5:7b-instruct@0.32.6` | `qwen3.5:9b@0.32.6` | `qwen2.5:14b-instruct@0.32.6` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | pass^1 | 0.364 | 0.293 | — | — | — | 0.248 | — | 0.552 | — | — | 0.299 | 0.339 | 0.248 |
| single | pass^5 | 0.078 | 0.089 | — | — | — | 0.149 | — | 0.185 | — | — | 0.095 | 0.079 | 0.149 |
| single | pass^15 | 0.040 | 0.000 | — | — | — | 0.060 | — | 0.080 | — | — | 0.020 | 0.040 | 0.060 |
| single | DAR | 0.618 | 0.719 | — | — | — | 0.893 | — | 0.594 | — | — | 0.715 | 0.655 | 0.893 |
| single | krippendorff_alpha | 0.205 | 0.102 | — | — | — | 0.382 | — | 0.387 | — | — | 0.106 | 0.241 | 0.382 |
| single | flip_rate | 0.920 | 0.880 | — | — | — | 0.460 | — | 0.900 | — | — | 0.840 | 0.900 | 0.460 |
| mas | pass^1 | 0.253 | 0.449 | — | — | — | 0.221 | — | 0.297 | — | — | 0.456 | 0.255 | 0.221 |
| mas | pass^5 | 0.110 | 0.107 | — | — | — | 0.145 | — | 0.113 | — | — | 0.139 | 0.108 | 0.145 |
| mas | pass^15 | 0.060 | 0.020 | — | — | — | 0.100 | — | 0.040 | — | — | 0.040 | 0.040 | 0.100 |
| mas | DAR | 0.802 | 0.647 | — | — | — | 0.914 | — | 0.705 | — | — | 0.661 | 0.809 | 0.914 |
| mas | krippendorff_alpha | 0.203 | 0.279 | — | — | — | 0.340 | — | 0.406 | — | — | 0.276 | 0.191 | 0.340 |
| mas | flip_rate | 0.760 | 0.900 | — | — | — | 0.320 | — | 0.840 | — | — | 0.860 | 0.800 | 0.320 |
