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

from . import build_rag
from .config import RagConfig
from .loaders import load_pdfs
from .models import Document
from .section_chunking import load_pdf_sections


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
        default="fixed",
        help="fixed = per-page + character windows (default); section = structure-aware",
    )
    pdf.add_argument(
        "--parent-context",
        action="store_true",
        help="With --chunker section: prefix chunks with doc title + section heading",
    )

    search = sub.add_parser("search", help="Search the corpus")
    search.add_argument("query", help="Natural-language query")
    search.add_argument("-k", type=int, default=5, help="Number of results (default 5)")
    for p in (ingest, pdf, search):
        p.add_argument("--collection", default=None, help="Chroma collection (default from RagConfig)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    config = RagConfig(**({"collection_name": args.collection} if args.collection else {}))
    if getattr(args, "chunker", None) == "section":
        config = RagConfig(collection_name=config.collection_name, chunk_size=0)  # store sections as-is
    rag = build_rag(config)

    if args.command == "ingest":
        count = rag.ingest(_load_documents(args.path))
        print(f"Ingested {count} documents.")
    elif args.command == "ingest-pdf":
        if args.chunker == "section":
            docs = load_pdf_sections(args.path, parent_context=args.parent_context)
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
