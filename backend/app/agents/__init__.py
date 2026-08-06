"""Agent-facing tools over the AML RAG corpus.

    >>> from app.ingestion.rag import build_rag
    >>> from app.agents import build_rag_tool
    >>> rag = build_rag()
    >>> tool = build_rag_tool(rag)
    >>> tool.invoke({"query": "customer due diligence threshold"})

Tools here take an already-built :class:`~app.ingestion.rag.RagSystem` (dependency
injection) and expose it as LangChain :class:`~langchain_core.tools.StructuredTool`
objects suitable for native tool calling (e.g. Ollama qwen models via ``bind_tools``).
"""

from __future__ import annotations

from .production_tools import (
    build_country_risk_tool,
    build_production_tools,
    build_query_accounts_tool,
    build_query_transactions_tool,
    build_sanctions_check_tool,
)
from .tools import build_rag_tool, build_rag_tools

__all__ = [
    "build_rag_tool",
    "build_rag_tools",
    "build_production_tools",
    "build_query_accounts_tool",
    "build_query_transactions_tool",
    "build_sanctions_check_tool",
    "build_country_risk_tool",
]
