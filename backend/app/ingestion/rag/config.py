"""Configuration for the AML RAG system.

A single immutable config object is injected into the system at build time so nothing
downstream hardcodes paths, model names, or store details (Dependency Inversion).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RagConfig:
    """Settings for building a :class:`RagSystem`.

    Attributes:
        persist_dir: On-disk directory for the Chroma store.
        collection_name: Chroma collection holding the corpus.
        embedding_model: sentence-transformers model id.
        distance: Vector distance metric ("cosine", "l2", or "ip").
        chunk_size: If > 0, long documents are split into chunks of this many
            characters before embedding (set for real PDF/long policies). 0 = no split.
        chunk_overlap: Character overlap between consecutive chunks.
        bm25_weight: Weight of the BM25 (lexical) side in hybrid search. 0 (default)
            = pure vector search; 1 = pure BM25. Fused as
            ``bm25_weight * bm25 + (1 - bm25_weight) * vector`` over normalized scores.
    """

    persist_dir: str = "./chroma_db"
    collection_name: str = "aml_corpus"
    embedding_model: str = "all-MiniLM-L6-v2"
    distance: str = "cosine"
    chunk_size: int = 900
    chunk_overlap: int = 150
    bm25_weight: float = 0.0
