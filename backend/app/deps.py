"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from app.generation import AnswerGenerator, build_answer_generator, build_llm_ping
from app.ingestion.rag import RagSystem, build_rag


@lru_cache
def get_rag() -> RagSystem:
    """Single shared RagSystem (model + store built once per process)."""
    return build_rag()


@lru_cache
def get_generator() -> AnswerGenerator:
    """Single shared AnswerGenerator (Ollama LLM client built once per process)."""
    return build_answer_generator(get_rag())


@lru_cache
def get_llm_ping() -> Callable[[], bool]:
    """Single shared LLM-connectivity probe (Ollama reachability)."""
    return build_llm_ping()
