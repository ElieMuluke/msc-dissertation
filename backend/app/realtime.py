"""WebSocket gateway for broadcasting realtime ingestion progress.

A single :class:`ConnectionManager` fans out ``ingestion_progress`` frames to all connected
clients. Dead connections are dropped on the next broadcast.
"""

from __future__ import annotations

from typing import Literal

from fastapi import WebSocket

Status = Literal["uploading", "parsing", "vectorizing", "completed", "error"]


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts JSON frames to them."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for websocket in list(self.active):
            try:
                await websocket.send_json(message)
            except Exception:  # noqa: BLE001 - drop any unusable connection
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


def progress_frame(filename: str, progress: int, status: Status, error: str | None = None) -> dict:
    """Build an ``ingestion_progress`` frame."""
    return {
        "event": "ingestion_progress",
        "data": {
            "filename": filename,
            "progress": progress,
            "status": status,
            "error_message": error,
        },
    }


# Shared application-wide gateway.
manager = ConnectionManager()
