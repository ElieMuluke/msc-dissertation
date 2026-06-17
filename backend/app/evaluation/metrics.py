"""Information-retrieval metrics for evaluating RAG retrieval quality.

All metrics operate on ranked lists of document ids vs. a set of relevant ids, so they
are independent of the embedding model or vector store. Binary relevance is assumed.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def _hits(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> int:
    relevant = set(relevant)
    return sum(1 for doc_id in retrieved[:k] if doc_id in relevant)


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of the top-k that are relevant."""
    return _hits(retrieved, relevant, k) / k if k else 0.0


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of relevant documents found in the top-k."""
    relevant = set(relevant)
    return _hits(retrieved, relevant, k) / len(relevant) if relevant else 0.0


def reciprocal_rank(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """1 / rank of the first relevant document (0 if none retrieved)."""
    relevant = set(relevant)
    for index, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (index + 1)
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Normalized discounted cumulative gain over the top-k (binary relevance)."""
    relevant = set(relevant)
    dcg = sum(
        1.0 / math.log2(index + 2)
        for index, doc_id in enumerate(retrieved[:k])
        if doc_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    return dcg / idcg if idcg else 0.0


def hit_rate_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """1.0 if any relevant document is in the top-k, else 0.0."""
    return 1.0 if _hits(retrieved, relevant, k) > 0 else 0.0
