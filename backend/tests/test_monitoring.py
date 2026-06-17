"""Unit tests for live-search monitoring metrics (pure, no MLflow I/O)."""

from __future__ import annotations

from app.evaluation.monitoring import search_metrics
from app.ingestion.rag.models import DocumentType, SearchResult


def _result(score):
    return SearchResult("id", "text", DocumentType.POLICY, {}, score)


def test_search_metrics_with_results():
    m = search_metrics([_result(0.9), _result(0.5)], k=5, latency_ms=12.5)
    assert m == {
        "k": 5.0,
        "n_results": 2.0,
        "latency_ms": 12.5,
        "top_score": 0.9,
        "mean_score": 0.7,
    }


def test_search_metrics_empty():
    m = search_metrics([], k=3, latency_ms=4.0)
    assert m["n_results"] == 0.0
    assert m["top_score"] == 0.0
    assert m["mean_score"] == 0.0
