"""Backend application package.

Loads ``backend/.env`` at import time so every entry point (FastAPI app and the
``python -m app.evaluation.*`` CLIs) sees the same config. Precedence: real shell
environment > ``.env`` > in-code defaults (``os.getenv(..., default)``). ``override=False``
keeps an already-exported shell variable authoritative over the ``.env`` value.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
