"""AML RAG system — ingest financial policies and actions, then search them.

    >>> from app.ingestion.rag import build_rag, Document, DocumentType
    >>> rag = build_rag()
    >>> rag.ingest([Document("p1", "Report cash over 10,000.", DocumentType.POLICY)])
    1
    >>> rag.search("cash reporting threshold", k=3)

Built on LangChain (Chroma + sentence-transformers). Swap the store by editing
:func:`build_rag`; reach the underlying retriever via :meth:`RagSystem.as_retriever`.
"""

from __future__ import annotations

from .config import RagConfig
from .loaders import load_pdfs
from .models import Document, DocumentType, SearchResult, SourceInfo
from .rag import RagSystem, build_rag
from .section_chunking import load_pdf_sections

__all__ = [
    "RagConfig",
    "Document",
    "DocumentType",
    "SearchResult",
    "SourceInfo",
    "RagSystem",
    "build_rag",
    "load_pdfs",
    "load_pdf_sections",
]
