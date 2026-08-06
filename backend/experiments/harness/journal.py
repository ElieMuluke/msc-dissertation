"""Append-only JSONL journal with fsync, resume keys, and progress file.

One journal per arm (``results/journal-{arm}.jsonl``), one JSON object per
line, schema per PRD-A. Every append is flushed and fsynced before the
runner moves on, so a crash loses at most the in-flight run. Resume is
journal-driven: completed runs are keyed by ``(case_id, arm, condition,
repeat_idx)`` and skipped on restart.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, IO

logger = logging.getLogger(__name__)

#: The resume identity of one run.
RunKey = tuple[str, str, str, int]


def journal_path(results_dir: Path, arm: str) -> Path:
    return results_dir / f"journal-{arm}.jsonl"


def _heal_torn_tail(path: Path) -> None:
    """Drop a partial trailing line left by a kill mid-write (F1).

    A ``kill -9`` between ``write`` and fsync can leave a torn final line
    with no trailing newline; appending straight after it would merge two
    runs into one corrupt line — silently losing the new run from resume
    and later crashing :func:`read_journal` in BOTH arm runners (progress
    reads both journals). Truncating back to the last complete line keeps
    the journal strictly valid; the torn run simply re-runs, which is the
    intended crash semantics. Only the owning runner calls this (on open
    for append) — readers never mutate the file.
    """
    if not path.exists() or path.stat().st_size == 0:
        return
    data = path.read_bytes()
    if data.endswith(b"\n"):
        return
    keep = data.rfind(b"\n") + 1  # 0 when no complete line survives
    logger.warning(
        "healing torn journal tail in %s: dropping %d partial bytes",
        path, len(data) - keep,
    )
    with open(path, "rb+") as fh:
        fh.truncate(keep)
        fh.flush()
        os.fsync(fh.fileno())


class Journal:
    """Append-only, fsynced JSONL writer for one arm."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: IO[str] | None = None

    def append(self, record: dict[str, Any]) -> None:
        """Write one run record durably (write, flush, fsync)."""
        if self._fh is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _heal_torn_tail(self.path)
            self._fh = open(self.path, "a", encoding="utf-8")
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> Journal:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def read_journal(path: Path) -> list[dict[str, Any]]:
    """Read all valid journal lines, tolerating a torn final line.

    A crash mid-write can leave one partial trailing line; it is skipped with
    a warning (the run it belonged to simply re-runs). A corrupt line
    anywhere else is an integrity error and raises.
    """
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                logger.warning("skipping torn final journal line in %s", path)
                continue
            raise
    return records


def run_key(record: dict[str, Any]) -> RunKey:
    return (record["case_id"], record["arm"], record["condition"], int(record["repeat_idx"]))


def completed_keys(path: Path) -> set[RunKey]:
    """The resume set: identities of all runs already journalled."""
    return {run_key(r) for r in read_journal(path)}


def write_progress(results_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Write ``results/progress.json`` atomically from the journals.

    Called after every run by whichever arm runner finished it; totals come
    from the manifest, done counts from both journals, per-arm ETA from the
    mean wall clock of that arm's last 20 runs.
    """
    arms: dict[str, Any] = {}
    total_done = 0
    total_planned = 0
    for arm, planned in manifest["totals"].items():
        records = read_journal(journal_path(results_dir, arm))
        recent = [r.get("wall_clock_s", 0.0) for r in records[-20:]]
        mean_s = (sum(recent) / len(recent)) if recent else None
        remaining = planned - len(records)
        arms[arm] = {
            "done": len(records),
            "total": planned,
            "last_run_at": records[-1]["started_at"] if records else None,
            "mean_wall_clock_s": round(mean_s, 2) if mean_s is not None else None,
            "eta_s": round(mean_s * remaining, 0) if mean_s is not None else None,
        }
        total_done += len(records)
        total_planned += planned
    progress = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "done": total_done,
        "total": total_planned,
        "arms": arms,
    }
    target = results_dir / "progress.json"
    # Unique tmp name per call (F2): both arm runners write progress after
    # every run; a shared tmp path lets them race on truncate/rename and kill
    # one runner with FileNotFoundError. pid + uuid covers processes and
    # threads alike; os.replace stays atomic per writer, last writer wins.
    tmp = results_dir / f".progress-{os.getpid()}-{uuid.uuid4().hex[:8]}.tmp"
    tmp.write_text(json.dumps(progress, indent=2))
    os.replace(tmp, target)
    return progress
