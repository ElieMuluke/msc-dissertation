"""Unit tests for structure-aware section chunking (pure text logic, no PDFs)."""

from __future__ import annotations

from app.ingestion.rag.section_chunking import (
    MAX_CHUNK_CHARS,
    _merge_small,
    _strip_repeated_lines,
    _sub_split,
    _valid_boundary,
    split_sections,
)


def test_valid_boundary_accepts_paragraph_start_after_sentence_end():
    assert _valid_boundary("previous sentence ends here.", "5.3.108 Some customers may not")
    assert _valid_boundary(None, "17. When an assessed country")
    assert _valid_boundary("Customers who cannot provide the standard evidence", "5.3.109 The FCA Rules")


def test_valid_boundary_rejects_cross_references_and_continuations():
    # lowercase after the number = a wrapped cross-reference, not a paragraph start
    assert not _valid_boundary("(see paragraphs", "5.3.139 to 5.3.142)")
    # mid-sentence previous line = the number is part of flowing text
    assert not _valid_boundary("as agent for that firm (see paragraphs", "5.6.34 – 5.6.35). More text")
    assert not _valid_boundary("ends mid sentence with no punctuation and is quite a long line overall indeed", "12. Continuation")


def test_split_sections_peels_trailing_heading_onto_next_section():
    pages = [
        "1. First paragraph body ends here.\nCustomers who cannot provide the standard evidence\n2. Second paragraph body."
    ]
    sections = split_sections(pages)
    assert len(sections) == 2
    assert sections[0][2].startswith("1. First")
    assert sections[1][0] == "Customers who cannot provide the standard evidence"
    assert sections[1][2].startswith("2. Second")


def test_merge_small_joins_same_heading_neighbours():
    sections = [["H", 0, "short one."], ["H", 0, "short two."], ["Other", 1, "x" * 400]]
    merged = _merge_small(sections)
    assert len(merged) == 2
    assert "short one." in merged[0][2] and "short two." in merged[0][2]


def test_sub_split_respects_limit_and_keeps_sentences():
    text = " ".join(f"Sentence number {i} is here." for i in range(100))
    pieces = _sub_split(text, 200)
    assert all(len(p) <= 200 for p in pieces)
    assert "".join(pieces).replace(" ", "") == text.replace(" ", "")


def test_strip_repeated_lines_drops_page_headers():
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
    pages = [f"THE FATF RECOMMENDATIONS\n{i} 2012-2025\nParagraph about {words[i]} matters." for i in range(10)]
    stripped = _strip_repeated_lines(pages)
    assert all("THE FATF RECOMMENDATIONS" not in p for p in stripped)
    assert all(f"Paragraph about {words[i]} matters." in stripped[i] for i in range(10))


def test_chunks_fit_embedder_window():
    assert MAX_CHUNK_CHARS <= 1200  # ~256 tokens for all-MiniLM-L6-v2
