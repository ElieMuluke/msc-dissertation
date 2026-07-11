"""Unit tests for prompt building and the answer generator (fake LLM, no Ollama)."""

from __future__ import annotations

from app.generation.config import GenerationConfig
from app.generation.generator import AnswerGenerator
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


def test_default_num_predict_leaves_room_for_reasoning_and_an_answer():
    """Regression: a 512-token cap let reasoning models (e.g. deepseek-r1:14b) spend the
    whole budget on their <think> trace, producing empty/truncated answers in the 2026-07
    eval run. The default must be large enough to cover a reasoning trace plus a full
    answer, matching the num_predict already used for the RAGAS judge LLM."""
    assert GenerationConfig().num_predict >= 2048
