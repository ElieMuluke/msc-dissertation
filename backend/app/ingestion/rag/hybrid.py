"""Hybrid BM25 + vector retrieval: lexical index and score fusion.

Regulatory queries often hinge on exact terms of art ("tipping off", "ICRG",
"Recommendation 16") that a small embedding model can blur; BM25 catches those, while
the vector side catches paraphrases. This module supplies the two pure pieces —
:class:`Bm25Index` (lexical scores per chunk id) and :func:`fuse` (weighted min-max
score fusion) — and :class:`RagSystem` wires them to the Chroma store when
``RagConfig.bm25_weight > 0``. Both pieces are framework-free and unit-testable.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class Bm25Index:
    """BM25 index over ``(id, text, metadata)`` chunks, queryable for per-id scores."""

    def __init__(self, ids: Sequence[str], texts: Sequence[str], metadatas: Sequence[dict]) -> None:
        from rank_bm25 import BM25Okapi

        self._ids = list(ids)
        self._metadatas = list(metadatas)
        self._bm25 = BM25Okapi([_tokenize(t) for t in texts]) if ids else None

    def scores(self, query: str, where: Optional[dict] = None, top_n: int = 50) -> dict[str, float]:
        """Top-``top_n`` BM25 scores as ``{chunk_id: score}``, optionally filtered.

        ``where`` is a flat metadata equality filter (same shape RagSystem passes to
        Chroma, e.g. ``{"doc_type": "policy"}``).
        """
        if self._bm25 is None:
            return {}
        raw = self._bm25.get_scores(_tokenize(query))
        pairs = [
            (self._ids[i], float(raw[i]))
            for i in range(len(self._ids))
            if not where or all(self._metadatas[i].get(key) == value for key, value in where.items())
        ]
        pairs.sort(key=lambda p: p[1], reverse=True)
        return dict(pairs[:top_n])


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    """Min-max normalize to [0, 1]; a constant list maps to all-1 (rank carries no info)."""
    if not scores:
        return {}
    low, high = min(scores.values()), max(scores.values())
    if high == low:
        return {k: 1.0 for k in scores}
    return {k: (v - low) / (high - low) for k, v in scores.items()}


def fuse(
    vector_scores: dict[str, float],
    bm25_scores: dict[str, float],
    bm25_weight: float,
    k: int,
) -> list[tuple[str, float]]:
    """Weighted fusion of two score maps over their union; top-``k`` ``(id, score)``.

    Each side is min-max normalized over its own candidate pool first, so BM25's
    unbounded scores and cosine relevances become comparable. Ids absent from one
    side score 0 on that side (standard convention for union-pool score fusion).
    """
    vec = _normalize(vector_scores)
    lex = _normalize(bm25_scores)
    fused = {
        cid: bm25_weight * lex.get(cid, 0.0) + (1.0 - bm25_weight) * vec.get(cid, 0.0)
        for cid in set(vec) | set(lex)
    }
    return sorted(fused.items(), key=lambda p: p[1], reverse=True)[:k]
