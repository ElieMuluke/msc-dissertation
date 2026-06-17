"""Prompt construction for grounded answer generation (pure, testable)."""

from __future__ import annotations

from collections.abc import Sequence

from app.ingestion.rag import SearchResult

SYSTEM_INSTRUCTION = (
    "You are an AML compliance assistant. Answer the question using ONLY the provided "
    "context. Cite the documents you rely on by their [id]. If the context does not "
    "contain enough information to answer, say so plainly and do not invent facts."
)


def _format_context(results: Sequence[SearchResult]) -> str:
    if not results:
        return "(no relevant documents found)"
    blocks = []
    for r in results:
        source = r.metadata.get("source", "?")
        page = r.metadata.get("page", "?")
        blocks.append(f"[{r.id}] (source: {source}, page: {page})\n{r.text}")
    return "\n\n".join(blocks)


def build_prompt(query: str, results: Sequence[SearchResult]) -> str:
    """Build the full prompt from the question and retrieved context."""
    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"Context:\n{_format_context(results)}\n\n"
        f"Question: {query}\n\n"
        "Answer (cite sources by [id]):"
    )
