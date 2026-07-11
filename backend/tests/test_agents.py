"""Tests for the search_aml_corpus agent tool, with the RagSystem faked."""

from __future__ import annotations

from app.agents import build_rag_tool
from app.ingestion.rag.models import SearchResult


class FakeRag:
    def __init__(self, results=None):
        self._results = (
            results
            if results is not None
            else [SearchResult("a1", "hit text", {"source": "a.pdf", "page": 2}, 0.9)]
        )
        self.last_query = None
        self.last_k = None

    def search(self, query, k=5):
        self.last_query = query
        self.last_k = k
        return self._results


def test_tool_metadata():
    tool = build_rag_tool(FakeRag())
    assert tool.name == "search_aml_corpus"
    assert tool.description
    fields = tool.args_schema.model_fields
    assert "query" in fields
    assert "k" in fields


def test_invoke_returns_formatted_hit():
    tool = build_rag_tool(FakeRag())
    result = tool.invoke({"query": "customer due diligence"})
    assert "a1" in result
    assert "a.pdf" in result
    assert "2" in result
    assert "hit text" in result


def test_no_results_returns_clear_message():
    tool = build_rag_tool(FakeRag(results=[]))
    result = tool.invoke({"query": "nonexistent topic"})
    assert result == "No matching documents found."
