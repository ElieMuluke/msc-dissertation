"""Shared Server-Sent Event helpers for streaming request-scoped progress over HTTP.

Three routes stream progress back to the client as SSE instead of broadcasting to the
formerly-shared `/ws` WebSocket gateway (superseded, see `app/api/routes/tabular.py` and
`app/api/routes/rag.py`): `POST /tabular/ingest`, `POST /tabular/ingest/local`, and
`POST /rag/documents/pdf`. `POST /rag/answer/stream` already established the SSE-on-response
pattern this module generalizes. This module holds the two pieces those routes have in
common: formatting one SSE frame, and bridging a blocking, thread-based producer of progress
updates to an async generator consumer.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any


def sse_frame(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame: ``event: <event>\\ndata: <json>\\n\\n``."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def bridge_thread_progress(work: Callable[[Callable[[dict], None]], Any]) -> AsyncIterator[dict]:
    """Run blocking ``work`` in a thread, yielding the progress dicts it reports as they arrive.

    ``work`` is called (in a worker thread) with one argument: an ``emit(frame)`` callback
    it may call any number of times to report progress. Each ``emit`` call is queued onto
    the running event loop via ``loop.call_soon_threadsafe`` and yielded here as soon as it
    arrives — not buffered until ``work`` returns — so a ``StreamingResponse`` built on top
    of this generator actually streams incrementally instead of appearing to hang until the
    whole blocking operation finishes.

    If ``work`` raises, the exception propagates from this generator (after any frames
    queued before the failure have been yielded), so the caller can catch it and emit a
    final ``error`` SSE frame — mirroring ``routes/rag.py``'s pre-existing ``answer_stream``
    error-frame pattern.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Any] = asyncio.Queue()
    done = object()

    def emit(frame: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, frame)

    def run() -> None:
        try:
            work(emit)
        except Exception as exc:  # noqa: BLE001 - forwarded to the async consumer, not swallowed
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, done)

    thread_task = asyncio.create_task(asyncio.to_thread(run))
    try:
        while True:
            item = await queue.get()
            if item is done:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        await thread_task
