"""Evaluation pipeline for the RAG system.

Owns evaluation datasets, metrics, and runners. Metrics are computed in-repo
(dissertation-defensible) and logged to a local MLflow tracking server for visualization.
This package grows as each new feature gets its own evaluation.
"""

from __future__ import annotations

from .dataset import QueryExample, load_queries
from .runner import evaluate
from .triad import TriadRecord, evaluate_triad, make_llm_judge

__all__ = [
    "QueryExample",
    "load_queries",
    "evaluate",
    "TriadRecord",
    "evaluate_triad",
    "make_llm_judge",
]
