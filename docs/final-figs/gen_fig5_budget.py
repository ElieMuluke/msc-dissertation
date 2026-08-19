"""fig5 — budget track: paired v2 -> v2b change per model and arm.

The question the figure must answer is whether relieving and disclosing the
iteration budget moved the arms, so it plots the pair, not the endpoint.
Run: backend/.venv/bin/python docs/final-figs/gen_fig5_budget.py
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

E = Path("/home/el/projects/msc-dissertation/backend/experiments")
LABELS = {
    r["alert_id"]: r["ground_truth"]
    for r in json.load(
        open("/home/el/projects/dfah-repo/econometrics/benchmarks/compliance_triage/data/alerts.json")
    )["alerts"]
}

PAIRS = [
    ("qwen2.5:7b", "results-qwen2.5-7b", "results-budget-qwen2.5-7b"),
    ("granite4.1:8b", "results-granite4.1-8b", "results-budget-granite4.1-8b"),
    ("qwen3.5:9b", "results-qwen3.5-9b-ollama0326", "results-budget-qwen3.5-9b"),
    ("lfm2.5:8b (think)", "results-lfm2.5-8b-thinking", "results-budget-lfm2.5-8b-thinking"),
]

BLUE, ORANGE, GREY = "#2E7BC4", "#E8663A", "#8A8F98"


def per_case(results_dir: str, arm: str) -> dict[str, float]:
    path = E / results_dir / f"journal-{arm}.jsonl"
    hits: dict[str, list[int]] = {}
    with path.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn tail on a live journal
            if r["condition"] != "t07-varied" or r["case_id"] not in LABELS:
                continue
            hits.setdefault(r["case_id"], []).append(
                int(r.get("decision") == LABELS[r["case_id"]])
            )
    return {c: sum(v) / len(v) for c, v in hits.items()}


def paired_stats(before: dict[str, float], after: dict[str, float]):
    cases = sorted(set(before) & set(after))
    diffs = [after[c] - before[c] for c in cases]
    obs = sum(diffs) / len(diffs)
    rng = random.Random(42)
    perms = sum(
        abs(sum(d * rng.choice((1, -1)) for d in diffs) / len(diffs)) >= abs(obs)
        for _ in range(5000)
    )
    return (
        sum(before[c] for c in cases) / len(cases),
        sum(after[c] for c in cases) / len(cases),
        obs,
        perms / 5000,
    )


fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True)
verification: list[str] = []

for ax, arm, colour in ((axes[0], "single", BLUE), (axes[1], "mas", ORANGE)):
    ys = range(len(PAIRS))
    for y, (name, v2, v2b) in zip(ys, PAIRS):
        b, a, delta, p = paired_stats(per_case(v2, arm), per_case(v2b, arm))
        sig = p < 0.05
        ax.plot([b, a], [y, y], color=colour if sig else GREY, lw=3 if sig else 2,
                alpha=1.0 if sig else 0.45, solid_capstyle="round", zorder=1)
        ax.scatter([b], [y], s=70, facecolor="white", edgecolor=GREY, lw=1.6, zorder=3)
        ax.scatter([a], [y], s=90, color=colour if sig else GREY,
                   alpha=1.0 if sig else 0.5, zorder=3)
        ax.annotate(f"{delta:+.3f}" + ("*" if sig else " n.s."),
                    ((b + a) / 2, y + 0.22), ha="center", va="bottom",
                    fontsize=9, color="#333" if sig else GREY)
        verification.append(f"{name:20s} {arm:6s} v2={b:.3f} v2b={a:.3f} d={delta:+.3f} p={p:.4f}")
    ax.axvline(0.520, color="#555", ls="--", lw=1.2, zorder=0)
    ax.set_yticks(list(ys))
    ax.set_ylim(-0.7, len(PAIRS) - 0.3)
    ax.set_title("Single agent" if arm == "single" else "MAS pipeline",
                 fontsize=12, pad=10)
    ax.set_xlabel("pass¹ (agreement with label)")
    ax.set_xlim(0.20, 0.58)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#E6E6E6", lw=0.8)
    ax.set_axisbelow(True)

# Model names go on after the loop: sharey means the second axis's empty
# ticklabels would otherwise clear the first axis's too.
axes[0].set_yticklabels([n for n, _, _ in PAIRS], fontsize=10)
for ax in axes:
    ax.annotate("baseline 0.520", (0.517, -0.45), fontsize=8,
                color="#555", ha="right", va="center", rotation=90)
axes[0].scatter([], [], s=70, facecolor="white", edgecolor=GREY, lw=1.6,
                label="uniform hidden budget (v2)")
axes[0].scatter([], [], s=90, color="#555", label="per-role disclosed budget (v2b)")
axes[0].legend(loc="lower right", frameon=False, fontsize=9)
fig.suptitle("Relieving and disclosing the iteration budget: paired change by model and arm",
             fontsize=13, y=0.98, x=0.02, ha="left")
fig.tight_layout(rect=(0, 0.02, 1, 0.94))
out = Path(__file__).parent / "fig5-budget-track.png"
fig.savefig(out, dpi=300, facecolor="white")
print("\n".join(verification))
print(f"\nwrote {out}")
