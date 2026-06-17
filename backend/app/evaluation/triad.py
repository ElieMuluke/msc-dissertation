"""RAG Triad evaluation (LLM-as-judge, reference-free).

Scores three dimensions in ``[0, 1]`` for each answered question:

- **context relevance** — are the retrieved contexts relevant to the question?
- **groundedness** — is the answer supported by the retrieved context (no hallucination)?
- **answer relevance** — does the answer actually address the question?

Prompt builders and aggregation are pure; the LLM is injected as a ``judge_fn`` so the
logic is unit-testable with a fake judge.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

JudgeFn = Callable[[str], float]

_SCORE_RULE = "Respond with ONLY a single number between 0 and 1 (e.g. 0.8)."


@dataclass(frozen=True)
class TriadRecord:
    """One answered question with the context it was generated from."""

    question: str
    answer: str
    contexts: list[str]


def context_relevance_prompt(question: str, context: str) -> str:
    return (
        "Rate how relevant the CONTEXT is for answering the QUESTION.\n"
        f"QUESTION: {question}\nCONTEXT: {context}\n{_SCORE_RULE}"
    )


def groundedness_prompt(answer: str, context: str) -> str:
    return (
        "Rate how well the ANSWER is supported by the CONTEXT "
        "(1 = fully supported, 0 = unsupported/hallucinated).\n"
        f"CONTEXT: {context}\nANSWER: {answer}\n{_SCORE_RULE}"
    )


def answer_relevance_prompt(question: str, answer: str) -> str:
    return (
        "Rate how well the ANSWER addresses the QUESTION.\n"
        f"QUESTION: {question}\nANSWER: {answer}\n{_SCORE_RULE}"
    )


def parse_score(text: str) -> float:
    """Extract the first number from the judge's reply and clamp to ``[0, 1]``."""
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return 0.0
    return max(0.0, min(1.0, float(match.group())))


def make_llm_judge(complete_fn: Callable[[str], str]) -> JudgeFn:
    """Turn a text-completion function into a 0–1 judge."""
    return lambda prompt: parse_score(complete_fn(prompt))


def evaluate_triad(records: Sequence[TriadRecord], judge_fn: JudgeFn) -> dict[str, float]:
    """Return mean triad scores over ``records`` (empty -> zeros)."""
    n = len(records)
    if n == 0:
        return {"context_relevance": 0.0, "groundedness": 0.0, "answer_relevance": 0.0}

    totals = {"context_relevance": 0.0, "groundedness": 0.0, "answer_relevance": 0.0}
    for record in records:
        ctx_scores = [judge_fn(context_relevance_prompt(record.question, c)) for c in record.contexts]
        totals["context_relevance"] += sum(ctx_scores) / len(ctx_scores) if ctx_scores else 0.0
        joined = "\n\n".join(record.contexts) if record.contexts else "(no context)"
        totals["groundedness"] += judge_fn(groundedness_prompt(record.answer, joined))
        totals["answer_relevance"] += judge_fn(answer_relevance_prompt(record.question, record.answer))

    return {name: value / n for name, value in totals.items()}
