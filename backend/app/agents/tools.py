"""LangChain tools that let an LLM agent query the AML RAG corpus.

The tool closes over an injected :class:`~app.ingestion.rag.RagSystem` (dependency
inversion — no client/model is constructed here), and formats results as a single
citation-annotated string, since LLM tool outputs must be plain content blocks.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.ingestion.rag import RagSystem, SearchResult

_TOOL_NAME = "search_aml_corpus"

_TOOL_DESCRIPTION = (
    "Search the indexed anti-money-laundering (AML) regulatory knowledge corpus to "
    "retrieve relevant passages. Call this tool whenever you need authoritative AML/CTF "
    "regulatory context to answer a question, ground a claim, or cite a source — do not "
    "rely on memory for specific rules, thresholds, or recommendation numbers. Use `k` to "
    "control how many passages are returned (default 4)."
)


class AmlCorpusSearchArgs(BaseModel):
    """Arguments for :func:`build_rag_tool`'s ``search_aml_corpus`` tool."""

    query: str = Field(..., description="Natural-language question or topic to search the AML corpus for.")
    k: int = Field(default=4, description="Maximum number of passages to retrieve.")


def _format_hit(result: SearchResult) -> str:
    source = result.metadata.get("source", "")
    page = result.metadata.get("page", "")
    header = f"[{result.id}] (source={source}, page={page}, score={result.score:.2f})"
    return f"{header}\n{result.text}"


def _format_results(results: list[SearchResult]) -> str:
    if not results:
        return "No matching documents found."
    return "\n\n".join(_format_hit(r) for r in results)


def build_rag_tool(rag: RagSystem) -> StructuredTool:
    """Build the ``search_aml_corpus`` tool, injecting the given :class:`RagSystem`.

    The returned tool retrieves AML regulatory knowledge for an LLM agent's native
    tool calling, returning a formatted citation string.
    """

    def search_aml_corpus(query: str, k: int = 4) -> str:
        results = rag.search(query, k=k)
        return _format_results(results)

    return StructuredTool.from_function(
        func=search_aml_corpus,
        name=_TOOL_NAME,
        description=_TOOL_DESCRIPTION,
        args_schema=AmlCorpusSearchArgs,
    )


def build_rag_tools(rag: RagSystem) -> list[StructuredTool]:
    """Build all RAG-backed tools for binding to an agent, e.g. ``llm.bind_tools(...)``."""
    return [build_rag_tool(rag)]
