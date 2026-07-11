"""Domain models for the AML RAG corpus.

Documents are generic ingestable text units (regulatory text, procedures, case notes,
or anything else) represented as a :class:`Document`. There is no type-based
classification of content — every document is stored and searched the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    """A single ingestable unit of text.

    Attributes:
        id: Stable unique identifier (re-ingesting the same id upserts).
        text: The natural-language content to embed and search.
        metadata: Arbitrary primitive (str/int/float/bool) fields, e.g.
            ``{"jurisdiction": "UK", "regulation": "MLR 2017"}``.
    """

    id: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    """A scored hit returned by a search.

    Attributes:
        id: Identifier of the matched document.
        text: The matched document's text.
        metadata: The document's metadata.
        score: Similarity in ``[0, 1]`` (higher is closer; ``1 - cosine_distance``).
    """

    id: str
    text: str
    metadata: dict
    score: float


@dataclass(frozen=True)
class SourceInfo:
    """An ingested source file, aggregated across its pages/chunks.

    Attributes:
        filename: The source filename (``metadata.source``).
        pages: Number of stored documents (pages/chunks) from this source.
        ingested_at: ISO-8601 timestamp of the earliest ingestion of this source.
    """

    filename: str
    pages: int
    ingested_at: str
