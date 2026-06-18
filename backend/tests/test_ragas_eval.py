"""Unit tests for the pure RAGAS dataset-conversion helper (no LLM, no Ollama).

`ragas.evaluate` itself is not exercised here: it needs a live LLM judge and is slow.
Only the data-mapping logic (:func:`to_evaluation_dataset`) is tested, offline.
"""

from __future__ import annotations

from app.evaluation.ragas_eval import RagasRecord, default_metrics, to_evaluation_dataset


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
