"""Uncertainty for the arm comparison: bootstrap CI over cases and a paired
permutation (sign-flip) test on the per-case arm difference.

Cases are the resampling unit throughout (repeats within a case are not
independent). Both procedures are seeded for reproducibility.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def bootstrap_ci_mean(
    values: Sequence[float],
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of per-case values."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        raise ValueError("no values to bootstrap")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
    means = arr[idx].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def paired_permutation_pvalue(
    diffs: Sequence[float],
    n_perm: int = 10_000,
    seed: int = 0,
) -> float:
    """Two-sided sign-flip permutation p-value for mean(diffs) == 0.

    ``diffs`` are per-case A−B differences (cases paired across arms).
    """
    arr = np.asarray(diffs, dtype=float)
    if arr.size == 0:
        raise ValueError("no paired differences")
    observed = abs(arr.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, arr.size))
    permuted = np.abs((signs * arr).mean(axis=1))
    # add-one smoothing: the observed permutation counts itself
    return float((np.sum(permuted >= observed - 1e-12) + 1) / (n_perm + 1))
