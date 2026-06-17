"""Request/response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel

from app.ingestion.rag import DocumentType


class SearchHit(BaseModel):
    id: str
    text: str
    doc_type: DocumentType
    metadata: dict
    score: float


class IngestResponse(BaseModel):
    ingested: int


class IngestedDocument(BaseModel):
    filename: str
    doc_type: DocumentType
    pages: int
    ingested_at: str


class DeleteResponse(BaseModel):
    status: str
    deleted_filename: str
    chunks_removed: int
