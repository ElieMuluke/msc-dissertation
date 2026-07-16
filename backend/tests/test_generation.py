"""Unit tests for prompt building and the answer generator (fake LLM, no Ollama)."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.generation.config import GenerationConfig
from app.generation.generator import OUT_OF_SCOPE_REFUSAL, AnswerGenerator
from app.generation.prompt import build_prompt
from app.ingestion.rag.models import SearchResult


def _result(rid, text, source="a.pdf", page=1, score=0.8):
    return SearchResult(rid, text, {"source": source, "page": page}, score)


def test_build_prompt_includes_context_and_ids():
    prompt = build_prompt("What is the CTR threshold?", [_result("p1", "Report cash over 10,000.")])
    assert "What is the CTR threshold?" in prompt
    assert "[p1]" in prompt and "a.pdf" in prompt
    assert "Report cash over 10,000." in prompt


def test_build_prompt_handles_no_context():
    prompt = build_prompt("anything", [])
    assert "no relevant documents found" in prompt


def test_generate_uses_context_and_cites():
    results = [_result("p1", "Report cash over 10,000.", page=3)]
    captured = {}

    def fake_search(query, k):
        captured["args"] = (query, k)
        return results

    def fake_complete(prompt):
        assert "[p1]" in prompt
        return "  File a CTR per [p1].  "

    gen = AnswerGenerator(fake_search, fake_complete)
    answer = gen.generate("threshold?", k=3)

    assert answer.answer == "File a CTR per [p1]."
    assert answer.used_context is True
    assert answer.citations[0].id == "p1"
    assert answer.citations[0].page == 3
    assert captured["args"] == ("threshold?", 3)


def test_generate_without_results_flags_no_context():
    gen = AnswerGenerator(lambda q, k: [], lambda prompt: "No data available.")
    answer = gen.generate("threshold?")
    assert answer.used_context is False
    assert answer.citations == []


def _must_not_call(*args, **kwargs):
    raise AssertionError("must not be called on the gated path")


def test_scope_gate_refuses_below_threshold_without_llm_or_search():
    gen = AnswerGenerator(
        _must_not_call, _must_not_call, confidence_fn=lambda q: 0.3, scope_threshold=0.46
    )
    answer = gen.generate("who won the world cup?")
    assert answer.answer == OUT_OF_SCOPE_REFUSAL
    assert answer.used_context is False
    assert answer.citations == []
    assert answer.contexts == []


def test_scope_gate_passes_above_threshold():
    gen = AnswerGenerator(
        lambda q, k: [_result("p1", "Report cash over 10,000.")],
        lambda prompt: "File a CTR per [p1].",
        confidence_fn=lambda q: 0.7,
        scope_threshold=0.46,
    )
    answer = gen.generate("CTR threshold?")
    assert answer.answer == "File a CTR per [p1]."
    assert answer.used_context is True


def test_scope_gate_disabled_by_zero_threshold():
    gen = AnswerGenerator(
        lambda q, k: [], lambda prompt: "answer", confidence_fn=lambda q: 0.0, scope_threshold=0.0
    )
    assert gen.generate("anything").answer == "answer"


def test_scope_gate_off_without_confidence_fn():
    gen = AnswerGenerator(lambda q, k: [], lambda prompt: "answer", scope_threshold=0.46)
    assert gen.generate("anything").answer == "answer"


def test_stream_scope_gate_yields_single_refusal_chunk():
    gen = AnswerGenerator(
        _must_not_call,
        _must_not_call,
        stream_fn=_must_not_call,
        confidence_fn=lambda q: 0.3,
        scope_threshold=0.46,
    )
    streamed = gen.stream("who won the world cup?")
    assert streamed.citations == []
    assert streamed.used_context is False
    chunks = list(streamed.chunks)
    assert len(chunks) == 1
    assert chunks[0].kind == "answer"
    assert chunks[0].text == OUT_OF_SCOPE_REFUSAL


def test_default_num_predict_leaves_room_for_reasoning_and_an_answer():
    """Regression: a 512-token cap let reasoning models (e.g. deepseek-r1:14b) spend the
    whole budget on their <think> trace, producing empty/truncated answers in the 2026-07
    eval run. The default must be large enough to cover a reasoning trace plus a full
    answer, matching the num_predict already used for the RAGAS judge LLM."""
    assert GenerationConfig().num_predict >= 2048


def test_resolve_scope_gate_threshold_known_embedders():
    """Each calibrated embedder resolves to its own gate threshold, not a shared default —
    a single value is wrong for both (see 2026-07-16 finding: bge-small-en-v1.5's
    out-of-scope confidence distribution sits far above all-MiniLM-L6-v2's, so reusing
    MiniLM's 0.46 would leave the gate almost inert for bge-small)."""
    from app.generation.config import resolve_scope_gate_threshold

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SCOPE_GATE_THRESHOLD", None)
        assert resolve_scope_gate_threshold("all-MiniLM-L6-v2") == 0.46
        assert resolve_scope_gate_threshold("BAAI/bge-small-en-v1.5") == 0.638


def test_resolve_scope_gate_threshold_unknown_embedder_falls_back_to_minilm():
    from app.generation.config import resolve_scope_gate_threshold

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SCOPE_GATE_THRESHOLD", None)
        assert resolve_scope_gate_threshold("some/uncalibrated-model") == 0.46


def test_resolve_scope_gate_threshold_explicit_env_var_always_wins():
    """An explicit SCOPE_GATE_THRESHOLD must override the per-embedder lookup for every
    embedder, calibrated or not — this is what makes the lookup a default, not a cage."""
    from app.generation.config import resolve_scope_gate_threshold

    with patch.dict(os.environ, {"SCOPE_GATE_THRESHOLD": "0.3"}):
        assert resolve_scope_gate_threshold("all-MiniLM-L6-v2") == 0.3
        assert resolve_scope_gate_threshold("BAAI/bge-small-en-v1.5") == 0.3
        assert resolve_scope_gate_threshold("some/uncalibrated-model") == 0.3
