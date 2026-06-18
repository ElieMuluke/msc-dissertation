"""Normalize raw PDF-extracted text before embedding.

Pure text transforms (no I/O) so they are unit-testable and reusable independent of the
PDF loader. Applied to each page's content in :func:`load_pdfs` prior to building
:class:`Document` models, to keep extraction noise out of the embedding space.
"""

from __future__ import annotations

import re

# Mis-extracted PDF glyphs/ligatures -> standard characters.
_GLYPHS = {"": "©", "ﬁ": "fi", "ﬂ": "fl"}

# Control characters that clutter embeddings: C0 controls (minus \t\n), DEL, and C1
# controls. Printable Latin-1 (\xa0-\xff: ©, é, ü, ...) is deliberately preserved.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_HYPHEN_JOIN = re.compile(r"(\w+)-\s*\n\s*(\w+)")
_SINGLE_BREAK = re.compile(r"(?<=[^\n])\n(?=[^\n])")
_SPACES = re.compile(r"[ \t]+")


def clean_pdf_text(text: str) -> str:
    """Return ``text`` normalized: glyphs, control chars, line joins, spacing.

    Steps: map known glyphs/ligatures to standard chars; strip control characters; join
    words hyphen-split across line breaks; turn single line breaks inside paragraphs into
    spaces (double breaks kept as paragraph gaps); collapse runs of spaces/tabs.
    """
    if not text:
        return ""
    for glyph, replacement in _GLYPHS.items():
        text = text.replace(glyph, replacement)
    text = _CONTROL.sub("", text)
    text = _HYPHEN_JOIN.sub(r"\1\2", text)
    text = _SINGLE_BREAK.sub(" ", text)
    text = _SPACES.sub(" ", text)
    return text.strip()
