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


def test_default_metrics_hardens_context_recall_judge_prompt_idempotently():
    """Regression (2026-07-07 diagnosis): small judges hedge with 0.5 verdicts and demand
    exact-phrase matches. The context_recall instruction must tell the judge to attribute
    on meaning and answer strictly 0/1 — appended exactly once even though ragas metrics
    are module-level singletons and default_metrics() is called repeatedly."""
    from app.evaluation.ragas_eval import _BINARY_JUDGE_SUFFIX

    default_metrics()
    metrics = default_metrics()
    recall = next(m for m in metrics if m.name == "context_recall")
    assert metrics and recall.context_recall_prompt.instruction.count(_BINARY_JUDGE_SUFFIX) == 1


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


def test_topic_adherence_metric_skips_malformed_judge_output():
    """Regression (2026-07-06 run): malformed judge output used to crash the metric job
    with a traceback (ValueError broadcast mismatch / TypeError dtype). The metric must
    instead score the sample NaN (counted + excluded downstream) and keep going."""
    import asyncio
    import math

    from app.evaluation.ragas_eval import to_topic_adherence_sample, topic_adherence_metrics

    (metric,) = topic_adherence_metrics(modes=("precision",))
    sample = to_topic_adherence_sample("What is EDD?", "EDD is enhanced due diligence.")

    for exc in (
        ValueError("operands could not be broadcast together with shapes (7,) (19,)"),
        TypeError("ufunc 'bitwise_and' not supported for the input types"),
    ):
        with patch.object(type(metric), "_per_topic_ascore", side_effect=exc):
            score = asyncio.run(metric._multi_turn_ascore(sample, None))
        assert math.isnan(score)


def _fake_prompt(fn):
    """Wrap an async function as a stand-in for a ragas PydanticPrompt."""
    from types import SimpleNamespace

    return SimpleNamespace(generate=fn)


def test_topic_adherence_classifies_each_topic_in_its_own_judge_call():
    """Regression (2026-07-07 run): RAGAS's stock TopicAdherenceScore classifies all N
    extracted topics in one judge call and small judges return the wrong count (7/64
    samples NaN). The safe metric must classify one topic per call — count mismatch
    impossible — and reproduce ragas's confusion-matrix math."""
    import asyncio

    from types import SimpleNamespace

    from app.evaluation.ragas_eval import to_topic_adherence_sample, topic_adherence_metrics

    (metric,) = topic_adherence_metrics(modes=("precision",))
    metric.llm = object()
    sample = to_topic_adherence_sample("What is EDD?", "EDD is enhanced due diligence.")

    classify_calls: list[list[str]] = []

    async def extract(data, llm, callbacks=None):
        return SimpleNamespace(topics=["t1", "t2", "t3"])

    async def refused(data, llm, callbacks=None):
        return SimpleNamespace(refused_to_answer=data.topic == "t3")

    async def classify(data, llm, callbacks=None):
        classify_calls.append(list(data.topics))
        return SimpleNamespace(classifications=[data.topics[0] != "t2"])

    metric.topic_extraction_prompt = _fake_prompt(extract)
    metric.topic_refused_prompt = _fake_prompt(refused)
    metric.topic_classification_prompt = _fake_prompt(classify)

    score = asyncio.run(metric._multi_turn_ascore(sample, None))

    assert classify_calls == [["t1"], ["t2"], ["t3"]]
    # answered=[T,T,F], on_topic=[T,F,T] -> tp=1 (t1), fp=1 (t2) -> precision = 1/2
    assert abs(score - 0.5) < 1e-6


def test_topic_adherence_metrics_use_corrected_classification_prompt():
    """Recommendation 2 (2026-07-09 diagnosis): ragas's stock TopicClassificationPrompt
    couples a vague instruction with a self-contradictory example (claims General
    Relativity does NOT fall under Physics), which the mistral-nemo judge mirrored as
    near-uniform False verdicts. Every metric must carry the corrected prompt: a
    meaning-based "falls under ANY reference topic" rule and coherent single-topic
    examples, with the stock 2-topic -> [True, False] example gone."""
    from app.evaluation.ragas_eval import topic_adherence_metrics

    metrics = topic_adherence_metrics()

    assert len(metrics) == 3
    for metric in metrics:
        prompt = metric.topic_classification_prompt
        assert "falls under any" in prompt.instruction.lower()
        assert prompt.examples, "corrected prompt must keep few-shot examples"
        for example_input, example_output in prompt.examples:
            assert len(example_input.topics) == 1
            assert len(example_output.classifications) == 1
        assert not any(
            len(example_input.topics) == 2 and example_output.classifications == [True, False]
            for example_input, example_output in prompt.examples
        )


