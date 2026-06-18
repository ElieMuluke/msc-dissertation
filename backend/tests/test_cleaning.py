"""Unit tests for PDF text normalization."""

from __future__ import annotations

from app.ingestion.rag.cleaning import clean_pdf_text


def test_empty():
    assert clean_pdf_text("") == ""


def test_glyphs_and_ligatures():
    #  is the mis-extracted copyright glyph; ﬁ is the "fi" ligature.
    assert clean_pdf_text("Copyright ") == "Copyright \xa9"
    assert clean_pdf_text("ﬁnancial") == "financial"


def test_strips_control_chars_but_keeps_latin1():
    assert clean_pdf_text("a\x00b\x07c") == "abc"
    # © and accented chars must survive (not in the control range).
    assert clean_pdf_text("caf\xe9 \xa9") == "caf\xe9 \xa9"


def test_joins_hyphenated_line_break():
    assert clean_pdf_text("trans-\naction") == "transaction"


def test_single_break_to_space_double_break_kept():
    assert clean_pdf_text("line one\nline two") == "line one line two"
    assert clean_pdf_text("para one\n\npara two") == "para one\n\npara two"


def test_collapses_spaces_and_trims():
    assert clean_pdf_text("  a\t\t b   c  ") == "a b c"
