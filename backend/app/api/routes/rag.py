"""RAG endpoints: ingest documents and search the corpus."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    CitationOut,
    DeleteResponse,
    IngestedDocument,
    SearchHit,
)
from app.api.sse import sse_frame
from app.deps import get_generator, get_rag
from app.evaluation.monitoring import log_search
from app.generation import AnswerGenerator
from app.ingestion.rag import RagSystem, load_pdfs

router = APIRouter(prefix="/rag", tags=["rag"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/documents/pdf")
async def ingest_pdfs(
    files: list[UploadFile] = File(...),
    rag: RagSystem = Depends(get_rag),
) -> StreamingResponse:
    """Ingest one or more uploaded PDFs (one document per page).

    Streams progress as Server-Sent Events instead of a single JSON response: one
    ``event: progress`` frame per milestone (``{"filename", "progress", "status"}``, status
    one of ``uploading``/``parsing``/``vectorizing``/``completed``), an ``event: error``
    frame (``{"filename", "message"}``) if a file fails — which stops processing of any
    remaining files in the same request — and, once every file has ingested successfully,
    one final ``event: done`` frame (``{"ingested": <total>}``).
    """

    async def event_stream() -> AsyncIterator[str]:
        total = 0
        # Persist under original filenames so ids/source metadata stay meaningful.
        with tempfile.TemporaryDirectory() as tmp_dir:
            for file in files:
                name = Path(file.filename or "").name
                try:
                    if not (file.filename or "").lower().endswith(".pdf"):
                        raise HTTPException(status_code=400, detail=f"Expected a .pdf file: {file.filename}")
                    yield sse_frame("progress", {"filename": name, "progress": 10, "status": "uploading"})
                    dest = Path(tmp_dir) / name
                    with dest.open("wb") as out:
                        shutil.copyfileobj(file.file, out)
                    yield sse_frame("progress", {"filename": name, "progress": 40, "status": "parsing"})
                    # Offload blocking PDF parsing + embedding to a thread so the event loop
                    # stays free and frames already yielded flush to the client promptly.
                    documents = await asyncio.to_thread(load_pdfs, str(dest))
                    yield sse_frame("progress", {"filename": name, "progress": 70, "status": "vectorizing"})
                    total += await asyncio.to_thread(rag.ingest, documents)
                    yield sse_frame("progress", {"filename": name, "progress": 100, "status": "completed"})
                except HTTPException as exc:
                    yield sse_frame("error", {"filename": name, "message": str(exc.detail)})
                    return
                except Exception as exc:  # noqa: BLE001 - report then stop
                    yield sse_frame("error", {"filename": name, "message": str(exc)})
                    return

        yield sse_frame("done", {"ingested": total})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/documents", response_model=list[IngestedDocument])
def list_documents(rag: RagSystem = Depends(get_rag)) -> list[IngestedDocument]:
    """List ingested source files (aggregated by source)."""
    return [
        IngestedDocument(
            filename=source.filename,
            pages=source.pages,
            ingested_at=source.ingested_at,
        )
        for source in rag.list_sources()
    ]


@router.delete("/documents")
def clear_documents(rag: RagSystem = Depends(get_rag)) -> dict[str, str]:
    """Clear the entire corpus."""
    rag.clear()
    return {"status": "cleared"}


@router.delete("/documents/{filename}", response_model=DeleteResponse)
def delete_document(filename: str, rag: RagSystem = Depends(get_rag)) -> DeleteResponse:
    """Delete all documents from one source file."""
    removed = rag.delete_by_source(filename)
    if removed == 0:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
    return DeleteResponse(status="success", deleted_filename=filename, chunks_removed=removed)


@router.get("/search", response_model=list[SearchHit])
def search(
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1, description="Search query"),
    k: int = Query(5, ge=1, le=50),
    rag: RagSystem = Depends(get_rag),
) -> list[SearchHit]:
    """Semantic search over the corpus."""
    start = time.perf_counter()
    results = rag.search(q, k=k)
    latency_ms = (time.perf_counter() - start) * 1000.0
    # Monitor the search in the background so logging never adds response latency.
    background_tasks.add_task(log_search, q, k, results, latency_ms)
    return [SearchHit(**vars(r)) for r in results]


@router.post("/answer", response_model=AnswerResponse)
async def answer(
    request: AnswerRequest,
    generator: AnswerGenerator = Depends(get_generator),
) -> AnswerResponse:
    """Retrieve context and generate a grounded answer with citations (local LLM)."""
    try:
        # Offload the blocking LLM call so the event loop stays free.
        result = await asyncio.to_thread(generator.generate, request.query, request.k)
    except Exception as exc:  # noqa: BLE001 - surface LLM/connection issues clearly
        raise HTTPException(status_code=503, detail=f"Generation failed (is Ollama running?): {exc}")
    return AnswerResponse(
        answer=result.answer,
        citations=[
            CitationOut(
                id=c.id,
                source=c.source,
                page=c.page if isinstance(c.page, int) else None,
                score=c.score,
            )
            for c in result.citations
        ],
        used_context=result.used_context,
    )


@router.post("/answer/stream")
def answer_stream(
    request: AnswerRequest,
    generator: AnswerGenerator = Depends(get_generator),
) -> StreamingResponse:
    """Stream a grounded answer token-by-token as Server-Sent Events.

    Emits ``thinking`` frames ``{"text": "..."}`` for the model's reasoning trace and
    ``token`` frames ``{"text": "..."}`` for the answer (interleaved, reasoning first),
    then a final ``done`` frame ``{"citations": [...], "used_context": bool}``. Any failure
    produces an ``error`` frame ``{"message": "..."}``. The body runs in a threadpool, so
    the blocking LLM stream never blocks the event loop.
    """

    def event_stream() -> Iterator[str]:
        try:
            streamed = generator.stream(request.query, request.k)
            for chunk in streamed.chunks:
                event = "thinking" if chunk.kind == "thinking" else "token"
                yield sse_frame(event, {"text": chunk.text})
        except Exception as exc:  # noqa: BLE001 - surface to the client as an error frame
            yield sse_frame("error", {"message": f"Generation failed (is Ollama running?): {exc}"})
            return
        citations = [
            CitationOut(
                id=c.id,
                source=c.source,
                page=c.page if isinstance(c.page, int) else None,
                score=c.score,
            ).model_dump()
            for c in streamed.citations
        ]
        yield sse_frame("done", {"citations": citations, "used_context": streamed.used_context})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
