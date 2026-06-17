"""Labeled evaluation datasets.

A retrieval dataset is a JSONL file where each line is
``{"query": "...", "relevant_ids": ["id1", "id2"]}``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QueryExample:
    """A query paired with the ids of the documents that should be retrieved."""

    query: str
    relevant_ids: frozenset[str]


def load_queries(path: str | Path) -> list[QueryExample]:
    """Load query examples from a JSONL file."""
    examples: list[QueryExample] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        examples.append(QueryExample(row["query"], frozenset(row["relevant_ids"])))
    return examples
