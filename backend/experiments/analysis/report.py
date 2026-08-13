"""Analysis deliverable: ``results/analysis-report.md`` + figures.

Everything is computed from the journals plus the manifest — no other
inputs. Every metric in the pre-registered tier table is either computed
for every arm × condition or listed with the reason it could not be.

Usage::

    python -m experiments.analysis.report
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from experiments.config import ARMS, CONDITIONS, DEFAULT_CONFIG
from experiments.analysis import metrics
from experiments.analysis.stats import bootstrap_ci_mean, paired_permutation_pvalue
from experiments.harness.dfah_data import (
    ground_truth,
    load_perturbation_cases,
    load_primary_cases,
)
from experiments.harness.journal import journal_path, read_journal

PRIMARY_CONDITION = "t07-varied"
PERT_CONDITIONS = ("pert-t0", "pert-t05", "pert-t10")
PERT_TEMPS = {"pert-t0": 0.0, "pert-t05": 0.5, "pert-t10": 1.0}


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(_fmt(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _summaries(
    journals: dict[str, list[dict[str, Any]]], labels: dict[str, str]
) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for arm in ARMS:
        for cond in CONDITIONS:
            groups = metrics.group_case_runs(journals[arm], arm, cond.name)
            complete = {c: g for c, g in groups.items() if len(g.decisions) >= 2}
            out[(arm, cond.name)] = (
                metrics.condition_summary(complete, labels) if complete else {"cases": 0}
            )
    return out


def _arm_comparison(journals: dict[str, list[dict[str, Any]]], labels: dict[str, str]) -> list[list[Any]]:
    """Bootstrap CI + permutation test on per-case A−B differences (t07)."""
    per_case: dict[str, dict[str, dict[str, float]]] = {}
    for arm in ARMS:
        groups = metrics.group_case_runs(journals[arm], arm, PRIMARY_CONDITION)
        per_case[arm] = {
            c: {
                "pass_fraction": sum(d == labels[c] for d in g.decisions) / len(g.decisions),
                "DAR": metrics.decision_agreement_rate(g.decisions),
                "entropy": metrics.normalised_entropy(g.decisions),
            }
            for c, g in groups.items()
            if len(g.decisions) >= 2
        }
    shared = sorted(set(per_case["single"]) & set(per_case["mas"]))
    rows: list[list[Any]] = []
    for metric in ("pass_fraction", "DAR", "entropy"):
        diffs = [
            per_case["single"][c][metric] - per_case["mas"][c][metric] for c in shared
        ]
        if not diffs:
            rows.append([metric, "—", "—", "not computed: no shared complete cases"])
            continue
        lo, hi = bootstrap_ci_mean(diffs, seed=1)
        p = paired_permutation_pvalue(diffs, seed=1)
        rows.append([metric, sum(diffs) / len(diffs), f"[{lo:.3f}, {hi:.3f}]", p])
    return rows


def _entropy_figure(summaries, figs_dir: Path) -> str | None:
    data = {
        arm: summaries[(arm, PRIMARY_CONDITION)].get("per_case_entropy") for arm in ARMS
    }
    if not all(data.values()):
        return None
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(
        [list(data[arm].values()) for arm in ARMS],
        bins=10, range=(0, 1), label=list(ARMS),
    )
    ax.set_xlabel("normalised decision entropy (per case)")
    ax.set_ylabel("cases")
    ax.set_title(f"Per-case entropy, {PRIMARY_CONDITION}")
    ax.legend()
    path = figs_dir / "entropy-hist.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path.name


def _perturbation_figure(summaries, figs_dir: Path) -> str | None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
    plotted = False
    for metric, ax in zip(("flip_rate", "DAR"), axes):
        for arm in ARMS:
            xs, ys = [], []
            for cond in PERT_CONDITIONS:
                value = summaries[(arm, cond)].get(metric)
                if value is not None:
                    xs.append(PERT_TEMPS[cond])
                    ys.append(value)
            if xs:
                ax.plot(xs, ys, marker="o", label=arm)
                plotted = True
        ax.set_xlabel("temperature")
        ax.set_ylabel(metric)
        ax.set_ylim(-0.05, 1.05)
        ax.legend()
    fig.suptitle("Perturbation block: temperature trend")
    if not plotted:
        plt.close(fig)
        return None
    path = figs_dir / "perturbation-trend.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path.name


TIER1_KEYS = ("pass^1", "pass^5", "pass^15", "DAR", "krippendorff_alpha", "flip_rate")
TIER2_KEYS = ("majority_vote_accuracy", "mean_entropy", "TAR", "jaccard", "nLCS",
              "malformed_rate")
# tokens_per_pass reported at ALL k (pre-registered 2026-08-06): a cell is "—"
# when the condition has fewer repeats than k or pass^k is zero.
COST_KEYS = ("tokens_per_run", "tokens_per_pass^1", "tokens_per_pass^5",
             "tokens_per_pass^15", "mean_wall_clock_s")


def build_report(results_dir: Path = DEFAULT_CONFIG.results_dir) -> Path:
    figs_dir = results_dir / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((results_dir / "manifest.json").read_text())
    labels = {**ground_truth(load_primary_cases()), **ground_truth(load_perturbation_cases())}
    journals = {arm: read_journal(journal_path(results_dir, arm)) for arm in ARMS}
    summaries = _summaries(journals, labels)

    lines: list[str] = ["# Analysis report — PRD-A repeatability experiment", ""]
    lines += [
        f"Model `{manifest['model']}` ({manifest['model_digest'][:19]}…), "
        f"Ollama {manifest['ollama_version']}, config hash "
        f"`{manifest['config_hash'][:12]}`.",
        f"Journal lines: " + ", ".join(f"{arm}={len(journals[arm])}" for arm in ARMS)
        + f"; planned total {sum(manifest['totals'].values())}.",
        "",
        "pass^k is agreement with the benchmark authors' labels, not"
        " 'correctness'. Malformed outputs are included in every metric as an"
        " outcome category: they never match a label (pass^k, majority vote)"
        " and never match a real decision, but two malformed outputs count as"
        " agreeing with each other in DAR/alpha/entropy (category equality)."
        " Majority-vote ties break by canonical outcome order (escalate > dismiss > investigate > malformed).",
        "",
    ]

    def section(title: str, keys: tuple[str, ...], conds: list[str]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        headers = ["arm", "condition", "cases", "repeats", *keys]
        rows = []
        for arm in ARMS:
            for cond in conds:
                s = summaries[(arm, cond)]
                if s.get("cases", 0) == 0:
                    rows.append([arm, cond, 0, "—"] +
                                ["not computed: no journal records"] +
                                ["—"] * (len(keys) - 1))
                else:
                    rows.append([arm, cond, s["cases"], s["repeats"]] +
                                [s.get(k) for k in keys])
        lines.append(_table(headers, rows))
        lines.append("")

    primary_conds = ["t0-fixed", "t07-varied"]
    section("Headline: Tier 1 (primary conditions)", TIER1_KEYS, primary_conds)
    section("Tier 2", TIER2_KEYS, primary_conds)
    section("Cost (Tier 3)", COST_KEYS, primary_conds)
    section("Perturbation block (instrument check)", TIER1_KEYS + ("mean_entropy",),
            list(PERT_CONDITIONS))
    section("Appendix: lexical consistency (ROUGE-L)", ("rouge_l_f1",),
            primary_conds + list(PERT_CONDITIONS))
    lines.append(
        "rouge_l_f1 is the mean pairwise ROUGE-L F1 of the FULL raw output "
        "text across repeats (lowercased, whitespace tokens): surface-form "
        "overlap only, distinct from the decision-level and trajectory-level "
        "metrics above, and never part of the Tier 1 winner criterion."
    )
    lines.append("")

    lines.append("## Arm difference (single − mas), t07-varied, per-case paired")
    lines.append("")
    lines.append(_table(
        ["metric", "mean diff", "bootstrap 95% CI", "permutation p"],
        _arm_comparison(journals, labels),
    ))
    lines.append("")

    for arm in ARMS:
        worst = summaries[(arm, PRIMARY_CONDITION)].get("worst_entropy_cases")
        if worst:
            lines.append(f"Worst-entropy cases ({arm}, {PRIMARY_CONDITION}): "
                         + ", ".join(worst))
    lines.append("")

    lines.append("## Figures")
    lines.append("")
    for name in (_entropy_figure(summaries, figs_dir),
                 _perturbation_figure(summaries, figs_dir)):
        lines.append(f"![]({'figs/' + name})" if name
                     else "figure not generated: insufficient journal data")
    lines.append("")

    target = results_dir / "analysis-report.md"
    target.write_text("\n".join(lines))
    return target


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default=None,
        help="replication model tag — analyse that model's results dir",
    )
    parser.add_argument("--results-dir", type=Path, default=None,
                        help="explicit results dir (overrides --model)")
    cli = parser.parse_args()
    if cli.results_dir is not None:
        target_dir = cli.results_dir
    elif cli.model is not None:
        from experiments.config import config_for_model

        target_dir = config_for_model(cli.model).results_dir
    else:
        target_dir = DEFAULT_CONFIG.results_dir
    print(f"wrote {build_report(target_dir)}")
