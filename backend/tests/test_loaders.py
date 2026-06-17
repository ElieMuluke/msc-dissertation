"""Unit tests for the PDF loader adapter (PyPDFLoader is faked — we test our mapping)."""

from __future__ import annotations

from langchain_core.documents import Document as LCDocument

import app.ingestion.rag.loaders as loaders
from app.ingestion.rag.models import DocumentType


class FakeLoader:
    def __init__(self, path):
        self.path = path

    def load(self):
        return [
            LCDocument(page_content="page one", metadata={"page": 0}),
            LCDocument(page_content="page two", metadata={"page": 1}),
        ]


def test_load_pdf_file(tmp_path, monkeypatch):
    monkeypatch.setattr(loaders, "PyPDFLoader", FakeLoader)
    pdf = tmp_path / "policy.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    docs = loaders.load_pdfs(str(pdf), DocumentType.POLICY)

    assert [d.id for d in docs] == ["policy-p0", "policy-p1"]
    assert all(d.doc_type is DocumentType.POLICY for d in docs)
    assert docs[0].metadata == {"source": "policy.pdf", "page": 0}


def test_load_pdf_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(loaders, "PyPDFLoader", FakeLoader)
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4")

    docs = loaders.load_pdfs(str(tmp_path), DocumentType.ACTION)

    assert {d.metadata["source"] for d in docs} == {"a.pdf", "b.pdf"}
    assert all(d.doc_type is DocumentType.ACTION for d in docs)
