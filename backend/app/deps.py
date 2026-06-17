"""Shared FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache

from app.generation import AnswerGenerator, build_answer_generator
from app.ingestion.rag import RagSystem, build_rag


@lru_cache
def get_rag() -> RagSystem:
    """Single shared RagSystem (model + store built once per process)."""
    return build_rag()


@lru_cache
def get_generator() -> AnswerGenerator:
    """Single shared AnswerGenerator (Ollama LLM client built once per process)."""
    return build_answer_generator(get_rag())
