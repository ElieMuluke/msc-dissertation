"""Pre-registered metrics, computed from the journal alone (PRD-A tier table).

All functions are pure and operate on decisions / trajectories grouped per
case, so they can be unit-tested on synthetic journals. Outcome categories
are the three decisions plus ``malformed``; malformed runs are never
excluded — they count as disagreements and as failures against the label.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Iterable, Sequence

from experiments.config import OUTCOMES


@dataclass
class CaseRuns:
    """All repeats of one case under one (arm, condition)."""

    case_id: str
    decisions: list[str] = field(default_factory=list)
    trajectories: list[list[str]] = field(default_factory=list)
    prompt_tokens: list[int] = field(default_factory=list)
    completion_tokens: list[int] = field(default_factory=list)
    wall_clock_s: list[float] = field(default_factory=list)


def group_case_runs(records: Iterable[dict[str, Any]], arm: str, condition: str) -> dict[str, CaseRuns]:
    """Group journal records for one arm × condition, ordered by repeat_idx."""
    selected = sorted(
        (r for r in records if r["arm"] == arm and r["condition"] == condition),
        key=lambda r: (r["case_id"], r["repeat_idx"]),
    )
    groups: dict[str, CaseRuns] = {}
    for r in selected:
        g = groups.setdefault(r["case_id"], CaseRuns(r["case_id"]))
        g.decisions.append(r["decision"])
        g.trajectories.append(list(r.get("tool_calls", [])))
        g.prompt_tokens.append(int(r.get("prompt_tokens", 0)))
        g.completion_tokens.append(int(r.get("completion_tokens", 0)))
        g.wall_clock_s.append(float(r.get("wall_clock_s", 0.0)))
    return groups


# --- Tier 1 -----------------------------------------------------------------

def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k: probability that k runs drawn without replacement all agree
    with the benchmark label, given c of n observed runs agree.

    ``C(c, k) / C(n, k)``; 0 when c < k. Framed as agreement with the
    benchmark authors' labels, never "correctness".
    """
    if k > n:
        raise ValueError(f"k={k} exceeds n={n}")
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def case_pass_hat_k(decisions: Sequence[str], label: str, k: int) -> float:
    c = sum(1 for d in decisions if d == label)
    return pass_hat_k(len(decisions), c, k)


def decision_agreement_rate(decisions: Sequence[str]) -> float:
    """DAR: fraction of unordered repeat pairs with identical decisions."""
    if len(decisions) < 2:
        raise ValueError("DAR needs at least 2 repeats")
    pairs = list(combinations(decisions, 2))
    return sum(a == b for a, b in pairs) / len(pairs)


def flipped(decisions: Sequence[str]) -> bool:
    """True if the case produced at least one divergent verdict."""
    return len(set(decisions)) > 1


def krippendorff_alpha(units: Sequence[Sequence[str]]) -> float | None:
    """Krippendorff's alpha (nominal): cases are units, repeats are coders.

    Returns ``None`` when undefined (fewer than 2 pairable values overall);
    1.0 when there is no expected disagreement (every value identical).
    """
    coincidences: Counter[tuple[str, str]] = Counter()
    for unit in units:
        m = len(unit)
        if m < 2:
            continue
        for i, a in enumerate(unit):
            for j, b in enumerate(unit):
                if i != j:
                    coincidences[(a, b)] += 1.0 / (m - 1)
    n_c: Counter[str] = Counter()
    for (a, _b), w in coincidences.items():
        n_c[a] += w
    n = sum(n_c.values())
    if n <= 1:
        return None
    d_o = sum(w for (a, b), w in coincidences.items() if a != b)
    d_e = sum(n_c[a] * n_c[b] for a in n_c for b in n_c if a != b) / (n - 1)
    if d_e == 0:
        return 1.0
    return 1.0 - d_o / d_e


# --- Tier 2 -----------------------------------------------------------------

def majority_vote(decisions: Sequence[str]) -> tuple[str, bool]:
    """Modal decision; ties broken by canonical OUTCOMES order (flagged)."""
    counts = Counter(decisions)
    top = max(counts.values())
    winners = [o for o in OUTCOMES if counts.get(o, 0) == top]
    return winners[0], len(winners) > 1


def normalised_entropy(decisions: Sequence[str]) -> float:
    """Shannon entropy of the outcome distribution, normalised by
    ``log2(len(OUTCOMES))`` (4 categories: 3 decisions + malformed)."""
    counts = Counter(decisions)
    total = sum(counts.values())
    h = -sum((c / total) * math.log2(c / total) for c in counts.values() if c)
    return h / math.log2(len(OUTCOMES))


