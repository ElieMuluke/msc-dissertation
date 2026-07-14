"""Unit tests for the pure RAGAS dataset-conversion helper (no LLM, no Ollama).

`ragas.evaluate` itself is not exercised here: it needs a live LLM judge and is slow.
Only the data-mapping logic (:func:`to_evaluation_dataset`) is tested, offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import pandas as pd

from app.evaluation.ragas_eval import (
    RagasRecord,
    RagasResult,
    default_metrics,
    run_ragas,
    to_evaluation_dataset,
)
from app.evaluation.ragas_run import build_report
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


def test_run_out_of_scope_splits_retrieval_gate_from_generation_refusal():
    """Recommendation 1 (metric split) + layer split: out-of-scope behavior separates the
    retrieval-layer F25 gate (short-circuits before any LLM call, detected by the exact
    OUT_OF_SCOPE_REFUSAL string) from generation-layer refusal (judged only for queries
    the gate let through). No Ollama: rag/generator/judge are all faked. q0,q2 are gated;
    q1,q3 reach generation and the judge alternates refused/answered."""
    from types import SimpleNamespace

    from app.generation import OUT_OF_SCOPE_REFUSAL
    from app.evaluation.ragas_run import _run_out_of_scope

    class _FakeRag:
        def scope_confidence(self, question):
            return {"q0": 0.1, "q1": 0.5, "q2": 0.2, "q3": 0.6}[question]

    class _FakeGenerator:
        def generate(self, question, k):
            if question in ("q0", "q2"):
                return SimpleNamespace(answer=OUT_OF_SCOPE_REFUSAL)
            return SimpleNamespace(answer=f"answer to {question}")

    verdicts = iter([True, False])  # only for q1, q3 (ungated)
    judge_calls: list[str] = []

    async def fake_generate(self, data=None, llm=None, **kwargs):
        judge_calls.append(data.topic)
        return SimpleNamespace(refused_to_answer=next(verdicts))

    rows = [{"question": f"q{i}"} for i in range(4)]
    with patch("ragas.metrics._topic_adherence.TopicRefusedPrompt.generate", fake_generate):
        result = _run_out_of_scope(_FakeRag(), _FakeGenerator(), 4, rows, llm=object())

    assert judge_calls == ["q1", "q3"]  # judge never invoked for gated rows
    assert abs(result.mean_scores["retrieval_scope_confidence"] - (0.1 + 0.5 + 0.2 + 0.6) / 4) < 1e-9
    assert result.mean_scores["gated_by_retrieval_confidence_rate"] == 0.5  # q0, q2
    assert result.mean_scores["generation_refusal_rate"] == 0.5  # q1 refused, q3 didn't
    assert result.mean_scores["out_of_scope_refusal_rate"] == 0.75  # q0,q1,q2 refused; q3 didn't
    assert result.nan_counts == {"generation_refusal_rate": 0}
    gated_rows = [s for s in result.sample_scores if s["gated"]]
    assert all(s["refused"] for s in gated_rows)


def test_run_out_of_scope_generation_refusal_rate_is_nan_when_gate_catches_everything():
    import math
    from types import SimpleNamespace

    from app.generation import OUT_OF_SCOPE_REFUSAL
    from app.evaluation.ragas_run import _run_out_of_scope

    class _FakeRag:
        def scope_confidence(self, question):
            return 0.1

    class _FakeGenerator:
        def generate(self, question, k):
            return SimpleNamespace(answer=OUT_OF_SCOPE_REFUSAL)

    def fail_if_called(self, data=None, llm=None, **kwargs):
        raise AssertionError("judge should never be invoked when every row is gated")

    rows = [{"question": "q0"}, {"question": "q1"}]
    with patch("ragas.metrics._topic_adherence.TopicRefusedPrompt.generate", fail_if_called):
        result = _run_out_of_scope(_FakeRag(), _FakeGenerator(), 4, rows, llm=object())

    assert result.mean_scores["gated_by_retrieval_confidence_rate"] == 1.0
    assert math.isnan(result.mean_scores["generation_refusal_rate"])
    assert result.nan_counts == {"generation_refusal_rate": 1}


def test_build_layer_summary_groups_metrics_by_layer_and_population():
    """The user-facing ask: metrics grouped by layer (retrieval/generation), shown against
    each question population (57 golden, 51 in-scope, 13 out-of-scope), so it's clear
    which layer produced which number."""
    from app.evaluation.ragas_run import build_layer_summary

    core4 = RagasResult(
        mean_scores={"context_precision": 0.664, "context_recall": 0.762, "faithfulness": 0.8, "answer_relevancy": 0.79},
        sample_scores=[],
        nan_counts={},
    )
    topic = RagasResult(
        mean_scores={"topic_adherence_precision": 0.9, "topic_adherence_recall": 0.99, "topic_adherence_f1": 0.93},
        sample_scores=[],
        nan_counts={},
    )
    oos = RagasResult(
        mean_scores={
            "retrieval_scope_confidence": 0.3,
            "gated_by_retrieval_confidence_rate": 1.0,
            "generation_refusal_rate": float("nan"),
            "out_of_scope_refusal_rate": 1.0,
        },
        sample_scores=[],
        nan_counts={"generation_refusal_rate": 1},
    )

    summary = build_layer_summary(core4, topic, oos, n_golden=57, n_in_scope=51, n_out_of_scope=13)

    assert "57 golden questions" in summary and "51 in-scope questions" in summary and "13 out-of-scope" in summary
    retrieval_row = summary.splitlines()[summary.splitlines().index(next(l for l in summary.splitlines() if l.startswith("| Retrieval")))]
    assert "context_precision: 0.664" in retrieval_row and "context_recall: 0.762" in retrieval_row
    assert "retrieval_scope_confidence: 0.300" in retrieval_row and "gated_by_retrieval_confidence_rate: 1.000" in retrieval_row
    generation_row = next(l for l in summary.splitlines() if l.startswith("| Generation"))
    assert "faithfulness: 0.800" in generation_row and "topic_adherence_f1: 0.930" in generation_row
    assert "generation_refusal_rate: nan [NaN]" in generation_row  # NaN shown, flagged, never hidden
    combined_row = next(l for l in summary.splitlines() if l.startswith("| Combined"))
    assert "out_of_scope_refusal_rate: 1.000" in combined_row
    assert "chunking" in summary.lower() and "not" in summary.lower()  # documents chunking isn't a 4th layer


def test_build_layer_summary_handles_missing_sections():
    """--skip-topic runs have no topic/out-of-scope results; cells render '—' not crash."""
    from app.evaluation.ragas_run import build_layer_summary

    core4 = RagasResult(mean_scores={"context_precision": 0.5}, sample_scores=[], nan_counts={})
    summary = build_layer_summary(core4, None, None, n_golden=6, n_in_scope=0, n_out_of_scope=0)
    assert "—" in summary
    assert "context_precision: 0.500" in summary


def test_build_report_means_distribution_categories_and_worst_queries():
    """The dissertation-grade detail report: means annotated with NaN counts, a
    distribution table over valid samples only, per-category means keyed by the golden
    set's categories, and a worst-5 list sorted ascending with NaN rows excluded."""
    rows = [
        {"user_input": "q0", "m": 1.0},
        {"user_input": "q1", "m": 0.2},
        {"user_input": "q2", "m": float("nan")},
        {"user_input": "q3", "m": 0.6},
        {"user_input": "q4", "m": 0.8},
    ]
    result = RagasResult(mean_scores={"m": 0.65}, sample_scores=rows, nan_counts={"m": 1})
    categories = {"q0": "clear", "q1": "clear", "q2": "ambiguous", "q3": "ambiguous", "q4": "ambiguous"}

    report = build_report("config-line", [("Core-4", result, ["m"])], categories)

    assert "config-line" in report and "## Core-4" in report
    assert "- m: 0.650  (NaN: 1/5)" in report
    # Distribution over the 4 valid values [0.2, 0.6, 0.8, 1.0] (exclusive quartiles).
    assert "| m | 0.200 | 0.300 | 0.700 | 0.950 | 1.000 | 4 |" in report
    # Per-category means: ambiguous = mean(0.6, 0.8), clear = mean(1.0, 0.2); NaN excluded.
    assert "| metric | ambiguous | clear |" in report
    assert "| m | 0.700 (n=2) | 0.600 (n=2) |" in report
    # Worst queries ascending, NaN row (q2) excluded.
    worst = report.split("**Worst 5 — m**")[1]
    assert worst.index("0.200 | q1") < worst.index("0.600 | q3") < worst.index("0.800 | q4") < worst.index("1.000 | q0")
    assert "q2" not in worst


