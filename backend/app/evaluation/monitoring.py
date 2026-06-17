"""Live monitoring of real searches to MLflow.

Each `/rag/search` call is logged as a run in the ``rag-search-monitoring`` experiment of
the same local MLflow store used by offline evaluation. View with
``mlflow ui --backend-store-uri sqlite:///mlflow.db`` from ``backend/``.

Logging is best-effort: a monitoring failure never affects the search response.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import mlflow

from app.ingestion.rag import SearchResult

_DB_PATH = Path(__file__).resolve().parents[2] / "mlflow.db"
_EXPERIMENT = "rag-search-monitoring"
_configured = False


def search_metrics(results: Sequence[SearchResult], k: int, latency_ms: float) -> dict[str, float]:
    """Metrics describing one search (pure, no I/O)."""
    scores = [r.score for r in results]
    return {
        "k": float(k),
        "n_results": float(len(results)),
        "latency_ms": latency_ms,
        "top_score": max(scores) if scores else 0.0,
        "mean_score": sum(scores) / len(scores) if scores else 0.0,
    }


def _configure() -> None:
    global _configured
    if not _configured:
        mlflow.set_tracking_uri(f"sqlite:///{_DB_PATH}")
        _configured = True


def log_search(
    query: str,
    k: int,
    doc_type: str | None,
    results: Sequence[SearchResult],
    latency_ms: float,
) -> None:
    """Log one search to MLflow. Best-effort: never raises."""
    try:
        _configure()
        mlflow.set_experiment(_EXPERIMENT)
        with mlflow.start_run():
            mlflow.set_tags({"query": query[:250], "doc_type": doc_type or "all"})
            mlflow.log_metrics(search_metrics(results, k, latency_ms))
    except Exception:  # noqa: BLE001 - monitoring must not break search
        pass
