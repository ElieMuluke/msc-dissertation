"""RAGAS-based RAG generation evaluation (faithfulness, relevancy, precision, recall).

Wraps the `ragas <https://docs.ragas.io>`_ library rather than reimplementing metrics.
Two layers, kept separate for testability:

- :func:`to_evaluation_dataset` — pure data conversion (records -> ``EvaluationDataset``).
  No model/LLM imports involved, so it is unit-testable offline.
- :func:`run_ragas` — thin wrapper around ``ragas.evaluate`` with the LLM judge and
  embeddings injected by the caller (Dependency Inversion), returning a
  :class:`RagasResult` (mean scores + per-sample rows).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from . import _ragas_compat  # noqa: F401 - side effect: must run before ragas is imported

if TYPE_CHECKING:
    from ragas.dataset_schema import EvaluationDataset
    from ragas.embeddings import BaseRagasEmbeddings
    from ragas.llms import BaseRagasLLM
    from ragas.metrics.base import Metric
    from ragas.run_config import RunConfig


@dataclass(frozen=True)
class RagasRecord:
    """One answered question, ready to be scored by RAGAS.

    Attributes:
        question: The user question (RAGAS calls this ``user_input``).
        answer: The generated answer (``response``).
        contexts: Retrieved context chunks (``retrieved_contexts``).
        reference: Ground-truth answer, required by context_precision/context_recall.
    """

    question: str
    answer: str
    contexts: list[str]
    reference: str


def to_evaluation_dataset(records: Sequence[RagasRecord]) -> "EvaluationDataset":
    """Convert :class:`RagasRecord` rows into a ``ragas.EvaluationDataset``.

    Pure data mapping — imports only ``ragas``'s dataset schema, not any LLM/embedding
    backend, so this is safe to unit-test without Ollama or HuggingFace models.
    """
    from ragas import EvaluationDataset, SingleTurnSample

    samples = [
        SingleTurnSample(
            user_input=record.question,
            response=record.answer,
            retrieved_contexts=list(record.contexts),
            reference=record.reference,
        )
        for record in records
    ]
    return EvaluationDataset(samples=samples)


def default_metrics() -> list["Metric"]:
    """The default RAGAS quartet: faithfulness, answer relevancy, context precision/recall."""
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    return [faithfulness, answer_relevancy, context_precision, context_recall]


def _sanitize_metric_name(name: str) -> str:
    """Make a metric name safe as an MLflow metric key (MLflow disallows e.g. ``@``)."""
    return "".join(c if (c.isalnum() or c in "_-. /") else "_" for c in name)


@dataclass(frozen=True)
class RagasResult:
    """Outcome of a RAGAS run: mean scores plus the raw per-sample rows."""

    mean_scores: dict[str, float]
    sample_scores: list[dict[str, float]]


def run_ragas(
    dataset: "EvaluationDataset",
    *,
    llm: "BaseRagasLLM",
    embeddings: "BaseRagasEmbeddings",
    metrics: Optional[list["Metric"]] = None,
    run_config: "Optional[RunConfig]" = None,
) -> RagasResult:
    """Run ``ragas.evaluate`` once with injected llm/embeddings.

    The llm and embeddings are passed by the caller (Dependency Inversion) so this
    function never hardcodes a model backend; ``ragas_run.py`` wires the local Ollama
    LLM and HuggingFace embeddings, but tests can inject fakes.

    ``run_config`` defaults to ``max_workers=1`` with a generous per-job timeout: a local
    CPU-only Ollama serves one request at a time, so running metric jobs concurrently makes
    them starve each other and hit the timeout. Serializing them keeps each call fast.

    Returns:
        A :class:`RagasResult` with mean scores (sanitized for ``mlflow.log_metrics``)
        and the raw per-sample score rows (for an MLflow artifact).
    """
    from ragas import evaluate
    from ragas.run_config import RunConfig

    result = evaluate(
        dataset=dataset,
        metrics=metrics or default_metrics(),
        llm=llm,
        embeddings=embeddings,
        run_config=run_config or RunConfig(max_workers=1, timeout=600),
    )
    mean_scores = {_sanitize_metric_name(name): float(value) for name, value in result._repr_dict.items()}
    return RagasResult(mean_scores=mean_scores, sample_scores=list(result.scores))
