"""Structure-aware section chunking for regulatory PDFs (JMLSG, FATF).

Regulatory documents carry explicit structure — numbered paragraphs (``5.3.108``,
``17.``), headed subsections, Recommendation boundaries. This module splits at those
boundaries instead of fixed character windows, so each chunk is a complete semantic
unit (a full rule/recommendation/paragraph) rather than a token-window slice.

Pipeline per PDF: load pages -> strip repeated page headers/footers -> split at
*validated* paragraph-number line starts -> peel trailing heading lines onto the next
section -> merge undersized neighbours under the same heading -> sentence-sub-split
oversized sections to ``MAX_CHUNK_CHARS`` (the ``all-MiniLM-L6-v2`` embedder truncates
at 256 tokens ≈ 1100 chars, so bigger chunks would be half-invisible to retrieval).

Boundary validation matters: raw PDF text wraps mid-sentence, so a line starting with
``5.6.34 – 5.6.35).`` may be a cross-reference, not a paragraph start. A number line
only opens a new section when the previous line ended a sentence (or was a heading)
and the number is followed by a capital/quote — cutting false splits from TOC lines
and inline references.

Public surface: :func:`load_pdf_sections` (mirrors :func:`loaders.load_pdfs` but
section-aware, with an optional parent-context prefix per chunk).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Optional

from .cleaning import clean_pdf_text
from .models import Document

# A paragraph-number line start: "5.3.108 Some...", "17. When...", "4.12. A credit...".
# Requires an upper-case/digit/quote after the number so lowercase continuations
# ("5.3.139 to 5.3.142)") never match.
_PARA_NUM = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+[\"'“(]?[A-Z0-9]")
_ALL_CAPS = re.compile(r"^[A-Z][A-Z0-9 ,&/\-\.\(\)’']{3,79}$")
_SENTENCE_END = re.compile(r"(?<=[.;:!?])\s+")

MAX_CHUNK_CHARS = 1100  # ≈256 tokens: the embedder's window; also far under rerankers' 512
_MIN_MERGE_CHARS = 350  # grow smaller sections by merging same-heading neighbours
_ORPHAN_CHARS = 120  # fragments below this are glued to the previous chunk regardless


def _strip_repeated_lines(pages: list[str]) -> list[str]:
    """Remove per-page headers/footers: edge lines recurring on >=20% of pages."""
    counts: Counter[str] = Counter()
    for text in pages:
        lines = text.splitlines()
        for line in set(l.strip() for l in (lines[:3] + lines[-3:]) if l.strip()):
            counts[re.sub(r"\d+", "#", line)] += 1
    threshold = max(3, len(pages) // 5)
    frequent = {k for k, v in counts.items() if v >= threshold}
    return [
        "\n".join(l for l in t.splitlines() if not l.strip() or re.sub(r"\d+", "#", l.strip()) not in frequent)
        for t in pages
    ]


def _heading_like(line: str) -> bool:
    """A short line without sentence-final punctuation, e.g. 'Higher risks'."""
    line = line.strip()
    return bool(
        line
        and len(line) <= 80
        and line[-1] not in ".;:,)"
        and not _PARA_NUM.match(line)
        and any(c.isalpha() for c in line)
        and len(line.split()) <= 12
    )


def _valid_boundary(prev_nonempty: Optional[str], line: str) -> bool:
    if not _PARA_NUM.match(line):
        return False
    if prev_nonempty is None or not prev_nonempty.strip():
        return True
    prev = prev_nonempty.strip()
    return prev[-1] in ".;:!?)”\"'" or _heading_like(prev) or bool(_ALL_CAPS.match(prev))


def split_sections(pages: list[str]) -> list[tuple[str, int, str]]:
    """Split raw page texts into ``(heading, start_page, text)`` sections.

    Sections open at validated paragraph-number boundaries. Trailing heading-like
    lines of a section belong to the *next* one and are peeled off as its heading.
    """
    sections: list[tuple[str, int, str]] = []
    heading = ""
    cur: list[str] = []
    cur_page = 0
    prev_nonempty: Optional[str] = None

    def flush() -> str:
        nonlocal cur
        trailing: list[str] = []
        while cur and (not cur[-1].strip() or _heading_like(cur[-1]) or _ALL_CAPS.match(cur[-1].strip())):
            line = cur.pop().strip()
            if line:
                trailing.insert(0, line)
            if len(trailing) >= 2:
                break
        text = "\n".join(cur).strip()
        if text:
            sections.append((heading, cur_page, text))
        cur = []
        return " ".join(trailing)

    for page_no, text in enumerate(pages):
        for line in text.splitlines():
            stripped = line.strip()
            if _valid_boundary(prev_nonempty, stripped):
                new_heading = flush()
                if new_heading:
                    heading = new_heading
                cur_page = page_no
            if not cur:
                cur_page = page_no
            cur.append(line)
            if stripped:
                prev_nonempty = line
    flush()
    return sections


def _merge_small(sections: list[tuple[str, int, str]], max_chunk_chars: int = MAX_CHUNK_CHARS) -> list[list]:
    """Merge undersized sections into same-heading neighbours (complete units only)."""
    out: list[list] = []
    for heading, page, text in sections:
        if out and out[-1][0] == heading and len(out[-1][2]) < _MIN_MERGE_CHARS and len(out[-1][2]) + len(text) <= max_chunk_chars:
            out[-1][2] += "\n" + text
        elif out and len(text) < _ORPHAN_CHARS and len(out[-1][2]) + len(text) <= max_chunk_chars:
            out[-1][2] += "\n" + text
        else:
            out.append([heading, page, text])
    return out


def _sub_split(text: str, limit: int) -> list[str]:
    """Split an oversized section at sentence boundaries into <=limit pieces."""
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        if current and len(current) + len(sentence) + 1 > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence
        while len(current) > limit:  # single sentence longer than the limit (tables)
            pieces.append(current[:limit])
            current = current[limit:]
    if current:
        pieces.append(current)
    return pieces


def _doc_title(stem: str) -> str:
    """Short human title for a corpus file, used as chunk parent context."""
    s = stem.lower()
    if "jmlsg" in s:
        part = "Part II" if ("part-ii" in s or "part_ii" in s or "part ii" in s) else "Part I"
        return f"JMLSG Guidance {part}"
    if "fatf recommendations" in s:
        return "FATF Recommendations"
    if "universal-procedures" in s:
        return "FATF Universal Procedures"
    if "icrg" in s:
        return "FATF Assessment & ICRG Procedures"
    return re.sub(r"[-_.]+", " ", re.sub(r"\.pdf.*$", "", stem)).strip()


def load_pdf_sections(
    path: str,
    metadata: Optional[dict] = None,
    parent_context: bool = False,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
) -> list[Document]:
    """Load PDF(s) into section-aligned :class:`Document` chunks.

    Mirrors :func:`loaders.load_pdfs` but chunks along document structure instead of
    pages+fixed windows. Ids are ``<filename>-s<n>``; metadata keeps ``source``,
    ``page`` (section start page) and ``section`` (nearest heading) for traceability.
    Pass the result to :meth:`RagSystem.ingest` with chunking disabled
    (``RagConfig(chunk_size=0)``) so chunks are stored exactly as produced.

    Args:
        parent_context: When True, prefix each chunk with its document title and
            section heading (``[JMLSG Guidance Part I — Higher risks] ...``) so the
            embedding and the LLM see where the text sits in the document.
        max_chunk_chars: Defaults to the ``all-MiniLM-L6-v2``-calibrated
            :data:`MAX_CHUNK_CHARS`; pass a larger value when ingesting with a
            longer-context embedder so chunks use its full window.
    """
    from langchain_community.document_loaders import PyPDFLoader

    target = Path(path)
    files = sorted(target.glob("*.pdf")) if target.is_dir() else [target]
    base_meta = metadata or {}

    documents: list[Document] = []
    for pdf in files:
        pages = _strip_repeated_lines([p.page_content for p in PyPDFLoader(str(pdf)).load()])
        title = _doc_title(pdf.stem)
        index = 0
        for heading, page_no, text in _merge_small(split_sections(pages), max_chunk_chars):
            prefix = ""
            if parent_context:
                label = f"{title} — {heading}" if heading else title
                prefix = f"[{label}] "
            for piece in _sub_split(clean_pdf_text(text), max_chunk_chars - len(prefix)):
                documents.append(
                    Document(
                        id=f"{pdf.stem}-s{index}",
                        text=prefix + piece,
                        metadata={**base_meta, "source": pdf.name, "page": page_no, "section": heading},
                    )
                )
                index += 1
    return documents
