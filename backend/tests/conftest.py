"""Shared test helpers."""

from __future__ import annotations

import json


def parse_sse_frames(body: str) -> list[dict]:
    """Parse a Server-Sent Events response body into ``[{"event": str, "data": dict}, ...]``.

    Used by tests exercising the SSE-streaming ingestion endpoints (``POST
    /tabular/ingest``, ``/ingest/local``, ``POST /rag/documents/pdf``) and
    ``POST /rag/answer/stream``, which all emit ``event: <name>\\ndata: <json>\\n\\n`` frames
    (see ``app/api/sse.py``).
    """
    frames: list[dict] = []
    for block in body.strip().split("\n\n"):
        if not block:
            continue
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        frames.append({"event": event, "data": data})
    return frames
