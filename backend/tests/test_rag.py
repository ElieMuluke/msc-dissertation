"""Unit tests for the RAG facade.

Uses an in-memory Chroma store with deterministic fake embeddings — no model download,
no persistence — to test ingest/search/filtering logic fast.
"""

from __future__ import annotations

import pytest
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.ingestion.rag.models import Document, DocumentType
from app.ingestion.rag.rag import RagSystem


@pytest.fixture
def rag():
    store = Chroma(
        collection_name="test",
        embedding_function=DeterministicFakeEmbedding(size=32),
        collection_metadata={"hnsw:space": "cosine"},
    )
    return RagSystem(store)


def _docs():
    return [
        Document("p1", "AML reporting policy", DocumentType.POLICY),
        Document("p2", "KYC onboarding policy", DocumentType.POLICY),
        Document("a1", "suspicious wire action", DocumentType.ACTION),
    ]


def test_ingest_counts(rag):
    assert rag.ingest(_docs()) == 3


def test_ingest_empty_is_noop(rag):
    assert rag.ingest([]) == 0


def test_search_returns_results(rag):
    rag.ingest(_docs())
    results = rag.search("policy", k=3)
    assert results
    assert all(0.0 <= r.score <= 1.0 for r in results)


def test_search_filters_by_doc_type(rag):
    rag.ingest(_docs())
    results = rag.search("anything", k=5, doc_type=DocumentType.ACTION)
    assert {r.id for r in results} == {"a1"}
    assert all(r.doc_type is DocumentType.ACTION for r in results)


def test_scope_confidence_returns_raw_relevance(rag):
    rag.ingest(_docs())
    conf = rag.scope_confidence("AML reporting policy")
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0
    assert conf == pytest.approx(rag.search("AML reporting policy", k=1)[0].score)


def test_scope_confidence_empty_store():
    store = Chroma(
        collection_name="test_empty",
        embedding_function=DeterministicFakeEmbedding(size=32),
        collection_metadata={"hnsw:space": "cosine"},
    )
    assert RagSystem(store).scope_confidence("anything") == 0.0


def test_scope_confidence_bypasses_bm25_fusion():
    store = Chroma(
        collection_name="test_hybrid",
        embedding_function=DeterministicFakeEmbedding(size=32),
        collection_metadata={"hnsw:space": "cosine"},
    )
    hybrid = RagSystem(store, bm25_weight=0.5)
    hybrid.ingest(_docs())
    raw = RagSystem(store).search("reporting policy", k=1)[0].score
    # scope_confidence reads the raw vector relevance, not the min-max-normalized
    # fused score (whose top is a near-constant regardless of absolute confidence).
    assert hybrid.scope_confidence("reporting policy") == pytest.approx(raw)
    assert hybrid.search("reporting policy", k=1)[0].score != pytest.approx(raw)


def test_list_and_delete_sources(rag):
    rag.ingest([
        Document("a-0", "t1", DocumentType.POLICY, {"source": "a.pdf"}),
        Document("a-1", "t2", DocumentType.POLICY, {"source": "a.pdf"}),
        Document("b-0", "t3", DocumentType.ACTION, {"source": "b.pdf"}),
    ])
    sources = {s.filename: s for s in rag.list_sources()}
    assert sources["a.pdf"].pages == 2
    assert sources["b.pdf"].doc_type is DocumentType.ACTION
    assert sources["a.pdf"].ingested_at  # timestamp stamped at ingest

    assert rag.delete_by_source("a.pdf") == 2
    assert {s.filename for s in rag.list_sources()} == {"b.pdf"}
    assert rag.delete_by_source("missing.pdf") == 0
