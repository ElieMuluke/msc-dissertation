"""API tests with the RagSystem and PDF loader faked — no model download, no real PDFs."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.api.routes.rag as rag_route
from app.deps import get_generator, get_llm_ping, get_rag
from app.generation.generator import Answer, Citation, StreamChunk, StreamedAnswer
from app.ingestion.rag.models import Document, SearchResult, SourceInfo
from app.main import app
from conftest import parse_sse_frames


class FakeGenerator:
    def generate(self, query, k=5):
        return Answer(
            answer=f"Answer to: {query} [a1]",
            citations=[Citation("a1", "a.pdf", 2, 0.9)],
            used_context=True,
            contexts=["ctx"],
        )

    def stream(self, query, k=5):
        return StreamedAnswer(
            citations=[Citation("a1", "a.pdf", 2, 0.9)],
            used_context=True,
            chunks=iter(
                [
                    StreamChunk("thinking", "Let me "),
                    StreamChunk("thinking", "reason."),
                    StreamChunk("answer", "Answer "),
                    StreamChunk("answer", "to "),
                    StreamChunk("answer", f"{query} [a1]"),
                ]
            ),
        )


class FakeRag:
    def __init__(self):
        self.ingested: list[Document] = []
        self.cleared = False

    def ingest(self, documents):
        docs = list(documents)
        self.ingested += docs
        return len(docs)

    def search(self, query, k=5):
        return [SearchResult("a1", "hit text", {}, 0.9)]

    def clear(self):
        self.cleared = True

    def list_sources(self):
        return [SourceInfo("a.pdf", 3, "2026-06-17T00:00:00+00:00")]

    def delete_by_source(self, filename):
        return 0 if filename == "missing.pdf" else 2

    def ping(self):
        return True


@pytest.fixture
def client(monkeypatch):
    fake = FakeRag()
    app.dependency_overrides[get_rag] = lambda: fake
    app.dependency_overrides[get_generator] = lambda: FakeGenerator()
    app.dependency_overrides[get_llm_ping] = lambda: (lambda: True)
    # Each fake PDF yields one page so ingested count == number of files.
    monkeypatch.setattr(rag_route, "load_pdfs", lambda path: [Document(path, "t")])
    # Don't write MLflow during tests.
    monkeypatch.setattr(rag_route, "log_search", lambda *a, **k: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_multi_pdf_upload(client):
    files = [
        ("files", ("a.pdf", b"%PDF-1.4", "application/pdf")),
        ("files", ("b.pdf", b"%PDF-1.4", "application/pdf")),
    ]
    res = client.post("/rag/documents/pdf", files=files)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse_frames(res.text)

    statuses = [f["data"]["status"] for f in frames if f["event"] == "progress" and f["data"]["filename"] == "a.pdf"]
    assert statuses == ["uploading", "parsing", "vectorizing", "completed"]
    done = frames[-1]
    assert done["event"] == "done"
    assert done["data"] == {"ingested": 2}


def test_rejects_non_pdf(client):
    files = [("files", ("notes.txt", b"hello", "text/plain"))]
    res = client.post("/rag/documents/pdf", files=files)
    assert res.status_code == 200
    frames = parse_sse_frames(res.text)
    assert frames[0]["event"] == "error"
    assert "notes.txt" in frames[0]["data"]["message"]


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
        {"filename": "a.pdf", "pages": 3, "ingested_at": "2026-06-17T00:00:00+00:00"}
    ]


def test_delete_document(client):
    res = client.delete("/rag/documents/a.pdf")
    assert res.status_code == 200
    assert res.json() == {"status": "success", "deleted_filename": "a.pdf", "chunks_removed": 2}


def test_delete_document_not_found(client):
    res = client.delete("/rag/documents/missing.pdf")
    assert res.status_code == 404


def test_answer(client):
    res = client.post("/rag/answer", json={"query": "What is the CTR threshold?", "k": 3})
    assert res.status_code == 200
    body = res.json()
    assert body["used_context"] is True
    assert body["citations"][0] == {"id": "a1", "source": "a.pdf", "page": 2, "score": 0.9}
    assert "[a1]" in body["answer"]


def test_answer_stream(client):
    res = client.post("/rag/answer/stream", json={"query": "CTR?"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    body = res.text
    assert "event: thinking" in body
    assert "event: token" in body
    assert "event: done" in body

    def texts(event: str) -> list[str]:
        return [
            json.loads(line[len("data: ") :])["text"]
            for block in body.split("\n\n")
            if f"event: {event}" in block
            for line in block.splitlines()
            if line.startswith("data: ")
        ]

    # Thinking arrives on its own channel; answer tokens concatenate to the full answer.
    assert "".join(texts("thinking")) == "Let me reason."
    assert "".join(texts("token")) == "Answer to CTR? [a1]"
    done = [b for b in body.split("\n\n") if "event: done" in b][0]
    payload = json.loads(done.splitlines()[-1][len("data: ") :])
    assert payload["used_context"] is True
    assert payload["citations"][0]["id"] == "a1"


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "connected", "llm": "connected"}


def test_health_degraded_when_llm_down(client):
    app.dependency_overrides[get_llm_ping] = lambda: (lambda: False)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "degraded", "database": "connected", "llm": "disconnected"}


