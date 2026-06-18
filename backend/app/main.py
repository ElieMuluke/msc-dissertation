"""FastAPI application for the AML compliance platform.

Thin HTTP layer over the ingestion/RAG code in ``app.ingestion``. Run with:

    uvicorn app.main:app --reload   # from the backend/ directory
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import rag
from app.api.schemas import HealthResponse
from app.deps import get_llm_ping, get_rag
from app.ingestion.rag import RagSystem
from app.realtime import manager

app = FastAPI(title="AML Compliance Platform API", version="0.1.0")

# Allow the Vite dev server (and configure real origins in deployment).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag.router)


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


@app.websocket("/ws")
async def ingestion_progress_ws(websocket: WebSocket) -> None:
    """Push ingestion progress frames to connected clients."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client messages are ignored
    except WebSocketDisconnect:
        manager.disconnect(websocket)
