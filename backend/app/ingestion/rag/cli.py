"""Command-line interface for the AML RAG system.

Examples:
    python -m src.ingestion.rag.cli ingest data/aml_sample.json
    python -m src.ingestion.rag.cli search "cash transaction reporting threshold" -k 3
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import RagSystem, build_rag
from .config import RagConfig
from .loaders import load_pdfs
from .models import Document
from .section_chunking import MAX_CHUNK_CHARS, load_pdf_sections

_MINILM_MAX_SEQ_LENGTH = 256  # token window MAX_CHUNK_CHARS (1100 chars) was calibrated against


def _resolve_max_chunk_chars(rag: RagSystem) -> int:
    """Scale MAX_CHUNK_CHARS to the active embedder's actual token window.

    Falls back to the MiniLM-calibrated default when the window isn't introspectable, so
    ingesting with the default embedder produces byte-identical chunk boundaries to before.
    """
    max_seq_length = rag.embedding_max_seq_length()
    if max_seq_length is None:
        return MAX_CHUNK_CHARS
    return int(max_seq_length * MAX_CHUNK_CHARS / _MINILM_MAX_SEQ_LENGTH)


def _load_documents(path: str) -> list[Document]:
    """Load documents from a JSON array of {id, text, metadata?} objects."""
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)
    return [
        Document(
            id=row["id"],
            text=row["text"],
            metadata=row.get("metadata", {}),
        )
        for row in rows
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aml-rag", description="Ingest and search AML policies and financial actions."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest documents from a JSON file")
    ingest.add_argument("path", help="Path to a JSON array of documents")

    pdf = sub.add_parser("ingest-pdf", help="Ingest a PDF file or directory of PDFs")
    pdf.add_argument("path", help="Path to a .pdf file or a directory of PDFs")
    pdf.add_argument(
        "--chunker",
        choices=["fixed", "section"],
        default=None,
        help="fixed = per-page + character windows; section = structure-aware "
        "(default from RagConfig / RAG_CHUNKER env var)",
    )
    pdf.add_argument(
        "--parent-context",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="With --chunker section: prefix chunks with doc title + section heading "
        "(default from RagConfig / RAG_PARENT_CONTEXT env var)",
    )
    pdf.add_argument(
        "--embedding-model",
        default=None,
        help="sentence-transformers model id (default from RagConfig / RAG_EMBEDDING_MODEL env var)",
    )

    search = sub.add_parser("search", help="Search the corpus")
    search.add_argument("query", help="Natural-language query")
    search.add_argument("-k", type=int, default=5, help="Number of results (default 5)")
    for p in (ingest, pdf, search):
        p.add_argument("--collection", default=None, help="Chroma collection (default from RagConfig)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    overrides: dict = {}
    if args.collection:
        overrides["collection_name"] = args.collection
    if getattr(args, "embedding_model", None):
        overrides["embedding_model"] = args.embedding_model
    if getattr(args, "chunker", None):
        overrides["chunker"] = args.chunker
    if getattr(args, "parent_context", None) is not None:
        overrides["parent_context"] = args.parent_context
    config = RagConfig(**overrides)
    if config.chunker == "section":
        config = RagConfig(**overrides, chunk_size=0)  # store sections as-is
    rag = build_rag(config)

    if args.command == "ingest":
        count = rag.ingest(_load_documents(args.path))
        print(f"Ingested {count} documents.")
    elif args.command == "ingest-pdf":
        if config.chunker == "section":
            max_chunk_chars = _resolve_max_chunk_chars(rag)
            docs = load_pdf_sections(
                args.path, parent_context=config.parent_context, max_chunk_chars=max_chunk_chars
            )
            print(f"Ingested {rag.ingest(docs)} section chunks from {args.path}.")
        else:
            docs = load_pdfs(args.path)
            print(f"Ingested {rag.ingest(docs)} pages from {args.path}.")
    elif args.command == "search":
        results = rag.search(args.query, k=args.k)
        if not results:
            print("No matches.")
        for result in results:
            print(f"[{result.score:.3f}] {result.id}: {result.text[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
