"""Domain models for the AML RAG corpus.

Two kinds of content are ingested and searched: anti-money-laundering *policies*
(rules, procedures, regulatory text) and financial *actions* (transactions, events,
case notes). Both are represented as a :class:`Document` tagged with a
:class:`DocumentType`, which lets searches be filtered to one kind or the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DocumentType(str, Enum):
    """Kind of content stored in the corpus."""

    POLICY = "policy"
    ACTION = "action"


@dataclass(frozen=True)
class Document:
    """A single ingestable unit of text.

    Attributes:
        id: Stable unique identifier (re-ingesting the same id upserts).
        text: The natural-language content to embed and search.
        doc_type: Whether this is a policy or a financial action.
        metadata: Arbitrary primitive (str/int/float/bool) fields, e.g.
            ``{"jurisdiction": "UK", "regulation": "MLR 2017"}``.
    """

    id: str
    text: str
    doc_type: DocumentType
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    """A scored hit returned by a search.

    Attributes:
        id: Identifier of the matched document.
        text: The matched document's text.
        doc_type: Policy or action.
        metadata: The document's metadata (without the internal doc_type field).
        score: Similarity in ``[0, 1]`` (higher is closer; ``1 - cosine_distance``).
    """

    id: str
    text: str
    doc_type: DocumentType
    metadata: dict
    score: float


@dataclass(frozen=True)
class SourceInfo:
    """An ingested source file, aggregated across its pages/chunks.

    Attributes:
        filename: The source filename (``metadata.source``).
        doc_type: Policy or action.
        pages: Number of stored documents (pages/chunks) from this source.
        ingested_at: ISO-8601 timestamp of the earliest ingestion of this source.
    """

    filename: str
    doc_type: DocumentType
    pages: int
    ingested_at: str
