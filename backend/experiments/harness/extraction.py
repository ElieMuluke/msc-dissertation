"""Decision extraction — the pre-registered ``FINAL DECISION:`` regex parse.

Locked rule (PRD-A): agent output must END with
``FINAL DECISION: <escalate|dismiss|investigate>``. Operationalisation,
fixed before run 1:

- ONLY the LAST non-empty line of the output is examined; earlier
  ``FINAL DECISION:`` lines in the text are ignored entirely (they neither
  validate nor invalidate the output);
- markdown emphasis characters (``* _ ` #``) are stripped from that line;
- one trailing ``.`` or ``!`` after the label is tolerated;
- the label match is case-insensitive; the line must contain nothing else
  (single label, no prefix, no trailing words);
- anything else — no contract line as the last non-empty line, invalid
  label, extra content on the line, empty output — is the outcome
  category ``malformed`` (never excluded, never retried).

Known accepted mode: last-line selection happens BEFORE markdown
stripping, so an output whose final line is a closing code fence (```)
below a valid contract line is ``malformed`` — the contract requires the
output to *end* with the decision line, applied literally.
"""

from __future__ import annotations

import re

MALFORMED = "malformed"

_FINAL_LINE_RE = re.compile(
    r"^FINAL\s+DECISION\s*:\s*(escalate|dismiss|investigate)\s*[.!]?$",
    re.IGNORECASE,
)
_MARKDOWN_CHARS_RE = re.compile(r"[*_`#]")


def extract_decision(text: str | None) -> str:
    """Return the decision label, or ``"malformed"``."""
    if not text:
        return MALFORMED
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return MALFORMED
    last = _MARKDOWN_CHARS_RE.sub("", lines[-1]).strip()
    match = _FINAL_LINE_RE.match(last)
    return match.group(1).lower() if match else MALFORMED
