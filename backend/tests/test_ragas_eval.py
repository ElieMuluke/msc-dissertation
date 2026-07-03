"""Unit tests for the pure RAGAS dataset-conversion helper (no LLM, no Ollama).

`ragas.evaluate` itself is not exercised here: it needs a live LLM judge and is slow.
Only the data-mapping logic (:func:`to_evaluation_dataset`) is tested, offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import pandas as pd

from app.evaluation.ragas_eval import RagasRecord, default_metrics, run_ragas, to_evaluation_dataset
from app.generation.config import GenerationConfig


def test_to_evaluation_dataset_maps_fields():
    records = [
        RagasRecord(
            question="What is the threshold?",
            answer="10,000 USD.",
            contexts=["Report cash over 10,000 USD.", "Other context."],
            reference="The threshold is 10,000 USD.",
        ),
        RagasRecord(
            question="Who needs EDD?",
            answer="PEPs.",
            contexts=["EDD applies to PEPs."],
            reference="Politically exposed persons.",
        ),
    ]

    dataset = to_evaluation_dataset(records)
    samples = list(dataset)

    assert len(samples) == 2
    assert samples[0].user_input == "What is the threshold?"
    assert samples[0].response == "10,000 USD."
    assert samples[0].retrieved_contexts == ["Report cash over 10,000 USD.", "Other context."]
    assert samples[0].reference == "The threshold is 10,000 USD."
    assert samples[1].user_input == "Who needs EDD?"
    assert samples[1].retrieved_contexts == ["EDD applies to PEPs."]


def test_to_evaluation_dataset_empty():
    dataset = to_evaluation_dataset([])
    assert list(dataset) == []


def test_default_metrics_returns_the_ragas_quartet():
    metrics = default_metrics()
    names = {m.name for m in metrics}
    assert names == {"faithfulness", "answer_relevancy", "context_precision", "context_recall"}


@dataclass
class _FakeModeMetric:
    """Minimal stand-in for a metric that structurally satisfies ragas's ``ModeMetric``
    protocol (has both ``name`` and ``mode``), e.g. ``TopicAdherenceScore``."""

    name: str
    mode: str


def test_run_ragas_renames_mode_metric_columns_back_to_plain_name():
    """Regression test: ragas.evaluate() writes ModeMetric results under a mangled
    column name (``"<name>(mode=<mode>)"``), which previously made ``run_ragas`` report
    the metric as entirely missing even though every sample scored fine."""
    metric = _FakeModeMetric(name="topic_adherence_precision", mode="precision")
    fake_df = pd.DataFrame({"topic_adherence_precision(mode=precision)": [1.0, 0.0, 0.5]})

    class _FakeEvaluationResult:
        def to_pandas(self):
            return fake_df

    with patch("ragas.evaluate", return_value=_FakeEvaluationResult()) as mock_evaluate:
        result = run_ragas(
            to_evaluation_dataset([]),
            llm=object(),
            metrics=[metric],
        )

    mock_evaluate.assert_called_once()
    assert result.mean_scores["topic_adherence_precision"] == 0.5
    assert result.nan_counts["topic_adherence_precision"] == 0
    assert result.sample_scores[0]["topic_adherence_precision"] == 1.0


def test_build_ragas_llm_shares_one_cache_across_topic_adherence_modes():
    """Regression: topic_adherence_metrics() creates one TopicAdherenceScore per mode
    (precision/recall/f1), each independently re-invoking the judge LLM for the same
    query. Without a shared cache the three modes can disagree with each other (observed
    in a 2026-07 run: ~16% of queries had a reported F1 inconsistent with the harmonic
    mean of that row's own precision/recall). The judge LLM must be built with a cache so
    identical prompts resolve once and get reused by every mode."""
    from app.evaluation.ragas_run import _build_ragas_llm

    config = GenerationConfig()
    llm, _ = _build_ragas_llm(config)

    assert llm.cache is not None
    llm.cache.set("k", "v")
    assert llm.cache.has_key("k")
    assert llm.cache.get("k") == "v"
