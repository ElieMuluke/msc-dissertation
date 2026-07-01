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

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from . import _ragas_compat  # noqa: F401 - side effect: must run before ragas is imported

if TYPE_CHECKING:
    from ragas.dataset_schema import EvaluationDataset, MultiTurnSample
    from ragas.embeddings import BaseRagasEmbeddings
    from ragas.llms import BaseRagasLLM
    from ragas.metrics.base import Metric
    from ragas.run_config import RunConfig

logger = logging.getLogger(__name__)

# The KYC/AML domain scope the compliance agent is expected to stay within. Used as the
# ``reference_topics`` for RAGAS TopicAdherenceScore: answers on these topics count toward
# adherence, answers on anything else count against it (the agent should refuse/deflect).
REFERENCE_TOPICS: list[str] = [
    "customer due diligence (CDD) and identity verification",
    "enhanced due diligence (EDD)",
    "simplified due diligence (SDD)",
    "politically exposed persons (PEPs)",
    "beneficial ownership and ownership/control structure",
    "suspicious transaction and activity reporting (SARs/STRs)",
    "tipping off and prejudicing an investigation",
    "record keeping and retention",
    "sanctions screening and targeted financial sanctions",
    "proliferation financing",
    "wire transfers and the travel rule",
    "correspondent banking relationships",
    "the risk-based approach to AML/CFT",
    "high-risk jurisdictions and countermeasures",
    "ongoing monitoring of business relationships",
    "reliance on third parties for CDD",
    "virtual assets and virtual asset service providers (VASPs)",
    "AML/CFT internal controls, governance and the compliance officer",
    "the FATF Recommendations and mutual evaluation methodology",
    "JMLSG guidance and the UK Money Laundering Regulations",
]


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


def to_topic_adherence_sample(
    question: str,
    answer: str,
    reference_topics: Optional[Sequence[str]] = None,
) -> "MultiTurnSample":
    """Wrap one question/answer turn as a ``MultiTurnSample`` for TopicAdherenceScore.

    TopicAdherenceScore is a multi-turn metric: it reads the human turn(s) to extract the
    topics asked about, checks whether the AI answered or refused each, and classifies each
    topic against ``reference_topics``. A single Q/A is represented as a one-round
    conversation. ``reference_topics`` defaults to :data:`REFERENCE_TOPICS` (the AML scope).
    """
    from ragas.dataset_schema import MultiTurnSample
    from ragas.messages import AIMessage, HumanMessage

    return MultiTurnSample(
        user_input=[HumanMessage(content=question), AIMessage(content=answer)],
        reference_topics=list(reference_topics if reference_topics is not None else REFERENCE_TOPICS),
    )


def topic_adherence_metrics(
    modes: Sequence[str] = ("precision", "recall", "f1"),
) -> list["Metric"]:
    """Build one TopicAdherenceScore per mode, each renamed ``topic_adherence_<mode>``.

    RAGAS's TopicAdherenceScore returns a single figure chosen by its ``mode`` (precision,
    recall or f1). To emit all three per query we instantiate one metric per mode and give
    each a distinct name so they land in separate output columns.
    """
    from ragas.metrics import TopicAdherenceScore

    metrics: list["Metric"] = []
    for mode in modes:
        metric = TopicAdherenceScore(mode=mode)  # type: ignore[arg-type]
        metric.name = f"topic_adherence_{mode}"
        metrics.append(metric)
    return metrics


def _sanitize_metric_name(name: str) -> str:
    """Make a metric name safe as an MLflow metric key (MLflow disallows e.g. ``@``)."""
    return "".join(c if (c.isalnum() or c in "_-. /") else "_" for c in name)


@dataclass(frozen=True)
class RagasResult:
    """Outcome of a RAGAS run: mean scores, per-sample rows, and NaN counts per metric.

    Attributes:
        mean_scores: Mean of each metric over the valid (non-NaN) samples, keyed by a
            metric name sanitized for ``mlflow.log_metrics``.
        sample_scores: The full per-sample table (one dict per query) including inputs and
            every metric column, so individual failure cases can be inspected.
        nan_counts: Number of NaN scores per metric — a non-zero count flags malformed
            input or a judge parsing failure that would otherwise be averaged away.
    """

    mean_scores: dict[str, float]
    sample_scores: list[dict[str, object]]
    nan_counts: dict[str, int]


def _summarize(result_df, metric_names: Sequence[str]) -> RagasResult:
    """Turn a RAGAS ``to_pandas()`` frame into a :class:`RagasResult`.

    Uses the public ``to_pandas()`` API (not private attributes). Means are computed over
    non-NaN samples; any NaN is counted and warned about rather than silently averaged in.
    """
    mean_scores: dict[str, float] = {}
    nan_counts: dict[str, int] = {}
    for name in metric_names:
        if name not in result_df.columns:
            logger.warning("Metric %s missing from RAGAS output columns", name)
            continue
        column = result_df[name]
        n_nan = int(column.isna().sum())
        nan_counts[_sanitize_metric_name(name)] = n_nan
        if n_nan:
            logger.warning(
                "Metric %s produced %d NaN score(s) out of %d samples "
                "(malformed input or judge parse failure); excluded from the mean.",
                name,
                n_nan,
                len(column),
            )
        mean = column.mean(skipna=True)
        mean_scores[_sanitize_metric_name(name)] = float(mean) if not math.isnan(mean) else float("nan")

    sample_scores = result_df.to_dict(orient="records")
    return RagasResult(mean_scores=mean_scores, sample_scores=sample_scores, nan_counts=nan_counts)


def run_ragas(
    dataset: "EvaluationDataset",
    *,
    llm: "BaseRagasLLM",
    embeddings: "Optional[BaseRagasEmbeddings]" = None,
    metrics: Optional[list["Metric"]] = None,
    run_config: "Optional[RunConfig]" = None,
) -> RagasResult:
    """Run ``ragas.evaluate`` once with an injected llm (and optional embeddings).

    The llm and embeddings are passed by the caller (Dependency Inversion) so this
    function never hardcodes a model backend; ``ragas_run.py`` wires the local Ollama
    LLM and HuggingFace embeddings, but tests can inject fakes. ``embeddings`` is optional
    because some metrics (e.g. TopicAdherenceScore) do not need them.

    ``run_config`` defaults to ``max_workers=1`` with a generous per-job timeout: a local
    CPU-only Ollama serves one request at a time, so running metric jobs concurrently makes
    them starve each other and hit the timeout. Serializing them keeps each call fast.

    Returns:
        A :class:`RagasResult` with mean scores, the full per-sample table, and per-metric
        NaN counts, all derived from the public ``to_pandas()`` API.
    """
    from ragas import evaluate
    from ragas.run_config import RunConfig

    chosen_metrics = metrics or default_metrics()
    result = evaluate(
        dataset=dataset,
        metrics=chosen_metrics,
        llm=llm,
        embeddings=embeddings,
        run_config=run_config or RunConfig(max_workers=1, timeout=600),
    )
    metric_names = [m.name for m in chosen_metrics]
    return _summarize(result.to_pandas(), metric_names)
