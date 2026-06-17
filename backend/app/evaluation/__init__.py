"""Evaluation pipeline for the RAG system.

Owns evaluation datasets, metrics, and runners. Metrics are computed in-repo
(dissertation-defensible) and logged to a local MLflow tracking server for visualization.
This package grows as each new feature gets its own evaluation.
"""

from __future__ import annotations

from .dataset import QueryExample, load_queries
from .runner import evaluate

__all__ = ["QueryExample", "load_queries", "evaluate"]
