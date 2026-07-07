"""AML RAG system built on LangChain (Chroma + sentence-transformers).

Domain types (:class:`Document`, :class:`DocumentType`, :class:`SearchResult`) are kept
independent of LangChain so application code never depends on the framework directly —
the store can be swapped (FAISS, pgvector, Pinecone) by changing :func:`build_rag` alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document as LCDocument
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import RagConfig
from .hybrid import Bm25Index, fuse
from .models import Document, DocumentType, SearchResult, SourceInfo

_DOC_TYPE_KEY = "doc_type"
_SOURCE_KEY = "source"
_INGESTED_AT_KEY = "ingested_at"


class RagSystem:
    """Ingest AML policies and financial actions, then search them semantically.

    With ``bm25_weight > 0`` search runs hybrid: BM25 lexical scores are fused with
    vector relevance scores (see :mod:`.hybrid`). The BM25 index is built lazily from
    the store's current contents and invalidated by any write (ingest/delete/clear).
    """

    def __init__(
        self,
        vectorstore: Chroma,
        splitter: Optional[RecursiveCharacterTextSplitter] = None,
        bm25_weight: float = 0.0,
    ) -> None:
        self._store = vectorstore
        self._splitter = splitter
        self._bm25_weight = bm25_weight
        self._bm25_index: Optional[Bm25Index] = None

    def ingest(self, documents: Iterable[Document]) -> int:
        """Embed and persist documents (upsert by id). Returns the number stored.

        If a text splitter is configured, long documents are chunked; chunk ids are
        suffixed ``#0``, ``#1``, ... so the source document stays traceable.
        """
        ingested_at = datetime.now(timezone.utc).isoformat()
        lc_docs: list[LCDocument] = []
        ids: list[str] = []
        for doc in documents:
            metadata = {**doc.metadata, _DOC_TYPE_KEY: doc.doc_type.value, _INGESTED_AT_KEY: ingested_at}
            chunks = self._splitter.split_text(doc.text) if self._splitter else [doc.text]
            for i, chunk in enumerate(chunks):
                lc_docs.append(LCDocument(page_content=chunk, metadata=metadata))
                ids.append(doc.id if len(chunks) == 1 else f"{doc.id}#{i}")
        if not lc_docs:
            return 0
        self._store.add_documents(lc_docs, ids=ids)
        self._bm25_index = None  # store changed; lexical index is stale
        return len(lc_docs)

    def search(self, query: str, k: int = 5, doc_type: Optional[DocumentType] = None) -> list[SearchResult]:
        """Return the top-``k`` matches, optionally restricted to one document type."""
        where = {_DOC_TYPE_KEY: doc_type.value} if doc_type is not None else None
        if self._bm25_weight > 0:
            return self._hybrid_search(query, k, where)
        hits = self._store.similarity_search_with_relevance_scores(query, k=k, filter=where)
        return [_to_result(doc, score) for doc, score in hits]

    def _hybrid_search(self, query: str, k: int, where: Optional[dict]) -> list[SearchResult]:
        """Fuse BM25 and vector scores over a wide candidate pool; return top-``k``."""
        pool = max(30, 5 * k)
        vector_hits = self._store.similarity_search_with_relevance_scores(query, k=pool, filter=where)
        vector_scores = {doc.id: float(score) for doc, score in vector_hits}
        by_id = {doc.id: doc for doc, _ in vector_hits}
        if self._bm25_index is None:
            data = self._store.get(include=["documents", "metadatas"])
            self._bm25_index = Bm25Index(
                data.get("ids") or [], data.get("documents") or [], data.get("metadatas") or []
            )
        bm25_scores = self._bm25_index.scores(query, where=where, top_n=pool)
        top = fuse(vector_scores, bm25_scores, self._bm25_weight, k)
        missing = [cid for cid, _ in top if cid not in by_id]
        if missing:
            fetched = self._store.get_by_ids(missing)
            by_id.update({doc.id: doc for doc in fetched})
        return [_to_result(by_id[cid], score) for cid, score in top if cid in by_id]

    def as_retriever(self, **kwargs):
        """Expose a LangChain retriever for downstream LLM chains / agents."""
        return self._store.as_retriever(**kwargs)

    def clear(self) -> None:
        """Delete all documents by resetting the underlying collection."""
        self._store.reset_collection()
        self._bm25_index = None

    def ping(self) -> bool:
        """Return ``True`` if the vector store is reachable."""
        try:
            self._store.get(limit=1)
            return True
        except Exception:  # noqa: BLE001 - any failure means unreachable
            return False

    def list_sources(self) -> list[SourceInfo]:
        """List ingested source files, aggregating pages/chunks per source."""
        data = self._store.get(include=["metadatas"])
        aggregated: dict[str, dict] = {}
        for meta in data.get("metadatas") or []:
            meta = meta or {}
            source = meta.get(_SOURCE_KEY)
            if not source:
                continue  # e.g. docs ingested without a source file
            entry = aggregated.setdefault(
                source,
                {
                    "doc_type": meta.get(_DOC_TYPE_KEY, DocumentType.POLICY.value),
                    "pages": 0,
                    "ingested_at": meta.get(_INGESTED_AT_KEY, ""),
                },
            )
            entry["pages"] += 1
            ingested_at = meta.get(_INGESTED_AT_KEY, "")
            if ingested_at and (not entry["ingested_at"] or ingested_at < entry["ingested_at"]):
                entry["ingested_at"] = ingested_at  # keep earliest
        return [
            SourceInfo(
                filename=source,
                doc_type=DocumentType(entry["doc_type"]),
                pages=entry["pages"],
                ingested_at=entry["ingested_at"],
            )
            for source, entry in aggregated.items()
        ]

    def delete_by_source(self, filename: str) -> int:
        """Delete all documents from one source file. Returns the number removed."""
        ids = self._store.get(where={_SOURCE_KEY: filename}).get("ids") or []
        if ids:
            self._store.delete(ids=ids)
            self._bm25_index = None
        return len(ids)


def _to_result(doc: LCDocument, score: float) -> SearchResult:
    metadata = dict(doc.metadata)
    doc_type = DocumentType(metadata.pop(_DOC_TYPE_KEY, DocumentType.POLICY.value))
    return SearchResult(
        id=doc.id or metadata.get("id", ""),
        text=doc.page_content,
        doc_type=doc_type,
        metadata=metadata,
        score=float(score),
    )


def build_rag(config: Optional[RagConfig] = None) -> RagSystem:
    """Wire embeddings + Chroma into a ready :class:`RagSystem` from a :class:`RagConfig`."""
    config = config or RagConfig()
    embeddings = HuggingFaceEmbeddings(
        model_name=config.embedding_model,
        encode_kwargs={"normalize_embeddings": True},
    )
    store = Chroma(
        collection_name=config.collection_name,
        embedding_function=embeddings,
        persist_directory=config.persist_dir,
        collection_metadata={"hnsw:space": config.distance},
    )
    splitter = (
        RecursiveCharacterTextSplitter(chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)
        if config.chunk_size > 0
        else None
    )
    return RagSystem(store, splitter, bm25_weight=config.bm25_weight)
