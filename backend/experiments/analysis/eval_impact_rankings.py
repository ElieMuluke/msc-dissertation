"""Corrected cross-sweep rankings after the deepseek-r1 / granite4.1 defects.

Read-only. Parses each sealed sweep's committed analysis-report.md Tier-1 table
(t07-varied rows) and prints the label-agreement ranking three ways:
  (1) as committed (all sweeps),
  (2) with deepseek-r1:14b@think excluded (defect A: tool channel dead, 0/2300
      tool calls -> different task; trajectory tier vacuous),
  (3) additionally flagging granite4.1:8b as degenerate (defect B: 85.6-86.9%
      `investigate`, every cell below the constant-dismiss baseline 0.520).

No LLM calls, no GPU, no network. Run from backend/:
    .venv/bin/python experiments/analysis/eval_impact_rankings.py
"""

from __future__ import annotations

import re
from pathlib import Path

EXPERIMENTS = Path(__file__).resolve().parents[1]

# sweep dir -> (label, defect flag)
SWEEPS = {
    "results-qwen3.5-9b-thinking": ("qwen3.5:9b (ctx1)", None),
    "results-qwen2.5-7b": ("qwen2.5:7b (ctx1)", None),
    "results-qwen2.5-14b": ("qwen2.5:14b (ctx1)", None),
    "results-gemma4": ("gemma4 (ctx2)", None),
    "results-qwen3.5-9b-ollama0326": ("qwen3.5:9b (ctx2)", None),
    "results-qwen2.5-7b-ollama0326": ("qwen2.5:7b (ctx2)", None),
    "results-qwen2.5-14b-ollama0326": ("qwen2.5:14b (ctx2)", None),
    "results-lfm2.5-8b-thinking": ("lfm2.5:8b@think (ctx3)", None),
    "results-qwen3.5-9b-thinking-budget": ("qwen3.5:9b@think-budget (ctx3)", None),
    "results-deepseek-r1-14b-thinking": (
        "deepseek-r1:14b@think (ctx3)",
        "DEFECT A: 0/2300 tool calls; tool-free task variant; EXCLUDE",
    ),
    "results-granite4.1-8b": (
        "granite4.1:8b (ctx3)",
        "DEFECT B: mode collapse (86% investigate); below 0.520 baseline; FLAG",
    ),
}

ROW = re.compile(
    r"^\|\s*(single|mas)\s*\|\s*t07-varied\s*\|\s*50\s*\|\s*15\s*\|"
    r"\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|"
    r"\s*([0-9.]+)\s*\|\s*(-?[0-9.]+)\s*\|"
)

BASELINE_DISMISS = 0.520  # 26/50 primary labels are dismiss


def main() -> None:
    rows = []
    for d, (label, defect) in SWEEPS.items():
        report = EXPERIMENTS / d / "analysis-report.md"
        if not report.exists():
            # fall back: qwen3.5 ctx1 lives in results/ historically
            alt = EXPERIMENTS / "results" / "analysis-report.md"
            report = alt if "qwen3.5-9b-thinking" in d and alt.exists() else report
        if not report.exists():
            print(f"  [missing] {d}")
            continue
        seen = {}
        for line in report.read_text().splitlines():
            m = ROW.match(line)
            if m and m.group(1) not in seen:
                arm, p1, p5, p15, dar, alpha = m.groups()
                seen[arm] = (float(p1), float(dar), float(alpha))
        if seen:
            rows.append((label, defect, seen))

    print("\n== t07-varied pass^1 (single | mas), DAR, alpha — all sweeps ==")
    for label, defect, seen in sorted(
        rows, key=lambda r: -max(v[0] for v in r[2].values())
    ):
        s = seen.get("single", (float("nan"),) * 3)
        m = seen.get("mas", (float("nan"),) * 3)
        flag = f"  <-- {defect}" if defect else ""
        below = (
            " [below always-dismiss 0.520]"
            if max(s[0], m[0]) < BASELINE_DISMISS and defect
            else ""
        )
        print(
            f"  pass^1 {s[0]:.3f}|{m[0]:.3f}  DAR {s[1]:.3f}|{m[1]:.3f}  "
            f"alpha {s[2]:.3f}|{m[2]:.3f}  {label}{below}{flag}"
        )

    valid = [r for r in rows if r[1] is None]
    best = max(valid, key=lambda r: max(v[0] for v in r[2].values()))
    best_arm = max(best[2], key=lambda a: best[2][a][0])
    print(
        f"\n== corrected best label agreement (defective sweeps excluded) ==\n"
        f"  {best[0]} {best_arm} pass^1 = {best[2][best_arm][0]:.3f}"
    )
    print(
        "  (deepseek-r1:14b@think single 0.628 is struck: model never saw tools;"
        " 2,300/2,300 runs made zero tool calls — not the same task.)"
    )


if __name__ == "__main__":
    main()
