"""Augmented generation: retrieve context, then generate a grounded answer.

Built on a local Ollama LLM (default ``gemma4:e2b``). The :class:`AnswerGenerator`
depends only on a search function and a text-completion function, so it is decoupled from
both the vector store and the LLM backend.
"""

from __future__ import annotations

from .config import GenerationConfig
from .generator import (
    Answer,
    AnswerGenerator,
    Citation,
    StreamChunk,
    StreamedAnswer,
    build_answer_generator,
    build_completion,
    build_llm_ping,
    build_stream_completion,
)

__all__ = [
    "GenerationConfig",
    "Answer",
    "Citation",
    "StreamChunk",
    "StreamedAnswer",
    "AnswerGenerator",
    "build_answer_generator",
    "build_completion",
    "build_stream_completion",
    "build_llm_ping",
]
