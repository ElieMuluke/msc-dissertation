# Dissertation figures

`backend/experiments/analysis/figures.py` regenerates every figure in the results
chapter that is derived from measured data (Figures 5 to 13). It reads the
append-only sweep journals and the DFAH ground-truth labels, and nothing else.
No figure is built from a report, a table, or a previous figure.

This exists so that "show me the code that generated Figure 13" has an answer.

## Running it

From `backend/`:

```bash
python -m experiments.analysis.figures --out ../docs/final-figs
python -m experiments.analysis.figures --only fig10 fig13
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--out` | `../docs/final-figs` | Directory to write PNGs into (created if absent) |
| `--only` | all | One or more figure names (`fig5` … `fig13`) |
| `--alerts` | see below | Path to the DFAH `alerts.json` |

### The label file

Accuracy metrics need the DFAH ground-truth labels, which live in the benchmark
clone outside this repository. The path is resolved in order:

1. `--alerts <path>`
2. `$DFAH_ALERTS`
3. `experiments.config.ALERTS_JSON`

`config.ALERTS_JSON` is derived from `config.DFAH_REPO`, an absolute path to the
benchmark clone on this machine. On any other machine pass `--alerts` or export
`DFAH_ALERTS` rather than editing the constant. Perturbation-case labels come
from the in-repo `experiments/perturbation_cases.json` and need no
configuration.

Repeatability metrics (DAR, flips, tokens, decision shares) do not use labels;
only `pass^k` does.

## What each figure shows

| Figure | File | Content | Sweeps | Condition |
|---|---|---|---|---|
| 5 | `fig5-experiment1-agreement.png` | pass¹ and DAR per architecture | `EXP1_MODELS` (4) | `t07-varied` |
| 6 | `fig6-serving-version.png` | Same models on Ollama 0.31.1 and 0.32.6 | `SERVING_PAIRS` (3) | `t07-varied` |
| 7 | `fig7-experiment2-agreement.png` | pass¹ and DAR per architecture | `EXP2_MODELS` (8) | `t07-varied` |
| 8 | `fig8-experiment3-budget.png` | DAR, 8-turn undisclosed vs 32-turn disclosed | `BUDGET_PAIRS` (6) | `t07-varied` |
| 9 | `fig9-decomposition-effect.png` | MAS − single on pass¹ and DAR | `EXP2_MODELS` | `t07-varied` |
| 10 | `fig10-pass-k.png` | pass^1, pass^5, pass^15 | `EXP2_MODELS` | `t07-varied` |
| 11 | `fig11-decision-changes.png` | Case-groups whose decision changed | `EXP2_MODELS` | `t0-fixed` + `pert-t0`, and `t07-varied` |
| 12 | `fig12-tokens-per-run.png` | Mean tokens per run, MAS-to-single ratio | `EXP2_MODELS` | `t07-varied` |
| 13 | `fig13-decision-redistribution.png` | Share of each decision per architecture | `EXP2_MODELS` | `t07-varied` |

Figures 1 to 3 are architecture diagrams, not measurements, and Figure 4 comes
from the retrieval sweep rather than the experiment journals. None of them is
built here.

## Which sweep feeds which bar

The groupings are module constants at the top of `figures.py`, keyed by
`config.REPLICATION_MODELS` registry keys, so a reader can check the mapping
without reading plotting code. Two of them are easy to get wrong:

- **`BUDGET_PAIRS`** pairs each `@b32` sweep with the baseline it is compared
  against, which is not always the same tag. `qwen3.5:9b@b32`'s baseline is
  `qwen3.5:9b@0.32.6` (the context-2 sweep), not `qwen3.5:9b`.
- **`T0_CONDITIONS`** is `("t0-fixed", "pert-t0")`. Temperature-zero flip counts
  are over 60 case-groups (50 primary + 10 perturbation), not 50. A case measured
  under both conditions contributes two independent groups.

## Design

`arm_stats()` returns an `ArmStats` for one sweep × arm × condition set. It calls
the pre-registered functions in `metrics.py` rather than redefining any metric,
but computes only what the figures need — unlike `metrics.condition_summary()`,
which also runs the trajectory and ROUGE passes and is roughly two orders of
magnitude slower over eighteen sweeps.

`SweepReader` caches journals per registry key, so a sweep appearing in several
figures is read from disk once.

A sweep with no data for a requested condition yields `None`, which the plotting
helpers render as `NaN` — a gap in the chart. This is deliberate: a missing
sweep must not draw a bar at zero, which would read as a measured result.

## Verification

Every number the module produces was checked against the dissertation's own
tables before the figures were adopted:

- Table 8 (Experiment 1): Krippendorff's alpha, flip rate and tokens per run
  match for all four models and both architectures.
- Table 9 (Experiment 2): matches, including muse-glimmer:30b at 0.435 / 0.619.
- Table 10 (Experiment 3): all twelve baseline-to-budget deltas match.
- The MAS-to-single token ratio spans 1.8 to 3.1, as stated in the abstract.

`experiments/tests/test_figures.py` covers `arm_stats()` on synthetic journals
with hand-computed expectations, including the multi-condition pooling rule and
the empty-sweep case.
