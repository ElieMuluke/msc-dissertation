"""Best-effort git checkpointing of ``experiments/results/``.

Called by the runner every N completed runs. Never raises: any add/commit/
push failure is logged and retried on the next cycle — a sync problem must
never kill the sweep (PRD-A component 5). A file lock serialises the two
arm runners so they cannot race each other in the git index; only the
results directory is committed (``git commit -- <path>``), so concurrent
work elsewhere in the tree is never swept into a checkpoint commit.
"""

from __future__ import annotations

import fcntl
import logging
import subprocess
from pathlib import Path

from experiments.config import REPO_ROOT, RESULTS_DIR

logger = logging.getLogger(__name__)

_LOCK_FILE = RESULTS_DIR / ".git-sync.lock"


def _git(repo: Path, *args: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=timeout,
    )


def sync_results(
    message: str,
    repo_root: Path = REPO_ROOT,
    results_dir: Path = RESULTS_DIR,
) -> bool:
    """Add, commit and push the results directory. Returns push success."""
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        with open(_LOCK_FILE, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            rel = str(results_dir.relative_to(repo_root))
            add = _git(repo_root, "add", "--", rel)
            if add.returncode != 0:
                logger.warning("git add failed: %s", add.stderr.strip())
            commit = _git(repo_root, "commit", "-m", message, "--", rel)
            if commit.returncode != 0 and "nothing to commit" not in (
                commit.stdout + commit.stderr
            ):
                logger.warning("git commit failed: %s", commit.stderr.strip())
            push = _git(repo_root, "push")
            if push.returncode != 0:
                logger.warning(
                    "git push failed (will retry next cycle): %s", push.stderr.strip()
                )
                return False
            logger.info("results synced: %s", message)
            return True
    except Exception as exc:  # never let git problems kill the sweep
        logger.warning("git sync error (will retry next cycle): %s", exc)
        return False
