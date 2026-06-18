"""LangChain tools that let an LLM agent query the AML RAG corpus.

The tool closes over an injected :class:`~app.ingestion.rag.RagSystem` (dependency
inversion — no client/model is constructed here), and formats results as a single
citation-annotated string, since LLM tool outputs must be plain content blocks.
"""

from __future__ import annotations

from typing import Literal, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.ingestion.rag import DocumentType, RagSystem, SearchResult

_DOC_TYPE_MAP: dict[str, DocumentType] = {
    "policy": DocumentType.POLICY,
    "action": DocumentType.ACTION,
}

_TOOL_NAME = "search_aml_corpus"

_TOOL_DESCRIPTION = (
    "Search the indexed anti-money-laundering (AML) knowledge corpus to retrieve "
    "relevant passages. The corpus has two kinds of content: JMLSG AML 'policy' "
    "guidance (rules, procedures, customer due diligence requirements) and FATF "
    "'action' recommendations (international standards, mutual evaluation follow-up "
    "actions). Call this tool whenever you need authoritative AML/CTF regulatory "
    "context to answer a question, ground a claim, or cite a source — do not rely on "
    "memory for specific rules, thresholds, or recommendation numbers. Set `doc_type` "
    "to \"policy\" to search JMLSG policy guidance only, \"action\" to search FATF "
    "actions/recommendations only, or leave it unset to search both. Use `k` to "
    "control how many passages are returned (default 4)."
)


class AmlCorpusSearchArgs(BaseModel):
    """Arguments for :func:`build_rag_tool`'s ``search_aml_corpus`` tool."""

    query: str = Field(..., description="Natural-language question or topic to search the AML corpus for.")
    doc_type: Optional[Literal["policy", "action"]] = Field(
        default=None,
        description=(
            "Restrict the search to one kind of document: 'policy' for JMLSG AML "
            "policies, 'action' for FATF actions/recommendations. Omit to search both."
        ),
    )
    k: int = Field(default=4, description="Maximum number of passages to retrieve.")


def _format_hit(result: SearchResult) -> str:
    source = result.metadata.get("source", "")
    page = result.metadata.get("page", "")
    header = f"[{result.id}] (type={result.doc_type.value}, source={source}, page={page}, score={result.score:.2f})"
    return f"{header}\n{result.text}"


def _format_results(results: list[SearchResult]) -> str:
    if not results:
        return "No matching documents found."
    return "\n\n".join(_format_hit(r) for r in results)


def build_rag_tool(rag: RagSystem) -> StructuredTool:
    """Build the ``search_aml_corpus`` tool, injecting the given :class:`RagSystem`.

    The returned tool retrieves AML knowledge (JMLSG policies and/or FATF actions)
    for an LLM agent's native tool calling, returning a formatted citation string.
    """

    def search_aml_corpus(query: str, doc_type: Optional[str] = None, k: int = 4) -> str:
        results = rag.search(query, k=k, doc_type=_DOC_TYPE_MAP.get(doc_type) if doc_type else None)
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