def test_build_report_refusal_section_lists_non_refused_queries():
    rows = [
        {"question": "give me crypto investment tips", "answer": "Out of scope.", "refused": True},
        {"question": "what is the best pizza topping", "answer": "Margherita.", "refused": False},
    ]
    result = RagasResult(
        mean_scores={"out_of_scope_refusal_rate": 0.5}, sample_scores=rows, nan_counts={}
    )

    report = build_report("hdr", [("Refusal", result, ["out_of_scope_refusal_rate"])])

    assert "- out_of_scope_refusal_rate: 0.500" in report
    assert "**Non-refused queries**" in report
    non_refused = report.split("**Non-refused queries**")[1]
    assert "- what is the best pizza topping" in non_refused
    assert "crypto investment tips" not in non_refused


def test_build_report_extracts_question_from_message_list_rows():
    """Topic-adherence rows carry the question as a message list, not a string; the
    report must still resolve it for worst-queries and per-category matching."""
    rows = [
        {
            "user_input": [{"type": "human", "content": "What is EDD?"}, {"type": "ai", "content": "..."}],
            "topic_adherence_f1": 0.4,
        }
    ]
    result = RagasResult(
        mean_scores={"topic_adherence_f1": 0.4}, sample_scores=rows, nan_counts={"topic_adherence_f1": 0}
    )

    report = build_report("hdr", [("Topic", result, ["topic_adherence_f1"])], {"What is EDD?": "clear"})

    assert "- 0.400 | What is EDD?" in report
    assert "| topic_adherence_f1 | 0.400 (n=1) |" in report  # per-category table matched


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
