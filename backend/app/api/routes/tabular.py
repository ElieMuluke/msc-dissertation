"""Tabular AML dataset endpoints: upload HI-Large CSV/TXT files, view ingested volumes."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.schemas import TabularCounts, TabularIngestResponse
from app.deps import get_tabular
from app.ingestion.tabular import TabularDataType, TabularSystem
from app.ingestion.tabular.loaders import count_rows
from app.realtime import manager, progress_frame

router = APIRouter(prefix="/tabular", tags=["tabular"])

_ALLOWED_EXTENSIONS: dict[TabularDataType, tuple[str, ...]] = {
    TabularDataType.ACCOUNTS: (".csv",),
    TabularDataType.TRANSACTIONS: (".csv",),
    TabularDataType.PATTERNS: (".csv", ".txt"),
}


@router.post("/ingest", response_model=TabularIngestResponse)
async def ingest(
    data_type: TabularDataType = Form(...),
    files: list[UploadFile] = File(...),
    tabular: TabularSystem = Depends(get_tabular),
) -> TabularIngestResponse:
    """Ingest one or more uploaded HI-Large tabular files for the selected ``data_type``.

    Broadcasts per-file progress frames over the ``/ws`` WebSocket gateway (mirrors
    ``ingest_pdfs`` in ``app/api/routes/rag.py``).
    """
    allowed = _ALLOWED_EXTENSIONS[data_type]
    ingested = 0
    with tempfile.TemporaryDirectory() as tmp_dir:
        for file in files:
            name = Path(file.filename or "").name
            try:
                if not name.lower().endswith(allowed):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Expected one of {allowed} for {data_type.value}: {file.filename}",
                    )
                await manager.broadcast(progress_frame(name, 10, "uploading"))
                dest = Path(tmp_dir) / name
                with dest.open("wb") as out:
                    shutil.copyfileobj(file.file, out)

                # Off the event loop: files can be huge.
                total = await asyncio.to_thread(count_rows, str(dest), data_type)
                loop = asyncio.get_running_loop()

                def on_batch(done: int, _total: int = total, _name: str = name) -> None:
                    pct = 10 + int(done / _total * 89) if _total else 90
                    pct = min(pct, 99)
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast(progress_frame(_name, pct, "inserting")), loop
                    )

                ingested += await asyncio.to_thread(tabular.ingest, data_type, str(dest), name, on_batch)
                await manager.broadcast(progress_frame(name, 100, "completed"))
            except HTTPException as exc:
                await manager.broadcast(progress_frame(name, 0, "error", str(exc.detail)))
                raise
            except Exception as exc:  # noqa: BLE001 - report then surface
                await manager.broadcast(progress_frame(name, 0, "error", str(exc)))
                raise

    return TabularIngestResponse(ingested=ingested, data_type=data_type.value)


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
