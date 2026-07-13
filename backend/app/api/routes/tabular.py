"""Tabular AML dataset endpoints: upload HI-Large CSV/TXT files, view ingested volumes."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import IO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.schemas import TabularCounts, TabularIngestResponse, TabularLocalIngestRequest, TabularTextIngestRequest
from app.api.sse import bridge_thread_progress, sse_frame
from app.deps import get_tabular
from app.ingestion.tabular import ByteCountingReader, CsvValidationError, TabularDataType, TabularSystem

router = APIRouter(prefix="/tabular", tags=["tabular"])

_ALLOWED_EXTENSIONS: dict[TabularDataType, tuple[str, ...]] = {
    TabularDataType.ACCOUNTS: (".csv",),
    TabularDataType.TRANSACTIONS: (".csv",),
    TabularDataType.PATTERNS: (".csv", ".txt"),
}

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def _ingest_file_with_progress(
    data_type: TabularDataType,
    name: str,
    size: int,
    open_binary: Callable[[], IO[bytes]],
    tabular: TabularSystem,
) -> AsyncIterator[dict]:
    """Ingest one file, yielding byte-based progress dicts as ingestion proceeds.

    Yields ``{"progress": int, "status": "uploading"|"inserting"}`` dicts as ingestion
    proceeds, ending with one ``{"progress": 100, "status": "completed", "ingested": int}``
    dict carrying the final row count. ``open_binary`` is a zero-arg callable returning a
    fresh binary file object — deferred so nothing is opened before ingestion actually
    starts — which is wrapped in a :class:`ByteCountingReader` and read directly by
    ``TabularSystem.ingest`` (no second on-disk copy, no separate row-count pass; see
    ``docs/tabular.md`` for the perf rationale). Progress percent is derived from bytes
    read against ``size`` rather than an exact row count.

    Raises whatever ``TabularSystem.ingest`` raises; shared by both the upload endpoint and
    the local-path endpoint, whose only difference is how ``open_binary`` opens the file.
    """
    yield {"progress": 10, "status": "uploading"}
    fileobj = open_binary()
    try:
        reader = ByteCountingReader(fileobj)
        result: dict[str, int] = {}

        def work(emit: Callable[[dict], None]) -> None:
            def on_batch(_done: int) -> None:
                pct = 10 + int(reader.bytes_read / size * 89) if size else 90
                emit({"progress": min(pct, 99), "status": "inserting"})

            result["ingested"] = tabular.ingest(data_type, reader, name, on_batch)

        async for frame in bridge_thread_progress(work):
            yield frame
    finally:
        fileobj.close()

    yield {"progress": 100, "status": "completed", "ingested": result["ingested"]}


@router.post("/ingest")
async def ingest(
    data_type: TabularDataType = Form(...),
    files: list[UploadFile] = File(...),
    tabular: TabularSystem = Depends(get_tabular),
) -> StreamingResponse:
    """Ingest one or more uploaded HI-Large tabular files for the selected ``data_type``.

    Streams progress as Server-Sent Events instead of a single JSON response: one
    ``event: progress`` frame per milestone/batch (``{"filename", "progress", "status"}``),
    an ``event: error`` frame (``{"filename", "message"}``) if a file fails — which stops
    processing of any remaining files in the same request — and, once every file has
    ingested successfully, one final ``event: done`` frame
    (``{"ingested": <total>, "data_type": ...}``). For files too large to comfortably
    round-trip over HTTP, use ``POST /tabular/ingest/local`` instead (reads directly from a
    server-local path, no upload).
    """
    allowed = _ALLOWED_EXTENSIONS[data_type]

    async def event_stream() -> AsyncIterator[str]:
        total = 0
        for file in files:
            name = Path(file.filename or "").name
            if not name.lower().endswith(allowed):
                yield sse_frame(
                    "error",
                    {"filename": name, "message": f"Expected one of {allowed} for {data_type.value}: {file.filename}"},
                )
                return
            try:
                async for frame in _ingest_file_with_progress(
                    data_type, name, file.size or 0, lambda f=file: f.file, tabular
                ):
                    ingested = frame.pop("ingested", None)
                    yield sse_frame("progress", {"filename": name, **frame})
                    if ingested is not None:
                        total += ingested
            except Exception as exc:  # noqa: BLE001 - report then stop
                yield sse_frame("error", {"filename": name, "message": str(exc)})
                return

        yield sse_frame("done", {"ingested": total, "data_type": data_type.value})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/ingest/local")
async def ingest_local(
    request: TabularLocalIngestRequest,
    tabular: TabularSystem = Depends(get_tabular),
) -> StreamingResponse:
    """Ingest a tabular file already sitting on the server's local disk, by path.

    Bypasses HTTP upload entirely: no multipart body. Meant for very large source files
    (e.g. multi-GB transaction dumps) where uploading over HTTP is both slow and, on hosts
    where ``/tmp`` is a small tmpfs, prone to running out of space mid-upload. Streams the
    same Server-Sent Event frame shape as ``POST /tabular/ingest`` (see its docstring).
    """
    path = Path(request.path)
    name = path.name
    allowed = _ALLOWED_EXTENSIONS[request.data_type]

    async def event_stream() -> AsyncIterator[str]:
        if not path.is_file():
            yield sse_frame("error", {"filename": name, "message": f"No such file: {request.path}"})
            return
        if not name.lower().endswith(allowed):
            yield sse_frame(
                "error",
                {"filename": name, "message": f"Expected one of {allowed} for {request.data_type.value}: {name}"},
            )
            return

        size = os.path.getsize(path)
        total = 0
        try:
            async for frame in _ingest_file_with_progress(
                request.data_type, name, size, lambda: open(path, "rb"), tabular
            ):
                ingested = frame.pop("ingested", None)
                yield sse_frame("progress", {"filename": name, **frame})
                if ingested is not None:
                    total = ingested
        except Exception as exc:  # noqa: BLE001 - report then stop
            yield sse_frame("error", {"filename": name, "message": str(exc)})
            return

        yield sse_frame("done", {"ingested": total, "data_type": request.data_type.value})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/ingest/text", response_model=TabularIngestResponse)
async def ingest_text(
    request: TabularTextIngestRequest,
    tabular: TabularSystem = Depends(get_tabular),
) -> TabularIngestResponse:
    """Ingest raw CSV/TXT text pasted (not uploaded as a file) for the selected ``data_type``.

    The entire payload is validated as well-formed before any DB write (see
    ``TabularSystem.ingest_text``): a malformed row anywhere returns ``422`` with the list
    of problems and leaves the database untouched, no partial inserts. Plain JSON
    request/response (unlike the file-upload paths, which stream SSE progress) — pasted
    text is small enough for a synchronous-feeling request.
    """
    try:
        ingested = await asyncio.to_thread(tabular.ingest_text, request.data_type, request.csv_text)
    except CsvValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    return TabularIngestResponse(ingested=ingested, data_type=request.data_type.value)


@router.get("/counts", response_model=TabularCounts)
def counts(tabular: TabularSystem = Depends(get_tabular)) -> TabularCounts:
    """Current ingested row counts, for a frontend volumes display."""
    result = tabular.counts()
    return TabularCounts(**result)


@router.delete("/data")
def clear_data(tabular: TabularSystem = Depends(get_tabular)) -> dict[str, str]:
    """Clear all ingested tabular data (accounts + transactions)."""
    tabular.clear()
    return {"status": "cleared"}
