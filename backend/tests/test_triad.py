"""Unit tests for RAG Triad evaluation (fake judge, no LLM)."""

from __future__ import annotations

import pytest

from app.evaluation.triad import (
    TriadRecord,
    answer_relevance_prompt,
    context_relevance_prompt,
    evaluate_triad,
    groundedness_prompt,
    make_llm_judge,
    parse_score,
)


@pytest.mark.parametrize(
    "text,expected",
    [("0.8", 0.8), ("Score: 0.5/1", 0.5), ("the rating is 1", 1.0), ("1.7", 1.0), ("-0.3", 0.0), ("n/a", 0.0)],
)
def test_parse_score(text, expected):
    assert parse_score(text) == expected


def test_prompts_contain_inputs_and_rule():
    assert "Q?" in context_relevance_prompt("Q?", "ctx") and "ctx" in context_relevance_prompt("Q?", "ctx")
    assert "ANS" in groundedness_prompt("ANS", "ctx")
    assert "Q?" in answer_relevance_prompt("Q?", "ANS")
    assert "between 0 and 1" in answer_relevance_prompt("Q?", "ANS")


def test_make_llm_judge_parses_completion():
    judge = make_llm_judge(lambda prompt: "I rate this 0.7")
    assert judge("anything") == 0.7


def test_evaluate_triad_means():
    records = [
        TriadRecord("q1", "a1", ["c1", "c2"]),
        TriadRecord("q2", "a2", ["c3"]),
    ]
    scores = evaluate_triad(records, judge_fn=lambda prompt: 0.8)
    assert scores == {"context_relevance": 0.8, "groundedness": 0.8, "answer_relevance": 0.8}


def test_evaluate_triad_empty():
    assert evaluate_triad([], judge_fn=lambda p: 1.0) == {
        "context_relevance": 0.0,
        "groundedness": 0.0,
        "answer_relevance": 0.0,
    }