def test_topic_adherence_scores_nan_when_no_topics_extracted():
    """The greeting/out-of-scope case: no topics extracted means adherence is unjudgeable
    (previously a TypeError crash) — score NaN, don't guess."""
    import asyncio
    import math

    from types import SimpleNamespace

    from app.evaluation.ragas_eval import to_topic_adherence_sample, topic_adherence_metrics

    (metric,) = topic_adherence_metrics(modes=("f1",))
    metric.llm = object()
    sample = to_topic_adherence_sample("Hi, how are you doing today?", "Hello! I can help with AML.")

    async def extract(data, llm, callbacks=None):
        return SimpleNamespace(topics=[])

    metric.topic_extraction_prompt = _fake_prompt(extract)

    assert math.isnan(asyncio.run(metric._multi_turn_ascore(sample, None)))


def test_repair_judge_json_passes_valid_output_through():
    import json

    from app.evaluation.ragas_run import _repair_judge_json

    text = '{"classifications": [{"statement": "s", "reason": "r", "attributed": 1}]}'
    assert json.loads(_repair_judge_json(text)) == json.loads(text)


def test_repair_judge_json_coerces_fractional_binary_verdicts():
    """Regression (2026-07-07 run, Job[95]): the judge emits valid JSON with
    "attributed": 0.5, which fails ragas's pydantic int field. Conservative policy:
    0.5 rounds down (no credit), >0.5 rounds up."""
    import json

    from ragas.metrics._context_recall import ContextRecallClassifications

    from app.evaluation.ragas_run import _repair_judge_json

    text = (
        '{"classifications": ['
        '{"statement": "a", "reason": "r", "attributed": 0.5},'
        '{"statement": "b", "reason": "r", "attributed": 0.7},'
        '{"statement": "c", "reason": "r", "attributed": 1}]}'
    )
    repaired = json.loads(_repair_judge_json(text))
    assert [c["attributed"] for c in repaired["classifications"]] == [0, 1, 1]
    ContextRecallClassifications(**repaired)  # must satisfy ragas's schema


def test_repair_judge_json_fixes_invalid_and_double_encoded_json():
    """Regression (2026-07-07 run, Jobs 23/91/107): literal \\n outside strings and
    whole objects wrapped in a JSON string (ragas's FixOutputFormat round-trip)."""
    import json

    from app.evaluation.ragas_run import _repair_judge_json

    literal_newlines = '{\\n  "classifications": [\\n {"statement": "s", "reason": "r", "attributed": 1}]}'
    repaired = json.loads(_repair_judge_json(literal_newlines))
    assert repaired["classifications"][0]["attributed"] == 1

    double_encoded = json.dumps('{"classifications": [{"statement": "s", "reason": "r", "verdict": 0.5}]}')
    repaired = json.loads(_repair_judge_json(double_encoded))
    assert repaired["classifications"][0]["verdict"] == 0


def test_repair_judge_json_returns_hopeless_text_unchanged():
    from app.evaluation.ragas_run import _repair_judge_json

    assert _repair_judge_json("I could not produce JSON, sorry.") == "I could not produce JSON, sorry."


def test_build_ragas_llm_enforces_json_decoding():
    """Regression (2026-07-06 run): the qwen2.5:3b judge emitted invalid JSON escapes →
    OutputParserException → NaN scores. The judge must run with Ollama's grammar-
    constrained JSON decoding so every judge response parses."""
    from app.evaluation.ragas_run import _build_ragas_llm

    llm, _ = _build_ragas_llm(GenerationConfig())
    assert llm.langchain_llm.format == "json"


def test_run_refusal_rate_means_judge_verdicts_and_keeps_per_row_detail():
    """Recommendation 1 (metric split): out-of-scope refusals are scored by their own
    judge-based metric, not folded into topic adherence (whose precision formula scores a
    correct refusal as 0.0). No Ollama: the generator and the ragas TopicRefusedPrompt
    judge are both faked; verdicts alternate refused/answered -> mean 0.5."""
    from types import SimpleNamespace

    from app.evaluation.ragas_run import _run_refusal_rate

    class _FakeGenerator:
        def generate(self, question, k):
            return SimpleNamespace(answer=f"answer to {question}")

    verdicts = iter([True, False, True, False])

    async def fake_generate(self, data=None, llm=None, **kwargs):
        assert data.user_input.startswith("Human: ") and "\nAI: answer to " in data.user_input
        assert data.topic in data.user_input
        return SimpleNamespace(refused_to_answer=next(verdicts))

    rows = [{"question": f"q{i}"} for i in range(4)]
    with patch("ragas.metrics._topic_adherence.TopicRefusedPrompt.generate", fake_generate):
        result = _run_refusal_rate(_FakeGenerator(), 4, rows, llm=object())

    assert result.mean_scores["out_of_scope_refusal_rate"] == 0.5
    assert result.nan_counts == {}
    assert [s["refused"] for s in result.sample_scores] == [True, False, True, False]
    assert result.sample_scores[0] == {"question": "q0", "answer": "answer to q0", "refused": True}


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