def _lcs_len(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def _pairwise_mean(items: Sequence[Any], score) -> float:
    pairs = list(combinations(items, 2))
    if not pairs:
        raise ValueError("need at least 2 trajectories")
    return sum(score(a, b) for a, b in pairs) / len(pairs)


def trajectory_agreement_rate(trajectories: Sequence[Sequence[str]]) -> float:
    """TAR: fraction of repeat pairs with identical ordered tool-name lists."""
    return _pairwise_mean(trajectories, lambda a, b: float(list(a) == list(b)))


def trajectory_jaccard(trajectories: Sequence[Sequence[str]]) -> float:
    """Mean pairwise Jaccard similarity of tool-name sets (∅,∅ → 1)."""
    def jac(a: Sequence[str], b: Sequence[str]) -> float:
        sa, sb = set(a), set(b)
        if not sa and not sb:
            return 1.0
        return len(sa & sb) / len(sa | sb)
    return _pairwise_mean(trajectories, jac)


def trajectory_nlcs(trajectories: Sequence[Sequence[str]]) -> float:
    """Mean pairwise LCS length normalised by the longer sequence (∅,∅ → 1)."""
    def nlcs(a: Sequence[str], b: Sequence[str]) -> float:
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return _lcs_len(a, b) / max(len(a), len(b))
    return _pairwise_mean(trajectories, nlcs)


# --- Aggregation -------------------------------------------------------------

def condition_summary(
    groups: dict[str, CaseRuns],
    labels: dict[str, str],
    pass_ks: Sequence[int] = (1, 5, 15),
) -> dict[str, Any]:
    """The full tier table for one arm × condition (means over cases).

    ``pass^k`` and ``tokens_per_pass^k`` are reported at every k in
    ``pass_ks`` that the condition's repeat count supports, plus k=n —
    all-k reporting was pre-registered 2026-08-06, before any results,
    to avoid a post-hoc k choice.
    """
    if not groups:
        return {"cases": 0}
    cases = sorted(groups)
    decisions_by_case = [groups[c].decisions for c in cases]
    n_repeats = min(len(d) for d in decisions_by_case)
    summary: dict[str, Any] = {"cases": len(cases), "repeats": n_repeats}
    ks = sorted({k for k in pass_ks if k <= n_repeats} | {n_repeats})
    for k in ks:
        summary[f"pass^{k}"] = _mean(
            [case_pass_hat_k(groups[c].decisions, labels[c], k) for c in cases]
        )
    summary["DAR"] = _mean([decision_agreement_rate(d) for d in decisions_by_case])
    summary["krippendorff_alpha"] = krippendorff_alpha(decisions_by_case)
    summary["flip_rate"] = _mean([float(flipped(d)) for d in decisions_by_case])
    majority = [majority_vote(groups[c].decisions) for c in cases]
    summary["majority_vote_accuracy"] = _mean(
        [float(m[0] == labels[c]) for m, c in zip(majority, cases)]
    )
    summary["majority_ties"] = sum(1 for m in majority if m[1])
    entropies = {c: normalised_entropy(groups[c].decisions) for c in cases}
    summary["mean_entropy"] = _mean(list(entropies.values()))
    summary["worst_entropy_cases"] = sorted(
        entropies, key=lambda c: (-entropies[c], c)
    )[:3]
    summary["per_case_entropy"] = entropies
    summary["TAR"] = _mean([trajectory_agreement_rate(groups[c].trajectories) for c in cases])
    summary["jaccard"] = _mean([trajectory_jaccard(groups[c].trajectories) for c in cases])
    summary["nLCS"] = _mean([trajectory_nlcs(groups[c].trajectories) for c in cases])
    total_tokens = [
        pt + ct
        for c in cases
        for pt, ct in zip(groups[c].prompt_tokens, groups[c].completion_tokens)
    ]
    summary["tokens_per_run"] = _mean([float(t) for t in total_tokens])
    summary["malformed_rate"] = _mean(
        [sum(d == "malformed" for d in ds) / len(ds) for ds in decisions_by_case]
    )
    summary["mean_wall_clock_s"] = _mean(
        [w for c in cases for w in groups[c].wall_clock_s]
    )
    for k in ks:
        pass_k = summary[f"pass^{k}"]
        summary[f"tokens_per_pass^{k}"] = (
            summary["tokens_per_run"] / pass_k if pass_k else None
        )
    return summary


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)
