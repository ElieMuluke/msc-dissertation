"""API tests with the RagSystem and PDF loader faked — no model download, no real PDFs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.api.routes.rag as rag_route
from app.deps import get_rag
from app.ingestion.rag.models import Document, DocumentType, SearchResult, SourceInfo
from app.main import app


class FakeRag:
    def __init__(self):
        self.ingested: list[Document] = []
        self.cleared = False

    def ingest(self, documents):
        docs = list(documents)
        self.ingested += docs
        return len(docs)

    def search(self, query, k=5, doc_type=None):
        return [SearchResult("a1", "hit text", DocumentType.POLICY, {}, 0.9)]

    def clear(self):
        self.cleared = True

    def list_sources(self):
        return [SourceInfo("a.pdf", DocumentType.POLICY, 3, "2026-06-17T00:00:00+00:00")]

    def delete_by_source(self, filename):
        return 0 if filename == "missing.pdf" else 2


@pytest.fixture
def client(monkeypatch):
    fake = FakeRag()
    app.dependency_overrides[get_rag] = lambda: fake
    # Each fake PDF yields one page so ingested count == number of files.
    monkeypatch.setattr(rag_route, "load_pdfs", lambda path, dt: [Document(path, "t", dt)])
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_multi_pdf_upload(client):
    files = [
        ("files", ("a.pdf", b"%PDF-1.4", "application/pdf")),
        ("files", ("b.pdf", b"%PDF-1.4", "application/pdf")),
    ]
    res = client.post("/rag/documents/pdf", files=files, data={"doc_type": "policy"})
    assert res.status_code == 200
    assert res.json() == {"ingested": 2}


def test_rejects_non_pdf(client):
    files = [("files", ("notes.txt", b"hello", "text/plain"))]
    res = client.post("/rag/documents/pdf", files=files, data={"doc_type": "policy"})
    assert res.status_code == 400


def test_search(client):
    res = client.get("/rag/search", params={"q": "money laundering"})
    assert res.status_code == 200
    assert res.json()[0]["id"] == "a1"


def test_clear_documents(client):
    res = client.delete("/rag/documents")
    assert res.status_code == 200
    assert res.json() == {"status": "cleared"}


def test_list_documents(client):
    res = client.get("/rag/documents")
    assert res.status_code == 200
    assert res.json() == [
        {"filename": "a.pdf", "doc_type": "policy", "pages": 3, "ingested_at": "2026-06-17T00:00:00+00:00"}
    ]


def test_delete_document(client):
    res = client.delete("/rag/documents/a.pdf")
    assert res.status_code == 200
    assert res.json() == {"status": "success", "deleted_filename": "a.pdf", "chunks_removed": 2}


def test_delete_document_not_found(client):
    res = client.delete("/rag/documents/missing.pdf")
    assert res.status_code == 404


def test_ws_ingestion_progress(client):
    with client.websocket_connect("/ws") as ws:
        res = client.post(
            "/rag/documents/pdf",
            files=[("files", ("a.pdf", b"%PDF-1.4", "application/pdf"))],
            data={"doc_type": "policy"},
        )
        assert res.status_code == 200
        frames = [ws.receive_json() for _ in range(4)]
    statuses = [f["data"]["status"] for f in frames]
    assert statuses == ["uploading", "parsing", "vectorizing", "completed"]
    assert all(f["event"] == "ingestion_progress" for f in frames)
