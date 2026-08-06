"""API-layer session memory for production analyses (PRD-B §5).

Conversation/session context lives *here*, strictly outside the shared agent modules:
the ``arun(case, context)`` contract stays stateless (the experiment harness imports the
same modules and must measure a memory-free code path). The analysis route reads a
session's prior-analysis summaries out of this store, passes them into ``context`` as
plain data, and appends the new analysis afterwards — the agent never mutates state.

In-process only (no persistence): sessions are a UI convenience, while the durable
audit trail is the report store (``app.reports``).
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


class SessionMemory:
    """Per-session list of prior analysis summaries, keyed by an opaque session key."""

    def __init__(self, max_entries_per_session: int = 20) -> None:
        self._max = max_entries_per_session
        self._sessions: dict[str, list[dict]] = defaultdict(list)
        self._lock = Lock()

    def history(self, key: str) -> list[dict]:
        """A copy of the session's entries, oldest first (empty for unknown keys)."""
        with self._lock:
            return list(self._sessions.get(key, []))

    def append(self, key: str, entry: dict) -> None:
        """Record one completed analysis for the session, keeping the newest N."""
        with self._lock:
            entries = self._sessions[key]
            entries.append(entry)
            del entries[: -self._max]

    def clear(self, key: str) -> None:
        """Forget one session."""
        with self._lock:
            self._sessions.pop(key, None)
