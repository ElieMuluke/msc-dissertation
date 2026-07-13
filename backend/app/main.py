"""FastAPI application for the AML compliance platform.

Thin HTTP layer over the ingestion/RAG code in ``app.ingestion``. Run with:

    uvicorn app.main:app --reload   # from the backend/ directory
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import rag, tabular
from app.api.schemas import HealthResponse
from app.deps import get_llm_ping, get_rag
from app.ingestion.rag import RagSystem

# `/tmp` is tmpfs (RAM-backed) on many Linux setups and can be far smaller than the
# multi-GB tabular files this app ingests (see app/api/routes/tabular.py). Both Starlette's
# multipart upload spooling and our own upload tempdir resolve through
# ``tempfile.gettempdir()``, so redirecting it once here (before any request is handled)
# fixes both call sites. Only applies if the caller hasn't already set TMPDIR themselves,
# and only if a disk-backed fallback actually exists.
_DISK_BACKED_TMP_DIR = "/var/tmp"
if "TMPDIR" not in os.environ and os.path.isdir(_DISK_BACKED_TMP_DIR):
    tempfile.tempdir = _DISK_BACKED_TMP_DIR

app = FastAPI(title="AML Compliance Platform API", version="0.1.0")

# Allow the Vite dev server (and configure real origins in deployment).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag.router)
app.include_router(tabular.router)


@app.get("/health", tags=["health"], response_model=HealthResponse)
def health(
    rag_system: RagSystem = Depends(get_rag),
    llm_ping: Callable[[], bool] = Depends(get_llm_ping),
) -> HealthResponse:
    """Report connectivity of the vector store and the local LLM for status badges."""
    db_ok = rag_system.ping()
    llm_ok = llm_ping()
    return HealthResponse(
        status="ok" if db_ok and llm_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        llm="connected" if llm_ok else "disconnected",
    )
