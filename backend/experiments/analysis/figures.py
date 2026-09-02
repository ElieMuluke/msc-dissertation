"""Dissertation figures, regenerated from the sweep journals.

Every figure in the results chapter that is derived from measured data is
built here. The only inputs are the append-only sweep journals under each
``results-*`` directory and the DFAH ground-truth labels; nothing is read
from a report, a table or a previous figure.

Metric definitions are not redefined: each one calls the pre-registered
function in :mod:`experiments.analysis.metrics`. Unlike
:func:`metrics.condition_summary` this module computes only the quantities
the figures need, so it skips the expensive trajectory and ROUGE passes.

The label file lives outside this repository (the DFAH benchmark clone).
It is resolved from ``--alerts``, then ``$DFAH_ALERTS``, then
:data:`experiments.config.ALERTS_JSON`.

Usage (from ``backend/``)::

    python -m experiments.analysis.figures --out ../docs/final-figs
    python -m experiments.analysis.figures --only fig10 fig13
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from experiments.analysis import metrics
from experiments.config import ALERTS_JSON, ARMS, DECISIONS, config_for_model
from experiments.harness.dfah_data import (
    ground_truth,
    load_perturbation_cases,
    load_primary_cases,
)
from experiments.harness.journal import journal_path, read_journal

# --- What each figure covers -------------------------------------------------
# Registry keys (config.REPLICATION_MODELS) paired with the short label used
# on the axis. Declared here so a reader can see exactly which sweep feeds
# which bar without opening the plotting code.

PRIMARY = "t07-varied"
#: Temperature-zero determinism is measured over the primary fixed-seed
#: condition plus the fixed-seed perturbation block: 50 + 10 case-groups.
T0_CONDITIONS = ("t0-fixed", "pert-t0")

EXP1_MODELS: list[tuple[str, str]] = [
    ("qwen3.5:9b", "qwen3.5:9b"),
    ("qwen2.5:7b-instruct", "qwen2.5:7b"),
    ("qwen2.5:14b-instruct", "qwen2.5:14b"),
    ("gemma4:latest", "gemma4"),
]

#: (context-1 key, context-2 key, label) — same model blobs, different
#: serving-stack version (Ollama 0.31.1 vs 0.32.6).
SERVING_PAIRS: list[tuple[str, str, str]] = [
    ("qwen3.5:9b", "qwen3.5:9b@0.32.6", "qwen3.5:9b"),
    ("qwen2.5:7b-instruct", "qwen2.5:7b-instruct@0.32.6", "qwen2.5:7b"),
    ("qwen2.5:14b-instruct", "qwen2.5:14b-instruct@0.32.6", "qwen2.5:14b"),
]

#: The eight configurations carried through the results chapter.
EXP2_MODELS: list[tuple[str, str]] = [
    ("qwen3.5:9b", "qwen3.5:9b"),
    ("qwen2.5:7b-instruct", "qwen2.5:7b"),
    ("qwen2.5:14b-instruct", "qwen2.5:14b"),
    ("gemma4:latest", "gemma4"),
    ("granite4.1:8b", "granite4.1:8b"),
    ("muse-glimmer:30b", "muse-glimmer:30b"),
    ("lfm2.5:8b@think", "lfm2.5:8b (delib.)"),
    ("qwen3.5:9b@think-budget", "qwen3.5:9b (delib.)"),
]

#: (baseline key, equalised-budget key, label). The baseline is the sweep the
#: "@b32" re-run is compared against in the budget track, not simply the
#: same tag: qwen3.5:9b's baseline is its context-2 sweep.
BUDGET_PAIRS: list[tuple[str, str, str]] = [
    ("qwen2.5:7b-instruct", "qwen2.5:7b-instruct@b32", "qwen2.5:7b"),
    ("granite4.1:8b", "granite4.1:8b@b32", "granite4.1:8b"),
    ("qwen3.5:9b@0.32.6", "qwen3.5:9b@b32", "qwen3.5:9b"),
    ("lfm2.5:8b@think", "lfm2.5:8b@b32-think", "lfm2.5:8b (delib.)"),
    (
        "qwen3.5:9b@think-budget",
        "qwen3.5:9b@b32-think-budget",
        "qwen3.5:9b (delib.)",
    ),
    ("gemma4:latest", "gemma4:latest@b32", "gemma4"),
]

# --- Style -------------------------------------------------------------------

SINGLE_FC, MAS_FC = "#D9D9D9", "#6E6E6E"
EDGE = "#2B2B2B"
ARM_LABEL = {"single": "Single agent", "mas": "MAS"}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 9,
            "axes.edgecolor": "#555555",
            "axes.labelcolor": "#1A1A1A",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": "#DDDDDD",
            "grid.linewidth": 0.6,
            "xtick.color": "#333333",
            "ytick.color": "#333333",
        }
    )


def _save(fig: plt.Figure, out_dir: Path, name: str) -> Path:
    path = out_dir / f"{name}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# --- Stats -------------------------------------------------------------------


@dataclass(frozen=True)
class ArmStats:
    """The figure-relevant metrics for one sweep × arm × condition set."""

    cases: int
    repeats: int
    pass_k: dict[int, float]
    dar: float
    alpha: float | None
    flip_rate: float
    flipped_cases: int
    tokens_per_run: float
    decision_share: dict[str, float]


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def arm_stats(
    records: list[dict[str, Any]],
    arm: str,
    conditions: Sequence[str],
    labels: dict[str, str],
    pass_ks: Sequence[int] = (1, 5, 15),
) -> ArmStats | None:
    """Metrics for one arm over one or more conditions, or None if empty.

    Case-groups from several conditions are kept separate (a case measured
    under both ``t0-fixed`` and ``pert-t0`` contributes two groups), which is
    how the temperature-zero flip counts are defined.
    """
    groups: list[tuple[str, metrics.CaseRuns]] = []
    for condition in conditions:
        for case_id, runs in sorted(
            metrics.group_case_runs(records, arm, condition).items()
        ):
            if len(runs.decisions) >= 2:
                groups.append((case_id, runs))
    if not groups:
        return None

    decisions = [g.decisions for _, g in groups]
    n_repeats = min(len(d) for d in decisions)
    flips = [flipped for flipped in (metrics.flipped(d) for d in decisions)]
    counts = {outcome: 0 for outcome in (*DECISIONS, "malformed")}
    total = 0
    for run_decisions in decisions:
        for decision in run_decisions:
            counts[decision] = counts.get(decision, 0) + 1
            total += 1
    tokens = [
        prompt + completion
        for _, g in groups
        for prompt, completion in zip(g.prompt_tokens, g.completion_tokens)
    ]
    return ArmStats(
        cases=len(groups),
        repeats=n_repeats,
        pass_k={
            k: _mean(
                [
                    metrics.case_pass_hat_k(g.decisions, labels[case_id], k)
                    for case_id, g in groups
                ]
            )
            for k in pass_ks
            if k <= n_repeats
        },
        dar=_mean([metrics.decision_agreement_rate(d) for d in decisions]),
        alpha=metrics.krippendorff_alpha(decisions),
        flip_rate=_mean([float(f) for f in flips]),
        flipped_cases=sum(flips),
        tokens_per_run=_mean([float(t) for t in tokens]),
        decision_share={k: (v / total if total else 0.0) for k, v in counts.items()},
    )


class SweepReader:
    """Loads and caches journals per registry key."""

    def __init__(self, labels: dict[str, str]) -> None:
        self.labels = labels
        self._journals: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def journals(self, key: str) -> dict[str, list[dict[str, Any]]]:
        if key not in self._journals:
            results_dir = config_for_model(key).results_dir
            self._journals[key] = {
                arm: read_journal(journal_path(results_dir, arm)) for arm in ARMS
            }
        return self._journals[key]

    def stats(
        self, key: str, arm: str, conditions: Sequence[str] = (PRIMARY,)
    ) -> ArmStats | None:
        return arm_stats(self.journals(key)[arm], arm, conditions, self.labels)


# --- Shared plotting helpers -------------------------------------------------


def _grouped_bars(
    ax: plt.Axes,
    categories: Sequence[str],
    series: Sequence[tuple[str, Sequence[float], str]],
    ylabel: str,
    title: str,
) -> None:
    """One cluster of bars per category, one bar per series."""
    width = 0.8 / len(series)
    offsets = [(i - (len(series) - 1) / 2) * width for i in range(len(series))]
    for (label, values, colour), offset in zip(series, offsets):
        positions = [i + offset for i in range(len(categories))]
        ax.bar(
            positions,
            values,
            width=width * 0.92,
            label=label,
            facecolor=colour,
            edgecolor=EDGE,
            linewidth=0.7,
        )
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=30, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10, fontweight="bold")


def _arm_series(
    reader: SweepReader,
    models: Sequence[tuple[str, str]],
    pick: Callable[[ArmStats], float],
    conditions: Sequence[str] = (PRIMARY,),
) -> tuple[list[str], list[tuple[str, list[float], str]]]:
    names = [label for _, label in models]
    series = []
    for arm, colour in (("single", SINGLE_FC), ("mas", MAS_FC)):
        values = []
        for key, _ in models:
            stats = reader.stats(key, arm, conditions)
            # NaN, not 0 — a sweep with no data for this condition leaves a
            # gap in the chart instead of a bar that reads as a real zero.
            values.append(pick(stats) if stats else float("nan"))
        series.append((ARM_LABEL[arm], values, colour))
    return names, series


# --- Figures -----------------------------------------------------------------


def fig5(reader: SweepReader, out_dir: Path) -> Path:
    """Experiment 1: label agreement and self-agreement, four baseline models."""
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))
    for ax, (pick, ylabel, title) in zip(
        axes,
        [
            (lambda s: s.pass_k[1], "pass¹", "Label agreement"),
            (lambda s: s.dar, "DAR", "Self-agreement"),
        ],
    ):
        names, series = _arm_series(reader, EXP1_MODELS, pick)
        _grouped_bars(ax, names, series, ylabel, title)
        ax.set_ylim(0, 1)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return _save(fig, out_dir, "fig5-experiment1-agreement")


def fig6(reader: SweepReader, out_dir: Path) -> Path:
    """The three qwen models run on both serving-stack versions."""
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))
    names = [label for _, _, label in SERVING_PAIRS]
    for ax, (pick, ylabel, title) in zip(
        axes,
        [
            (lambda s: s.pass_k[1], "pass¹", "Label agreement"),
            (lambda s: s.dar, "DAR", "Self-agreement"),
        ],
    ):
        series = []
        for arm, base_colour in (("single", SINGLE_FC), ("mas", MAS_FC)):
            for idx, version in enumerate(("0.31.1", "0.32.6")):
                values = []
                for keys in SERVING_PAIRS:
                    stats = reader.stats(keys[idx], arm)
                    values.append(pick(stats) if stats else float("nan"))
                series.append(
                    (
                        f"{ARM_LABEL[arm]}, {version}",
                        values,
                        base_colour if idx == 0 else "#FFFFFF" if arm == "single" else "#B0B0B0",
                    )
                )
        _grouped_bars(ax, names, series, ylabel, title)
        ax.set_ylim(0, 1)
    axes[0].legend(frameon=False, fontsize=7.5, ncol=2)
    fig.tight_layout()
    return _save(fig, out_dir, "fig6-serving-version")


def fig7(reader: SweepReader, out_dir: Path) -> Path:
    """Experiment 2: label agreement and self-agreement per architecture."""
    fig, axes = plt.subplots(2, 1, figsize=(9.0, 6.4))
    for ax, (pick, ylabel, title) in zip(
        axes,
        [
            (lambda s: s.pass_k[1], "pass¹", "Label agreement"),
            (lambda s: s.dar, "DAR", "Self-agreement"),
        ],
    ):
        names, series = _arm_series(reader, EXP2_MODELS, pick)
        _grouped_bars(ax, names, series, ylabel, title)
        ax.set_ylim(0, 1)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return _save(fig, out_dir, "fig7-experiment2-agreement")


def fig8(reader: SweepReader, out_dir: Path) -> Path:
    """Experiment 3: self-agreement, 8-turn undisclosed vs 32-turn disclosed."""
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    names = [f"{label}\n{ARM_LABEL[arm]}" for _, _, label in BUDGET_PAIRS for arm in ARMS]
    series = []
    for idx, (track, colour) in enumerate(
        ((("8 turns, undisclosed"), SINGLE_FC), (("32 turns, disclosed"), MAS_FC))
    ):
        values = []
        for keys in BUDGET_PAIRS:
            for arm in ARMS:
                stats = reader.stats(keys[idx], arm)
                values.append(stats.dar if stats else float("nan"))
        series.append((track, values, colour))
    _grouped_bars(ax, names, series, "DAR", "Self-agreement under each turn budget")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return _save(fig, out_dir, "fig8-experiment3-budget")


def fig9(reader: SweepReader, out_dir: Path) -> Path:
    """Effect of decomposition (MAS − single) on accuracy and self-agreement."""
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    names = [label for _, label in EXP2_MODELS]
    series = []
    for pick, label, colour in (
        (lambda s: s.pass_k[1], "Δ pass¹", SINGLE_FC),
        (lambda s: s.dar, "Δ DAR", MAS_FC),
    ):
        values = []
        for key, _ in EXP2_MODELS:
            single, mas = reader.stats(key, "single"), reader.stats(key, "mas")
            values.append(pick(mas) - pick(single) if single and mas else float("nan"))
        series.append((label, values, colour))
    _grouped_bars(ax, names, series, "MAS − single agent", "Effect of decomposition")
    ax.axhline(0, color=EDGE, linewidth=0.9)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return _save(fig, out_dir, "fig9-decomposition-effect")


def fig10(reader: SweepReader, out_dir: Path) -> Path:
    """pass^k at k = 1, 5 and 15 for every configuration."""
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.6), sharey=True)
    for ax, k in zip(axes, (1, 5, 15)):
        names, series = _arm_series(reader, EXP2_MODELS, lambda s, k=k: s.pass_k.get(k, 0.0))
        _grouped_bars(ax, names, series, "pass^k" if k == 1 else "", f"pass^{k}")
        ax.set_ylim(0, 1)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return _save(fig, out_dir, "fig10-pass-k")


def fig11(reader: SweepReader, out_dir: Path) -> Path:
    """Case-groups whose decision changed, at temperature zero and at 0.7."""
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.8), sharey=False)
    panels = [
        (T0_CONDITIONS, "Temperature 0, fixed seed"),
        ((PRIMARY,), "Temperature 0.7, varied seeds"),
    ]
    for ax, (conditions, title) in zip(axes, panels):
        names, series = _arm_series(
            reader, EXP2_MODELS, lambda s: float(s.flipped_cases), conditions
        )
        total = max(
            (reader.stats(key, arm, conditions).cases if reader.stats(key, arm, conditions) else 0)
            for key, _ in EXP2_MODELS
            for arm in ARMS
        )
        _grouped_bars(ax, names, series, f"case-groups that changed (of {total})", title)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return _save(fig, out_dir, "fig11-decision-changes")


def fig12(reader: SweepReader, out_dir: Path) -> Path:
    """Mean tokens per run per configuration, with the MAS-to-single ratio."""
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    names, series = _arm_series(reader, EXP2_MODELS, lambda s: s.tokens_per_run)
    _grouped_bars(ax, names, series, "mean tokens per run", "Cost per decision")
    ax.legend(frameon=False, fontsize=8, loc="upper left")

    ratio_ax = ax.twinx()
    ratios = [
        (mas / single if single else float("nan"))
        for single, mas in zip(series[0][1], series[1][1])
    ]
    ratio_ax.plot(
        range(len(names)), ratios, marker="D", ms=5, color=EDGE, linewidth=1.1,
        label="MAS ÷ single",
    )
    ratio_ax.set_ylabel("MAS-to-single ratio")
    finite = [r for r in ratios if r == r]
    ratio_ax.set_ylim(0, max(finite) * 1.3 if finite else 1)
    ratio_ax.grid(False)
    ratio_ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    return _save(fig, out_dir, "fig12-tokens-per-run")


def fig13(reader: SweepReader, out_dir: Path) -> Path:
    """How the decisions themselves redistribute when the agent is decomposed."""
    outcomes = (*DECISIONS, "malformed")
    shades = ["#3A3A3A", "#8A8A8A", "#C4C4C4", "#F0F0F0"]
    fig, ax = plt.subplots(figsize=(10.0, 4.0))
    positions, tick_positions, tick_labels = [], [], []
    for idx, (key, label) in enumerate(EXP2_MODELS):
        base = idx * 1.0
        for offset, arm in ((-0.18, "single"), (0.18, "mas")):
            positions.append((base + offset, arm, key))
        tick_positions.append(base)
        tick_labels.append(label)

    for position, arm, key in positions:
        stats = reader.stats(key, arm)
        bottom = 0.0
        for outcome, shade in zip(outcomes, shades):
            share = stats.decision_share.get(outcome, 0.0) if stats else 0.0
            ax.bar(
                position, share, bottom=bottom, width=0.3,
                facecolor=shade, edgecolor=EDGE, linewidth=0.6,
                label=outcome if (position, outcome) == (positions[0][0], outcome) else None,
            )
            bottom += share
        ax.text(position, 1.02, "S" if arm == "single" else "M", ha="center", fontsize=7)

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=30, ha="right")
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("share of runs")
    ax.set_title(
        "Decision redistribution per configuration (S = single agent, M = MAS)",
        fontsize=10, fontweight="bold",
    )
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.42))
    fig.tight_layout()
    return _save(fig, out_dir, "fig13-decision-redistribution")


FIGURES: dict[str, Callable[[SweepReader, Path], Path]] = {
    "fig5": fig5,
    "fig6": fig6,
    "fig7": fig7,
    "fig8": fig8,
    "fig9": fig9,
    "fig10": fig10,
    "fig11": fig11,
    "fig12": fig12,
    "fig13": fig13,
}


# --- Entry point -------------------------------------------------------------


def resolve_alerts(explicit: str | None = None) -> Path:
    """The DFAH alerts file: ``--alerts``, then ``$DFAH_ALERTS``, then config."""
    for candidate in (explicit, os.environ.get("DFAH_ALERTS"), ALERTS_JSON):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise SystemExit(
        "DFAH alerts.json not found. Pass --alerts <path>, set $DFAH_ALERTS, "
        f"or place it at {ALERTS_JSON}."
    )


def build_figures(
    out_dir: Path, only: Sequence[str] | None = None, alerts: str | None = None
) -> list[Path]:
    """Regenerate the requested figures (all of them by default)."""
    _style()
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = {
        **ground_truth(load_primary_cases(resolve_alerts(alerts))),
        **ground_truth(load_perturbation_cases()),
    }
    reader = SweepReader(labels)
    names = list(only) if only else list(FIGURES)
    written = []
    for name in names:
        if name not in FIGURES:
            raise SystemExit(f"unknown figure {name!r}; known: {', '.join(FIGURES)}")
        written.append(FIGURES[name](reader, out_dir))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("../docs/final-figs"))
    parser.add_argument("--only", nargs="*", default=None, help="figure names, e.g. fig10")
    parser.add_argument("--alerts", default=None, help="path to the DFAH alerts.json")
    args = parser.parse_args()
    for path in build_figures(args.out, args.only, args.alerts):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
