"""Unit tests for the WebSocket ConnectionManager and progress frames (no real sockets)."""

from __future__ import annotations

import asyncio

from app.realtime import ConnectionManager, progress_frame


class FakeWS:
    def __init__(self, fail: bool = False):
        self.sent: list[dict] = []
        self.fail = fail
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self.fail:
            raise RuntimeError("dead connection")
        self.sent.append(message)


def test_progress_frame_shape():
    frame = progress_frame("a.pdf", 70, "vectorizing")
    assert frame["event"] == "ingestion_progress"
    assert frame["data"] == {
        "filename": "a.pdf",
        "progress": 70,
        "status": "vectorizing",
        "error_message": None,
    }


def test_connect_and_broadcast():
    manager = ConnectionManager()
    ws = FakeWS()
    asyncio.run(manager.connect(ws))
    assert ws.accepted and ws in manager.active
    asyncio.run(manager.broadcast(progress_frame("a.pdf", 100, "completed")))
    assert ws.sent[0]["data"]["status"] == "completed"


def test_broadcast_drops_dead_connections():
    manager = ConnectionManager()
    ws = FakeWS(fail=True)
    asyncio.run(manager.connect(ws))
    asyncio.run(manager.broadcast(progress_frame("a.pdf", 0, "error", "boom")))
    assert ws not in manager.active
