"""Unit tests for retrieval metrics and the evaluation runner (pure, no model/store)."""

from __future__ import annotations

import math

from app.evaluation.dataset import QueryExample
from app.evaluation.metrics import (
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.runner import evaluate


def test_precision_and_recall():
    retrieved = ["a", "x", "b", "y"]
    relevant = {"a", "b", "c"}
    assert precision_at_k(retrieved, relevant, 4) == 0.5  # 2 of 4
    assert recall_at_k(retrieved, relevant, 4) == 2 / 3   # 2 of 3 relevant


def test_reciprocal_rank():
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == 1 / 3
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_ndcg_perfect_and_partial():
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 2) == 1.0
    expected = (1 / math.log2(2) + 1 / math.log2(4)) / (1 / math.log2(2) + 1 / math.log2(3))
    assert ndcg_at_k(["a", "x", "c"], {"a", "c"}, 3) == expected


def test_hit_rate():
    assert hit_rate_at_k(["x", "a"], {"a"}, 2) == 1.0
    assert hit_rate_at_k(["x", "a"], {"a"}, 1) == 0.0


def test_evaluate_aggregates_means():
    queries = [
        QueryExample("q1", frozenset({"a"})),
        QueryExample("q2", frozenset({"b"})),
    ]
    # q1: relevant at rank 1; q2: relevant at rank 2.
    rankings = {"q1": ["a", "z"], "q2": ["z", "b"]}
    metrics = evaluate(lambda q: rankings[q], queries, k=2)
    assert metrics["mrr"] == (1.0 + 0.5) / 2
    assert metrics["hit_rate@2"] == 1.0
    assert metrics["recall@2"] == 1.0


def test_evaluate_empty():
    assert evaluate(lambda q: [], [], k=5)["mrr"] == 0.0
