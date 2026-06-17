"""FastAPI application for the AML compliance platform.

Thin HTTP layer over the ingestion/RAG code in ``app.ingestion``. Run with:

    uvicorn app.main:app --reload   # from the backend/ directory
"""

from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import rag
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


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def ingestion_progress_ws(websocket: WebSocket) -> None:
    """Push ingestion progress frames to connected clients."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client messages are ignored
    except WebSocketDisconnect:
        manager.disconnect(websocket)
