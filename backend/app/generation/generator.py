"""Augmented answer generation: retrieve, then generate a grounded answer.

The generator depends on a ``search_fn`` and a ``complete_fn`` (str -> str), so it is
independent of both the vector store and the LLM backend and is unit-testable with fakes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Optional

from app.generation.config import GenerationConfig
from app.generation.prompt import build_prompt
from app.ingestion.rag import DocumentType, RagSystem, SearchResult

SearchFn = Callable[[str, int, Optional[DocumentType]], Sequence[SearchResult]]
CompleteFn = Callable[[str], str]


@dataclass(frozen=True)
class Citation:
    id: str
    source: str
    page: object
    score: float


@dataclass(frozen=True)
class Answer:
    answer: str
    citations: list[Citation]
    used_context: bool
    contexts: list[str] = field(default_factory=list)


def _citation(result: SearchResult) -> Citation:
    return Citation(
        id=result.id,
        source=result.metadata.get("source", ""),
        page=result.metadata.get("page"),
        score=result.score,
    )


class AnswerGenerator:
    """Retrieve context then generate a grounded answer with citations."""

    def __init__(self, search_fn: SearchFn, complete_fn: CompleteFn) -> None:
        self._search = search_fn
        self._complete = complete_fn

    def generate(self, query: str, k: int = 5, doc_type: Optional[DocumentType] = None) -> Answer:
        results = list(self._search(query, k, doc_type))
        answer = self._complete(build_prompt(query, results)).strip()
        return Answer(
            answer=answer,
            citations=[_citation(r) for r in results],
            used_context=bool(results),
            contexts=[r.text for r in results],
        )


def build_completion(config: Optional[GenerationConfig] = None) -> CompleteFn:
    """Build a text-completion function backed by a local Ollama chat model."""
    from langchain_ollama import ChatOllama

    config = config or GenerationConfig()
    llm = ChatOllama(model=config.model, base_url=config.base_url, temperature=config.temperature)
    return lambda prompt: llm.invoke(prompt).content


def build_answer_generator(rag: RagSystem, config: Optional[GenerationConfig] = None) -> AnswerGenerator:
    """Wire a RagSystem and an Ollama chat model into an :class:`AnswerGenerator`."""
    complete = build_completion(config)

    def search(query: str, k: int, doc_type: Optional[DocumentType]):
        return rag.search(query, k=k, doc_type=doc_type)

    return AnswerGenerator(search, complete)
