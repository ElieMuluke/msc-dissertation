"""Path setup: put ``backend/`` on sys.path for ``experiments`` and ``app``.

Needed only when pytest is invoked from outside ``backend/`` (from within,
backend/pyproject.toml's ``pythonpath = ["."]`` already covers it).
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]  # …/backend
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
