"""Evaluation pipeline for the RAG system.

Owns evaluation datasets, metrics, and runners, and logs results to a local MLflow
tracking server for visualization. Retrieval is scored in-repo (see :mod:`runner`);
generation quality is scored via the `ragas <https://docs.ragas.io>`_ library
(see :mod:`ragas_eval`) rather than a from-scratch implementation.
"""

from __future__ import annotations

from .dataset import QueryExample, load_queries
from .ragas_eval import RagasRecord, RagasResult, run_ragas, to_evaluation_dataset
from .runner import evaluate

__all__ = [
    "QueryExample",
    "load_queries",
    "evaluate",
    "RagasRecord",
    "RagasResult",
    "to_evaluation_dataset",
    "run_ragas",
]
