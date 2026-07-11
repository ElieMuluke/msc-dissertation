"""Request/response schemas for the API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.ingestion.tabular import TabularDataType


class SearchHit(BaseModel):
    id: str
    text: str
    metadata: dict
    score: float


class IngestResponse(BaseModel):
    ingested: int


class IngestedDocument(BaseModel):
    filename: str
    pages: int
    ingested_at: str


class DeleteResponse(BaseModel):
    status: str
    deleted_filename: str
    chunks_removed: int


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded"
    database: str  # "connected" | "disconnected"
    llm: str  # "connected" | "disconnected"


class AnswerRequest(BaseModel):
    query: str
    k: int = 4


class CitationOut(BaseModel):
    id: str
    source: str
    page: Optional[int] = None
    score: float


class AnswerResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    used_context: bool


class TabularIngestResponse(BaseModel):
    ingested: int
    data_type: str


class TabularLocalIngestRequest(BaseModel):
    data_type: TabularDataType
    path: str


class TabularCounts(BaseModel):
    accounts: int
    transactions: int
