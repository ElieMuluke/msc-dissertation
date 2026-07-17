"""Shared FastAPI dependencies."""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache

from app.generation import (
    AnswerGenerator,
    GenerationConfig,
    build_answer_generator,
    build_llm_ping,
    resolve_scope_gate_threshold,
)
from app.ingestion.rag import RagConfig, RagSystem, build_rag
from app.ingestion.tabular import TabularSystem, build_tabular_system

# Validated retrieval config (see docs/evaluation.md and the 2026-07-17 24-run sweep):
# section-aware chunking + parent-context prefix + bge-small-en-v1.5 (aml_sections_c)
# with hybrid BM25+vector search raises context_precision/recall over both the plain-vector
# aml_corpus baseline and the prior MiniLM/aml_sections_b config, with no cost to
# faithfulness/answer_relevancy. bm25_weight=0.4 chosen from the sweep's 0.2-0.4 band (the
# two were statistically indistinguishable on context_precision; 0.4 has the edge on
# context_recall, 0.787 vs 0.769). Each field is independently env-overridable (matching
# RagConfig.embedding_model's own RAG_EMBEDDING_MODEL convention) so the deployed config can
# be tuned without a code change; the literals below are the sweep-recommended defaults.
_RAG_CONFIG = RagConfig(
    collection_name=os.getenv("RAG_COLLECTION_NAME", "aml_sections_c"),
    embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
    bm25_weight=float(os.getenv("RAG_BM25_WEIGHT", "0.4")),
)


@lru_cache
def get_rag() -> RagSystem:
    """Single shared RagSystem (model + store built once per process)."""
    return build_rag(_RAG_CONFIG)


@lru_cache
def get_tabular() -> TabularSystem:
    """Single shared TabularSystem (engine + schema built once per process)."""
    return build_tabular_system()


@lru_cache
def get_generator() -> AnswerGenerator:
    """Single shared AnswerGenerator (Ollama LLM client built once per process).

    Resolves ``scope_gate_threshold`` from ``_RAG_CONFIG.embedding_model`` explicitly
    rather than relying on ``GenerationConfig``'s own field default: that default is
    computed once at import time from a bare ``RagConfig()``'s env-derived embedding
    model, which would silently diverge from ``_RAG_CONFIG.embedding_model`` whenever the
    latter is set by a literal (as it is here) rather than purely by ``RAG_EMBEDDING_MODEL``.
    """
    gen_config = GenerationConfig(scope_gate_threshold=resolve_scope_gate_threshold(_RAG_CONFIG.embedding_model))
    return build_answer_generator(get_rag(), gen_config)


@lru_cache
def get_llm_ping() -> Callable[[], bool]:
    """Single shared LLM-connectivity probe (Ollama reachability)."""
    return build_llm_ping()
