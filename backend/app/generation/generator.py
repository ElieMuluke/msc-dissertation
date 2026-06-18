"""Augmented answer generation: retrieve, then generate a grounded answer.

The generator depends on a ``search_fn`` and a ``complete_fn`` (str -> str), so it is
independent of both the vector store and the LLM backend and is unit-testable with fakes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Optional

from app.generation.config import GenerationConfig
from app.generation.prompt import build_prompt
from app.ingestion.rag import DocumentType, RagSystem, SearchResult

SearchFn = Callable[[str, int, Optional[DocumentType]], Sequence[SearchResult]]
CompleteFn = Callable[[str], str]
StreamFn = Callable[[str], Iterator[str]]


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


@dataclass
class StreamedAnswer:
    """A streamed answer: citations are known up front, the text arrives as tokens."""

    citations: list[Citation]
    used_context: bool
    tokens: Iterator[str]


def _citation(result: SearchResult) -> Citation:
    return Citation(
        id=result.id,
        source=result.metadata.get("source", ""),
        page=result.metadata.get("page"),
        score=result.score,
    )


class AnswerGenerator:
    """Retrieve context then generate a grounded answer with citations."""

    def __init__(
        self,
        search_fn: SearchFn,
        complete_fn: CompleteFn,
        stream_fn: Optional[StreamFn] = None,
    ) -> None:
        self._search = search_fn
        self._complete = complete_fn
        self._stream = stream_fn

    def generate(self, query: str, k: int = 5, doc_type: Optional[DocumentType] = None) -> Answer:
        results = list(self._search(query, k, doc_type))
        answer = self._complete(build_prompt(query, results)).strip()
        return Answer(
            answer=answer,
            citations=[_citation(r) for r in results],
            used_context=bool(results),
            contexts=[r.text for r in results],
        )

    def stream(self, query: str, k: int = 5, doc_type: Optional[DocumentType] = None) -> StreamedAnswer:
        """Retrieve context, then stream the answer tokens. Citations are known up front."""
        if self._stream is None:
            raise RuntimeError("This AnswerGenerator was built without streaming support")
        results = list(self._search(query, k, doc_type))
        return StreamedAnswer(
            citations=[_citation(r) for r in results],
            used_context=bool(results),
            tokens=self._stream(build_prompt(query, results)),
        )


def _build_chat_ollama(config: GenerationConfig):
    """Construct a configured Ollama chat model (shared by completion + streaming)."""
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=config.model,
        base_url=config.base_url,
        temperature=config.temperature,
        num_predict=config.num_predict,
        num_ctx=config.num_ctx,
        keep_alive=config.keep_alive,
    )


def build_completion(config: Optional[GenerationConfig] = None) -> CompleteFn:
    """Build a text-completion function backed by a local Ollama chat model."""
    llm = _build_chat_ollama(config or GenerationConfig())
    return lambda prompt: llm.invoke(prompt).content


def build_stream_completion(config: Optional[GenerationConfig] = None) -> StreamFn:
    """Build a streaming completion function yielding answer token chunks."""
    llm = _build_chat_ollama(config or GenerationConfig())

    def stream(prompt: str) -> Iterator[str]:
        for chunk in llm.stream(prompt):
            text = chunk.content
            if text:
                yield text

    return stream


def build_llm_ping(config: Optional[GenerationConfig] = None) -> Callable[[], bool]:
    """Build a function reporting whether the Ollama server is reachable."""
    import httpx

    config = config or GenerationConfig()
    url = f"{config.base_url.rstrip('/')}/api/tags"

    def ping() -> bool:
        try:
            return httpx.get(url, timeout=2.0).status_code == 200
        except Exception:  # noqa: BLE001 - any failure means unreachable
            return False

    return ping


def build_answer_generator(rag: RagSystem, config: Optional[GenerationConfig] = None) -> AnswerGenerator:
    """Wire a RagSystem and an Ollama chat model into an :class:`AnswerGenerator`."""
    complete = build_completion(config)
    stream = build_stream_completion(config)

    def search(query: str, k: int, doc_type: Optional[DocumentType]):
        return rag.search(query, k=k, doc_type=doc_type)

    return AnswerGenerator(search, complete, stream)
