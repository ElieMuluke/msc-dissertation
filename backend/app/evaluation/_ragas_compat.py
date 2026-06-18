"""Compatibility shim — import this before ``ragas``.

``ragas`` calls ``nest_asyncio.apply()`` at import time. On Python >= 3.13 that monkeypatch
breaks ``asyncio.timeout()`` (raising "Timeout should be used inside a task"), which makes
every ragas metric silently fail and return ``NaN``. Our evaluation runners drive ragas
from a plain event loop with no already-running loop, so nest_asyncio is unnecessary here —
neutralize it so the import-time ``apply()`` is a no-op and timeouts keep working.

Importing this module (for its side effect) must happen before any ``import ragas``.
"""

from __future__ import annotations

import nest_asyncio

nest_asyncio.apply = lambda *args, **kwargs: None
