"""Load real PDF policy/action documents into the RAG domain model."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader

from .models import Document, DocumentType


def load_pdfs(
    path: str,
    doc_type: DocumentType = DocumentType.POLICY,
    metadata: Optional[dict] = None,
) -> list[Document]:
    """Load a PDF file, or every ``*.pdf`` in a directory, into :class:`Document` objects.

    One document is produced per page. The page number and source filename are kept in
    metadata for regulatory traceability; ids are ``<filename>-p<page>``. Pass the result
    to :meth:`RagSystem.ingest` (set ``RagConfig.chunk_size`` to chunk long pages).
    """
    target = Path(path)
    files = sorted(target.glob("*.pdf")) if target.is_dir() else [target]
    base_meta = metadata or {}

    documents: list[Document] = []
    for pdf in files:
        for page in PyPDFLoader(str(pdf)).load():
            page_no = page.metadata.get("page", 0)
            documents.append(
                Document(
                    id=f"{pdf.stem}-p{page_no}",
                    text=page.page_content,
                    doc_type=doc_type,
                    metadata={**base_meta, "source": pdf.name, "page": page_no},
                )
            )
    return documents
