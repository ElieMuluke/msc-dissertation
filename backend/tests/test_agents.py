"""Tests for the search_aml_corpus agent tool, with the RagSystem faked."""

from __future__ import annotations

from app.agents import build_rag_tool
from app.ingestion.rag.models import DocumentType, SearchResult


class FakeRag:
    def __init__(self, results=None):
        self._results = results if results is not None else [SearchResult("a1", "hit text", DocumentType.POLICY, {"source": "a.pdf", "page": 2}, 0.9)]
        self.last_query = None
        self.last_k = None
        self.last_doc_type = None

    def search(self, query, k=5, doc_type=None):
        self.last_query = query
        self.last_k = k
        self.last_doc_type = doc_type
        return self._results


def test_tool_metadata():
    tool = build_rag_tool(FakeRag())
    assert tool.name == "search_aml_corpus"
    assert tool.description
    fields = tool.args_schema.model_fields
    assert "query" in fields
    assert "doc_type" in fields
    assert "k" in fields


def test_invoke_returns_formatted_hit():
    tool = build_rag_tool(FakeRag())
    result = tool.invoke({"query": "customer due diligence"})
    assert "a1" in result
    assert "a.pdf" in result
    assert "2" in result
    assert "hit text" in result


def test_doc_type_action_maps_to_enum():
    fake = FakeRag()
    tool = build_rag_tool(fake)
    tool.invoke({"query": "FATF recommendation 10", "doc_type": "action"})
    assert fake.last_doc_type == DocumentType.ACTION


def test_doc_type_none_passes_none():
    fake = FakeRag()
    tool = build_rag_tool(fake)
    tool.invoke({"query": "any AML topic"})
    assert fake.last_doc_type is None


def test_no_results_returns_clear_message():
    tool = build_rag_tool(FakeRag(results=[]))
    result = tool.invoke({"query": "nonexistent topic"})
    assert result == "No matching documents found."
