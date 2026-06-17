"""Run a retrieval evaluation and aggregate metrics across queries.

``evaluate`` depends only on a ``search_fn(query) -> ranked list of ids``, so it is
independent of the RAG implementation and unit-testable with a fake searcher.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .dataset import QueryExample
from .metrics import (
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

SearchFn = Callable[[str], Sequence[str]]


def evaluate(search_fn: SearchFn, queries: Sequence[QueryExample], k: int = 5) -> dict[str, float]:
    """Return mean retrieval metrics over ``queries`` (empty -> zeros)."""
    n = len(queries)
    if n == 0:
        return {f"precision@{k}": 0.0, f"recall@{k}": 0.0, "mrr": 0.0, f"ndcg@{k}": 0.0, f"hit_rate@{k}": 0.0}

    totals = {f"precision@{k}": 0.0, f"recall@{k}": 0.0, "mrr": 0.0, f"ndcg@{k}": 0.0, f"hit_rate@{k}": 0.0}
    for example in queries:
        retrieved = list(search_fn(example.query))
        relevant = example.relevant_ids
        totals[f"precision@{k}"] += precision_at_k(retrieved, relevant, k)
        totals[f"recall@{k}"] += recall_at_k(retrieved, relevant, k)
        totals["mrr"] += reciprocal_rank(retrieved, relevant)
        totals[f"ndcg@{k}"] += ndcg_at_k(retrieved, relevant, k)
        totals[f"hit_rate@{k}"] += hit_rate_at_k(retrieved, relevant, k)

    return {name: value / n for name, value in totals.items()}
