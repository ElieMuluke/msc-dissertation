"""Evaluation pipeline for the RAG system.

Owns evaluation datasets, metrics, and runners, and logs results to a local MLflow
tracking server for visualization. Retrieval is scored in-repo (see :mod:`runner`);
generation quality is scored via the `ragas <https://docs.ragas.io>`_ library
(see :mod:`ragas_eval`) rather than a from-scratch implementation.
"""

from __future__ import annotations

from .dataset import QueryExample, load_queries
from .ragas_eval import (
    REFERENCE_TOPICS,
    RagasRecord,
    RagasResult,
    default_metrics,
    run_ragas,
    to_evaluation_dataset,
    to_topic_adherence_sample,
    topic_adherence_metrics,
)
from .runner import evaluate

__all__ = [
    "QueryExample",
    "load_queries",
    "evaluate",
    "RagasRecord",
    "RagasResult",
    "REFERENCE_TOPICS",
    "default_metrics",
    "to_evaluation_dataset",
    "to_topic_adherence_sample",
    "topic_adherence_metrics",
    "run_ragas",
]
