"""Per-run environment fingerprint (harness v2): GPU + host-load snapshot.

Journalled with every run so analysis can flag runs that executed under an
abnormal environment (VRAM pressure from another process, host CPU load).
``nvidia-smi`` is queried at most once every ``refresh_every`` samples (it
costs ~50-100 ms and the values move slowly at sweep timescales); between
refreshes the cached snapshot is returned. A missing or failing
``nvidia-smi`` yields ``None`` GPU fields — the fingerprint must never be
able to fail a run.

Fields (see the journal schema note in ``runner.execute_run``):

- ``gpu_name``          — e.g. ``"NVIDIA GeForce RTX 4090"`` (null if no smi)
- ``gpu_driver``        — driver version string (null if no smi)
- ``gpu_vram_used_mb``  — VRAM in use across the GPU, MiB (null if no smi)
- ``host_load_1m``      — 1-minute load average (null on platforms without)
- ``host_load_high``    — flag: 1-minute load average > CPU count
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

_SMI_QUERY = "name,driver_version,memory.used"


def _gpu_snapshot(timeout: float = 10.0) -> dict[str, Any]:
    """One nvidia-smi query; all-``None`` fields when unavailable."""
    empty: dict[str, Any] = {
        "gpu_name": None, "gpu_driver": None, "gpu_vram_used_mb": None
    }
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={_SMI_QUERY}",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=timeout,
        )
        if out.returncode != 0:
            logger.warning("nvidia-smi failed (rc=%d): %s",
                           out.returncode, out.stderr.strip())
            return empty
        # first GPU line; fields are "<name>, <driver>, <mem-used-MiB>"
        line = out.stdout.strip().splitlines()[0]
        name, driver, mem_used = (part.strip() for part in line.split(",", 2))
        return {
            "gpu_name": name,
            "gpu_driver": driver,
            "gpu_vram_used_mb": int(float(mem_used)),
        }
    except FileNotFoundError:
        return empty  # no NVIDIA stack on this host — expected, not an error
    except Exception as exc:  # never let telemetry kill a run
        logger.warning("nvidia-smi snapshot failed: %s", exc)
        return empty


def _host_load() -> dict[str, Any]:
    try:
        load_1m = os.getloadavg()[0]
    except OSError:
        return {"host_load_1m": None, "host_load_high": None}
    cpus = os.cpu_count() or 1
    return {"host_load_1m": round(load_1m, 2), "host_load_high": load_1m > cpus}


class EnvFingerprint:
    """Cached environment sampler: refreshes every ``refresh_every`` calls.

    The host-load fields are cheap and refreshed on every call; only the
    ``nvidia-smi`` GPU snapshot is cached.
    """

    def __init__(self, refresh_every: int = 25) -> None:
        if refresh_every < 1:
            raise ValueError("refresh_every must be >= 1")
        self._refresh_every = refresh_every
        self._calls = 0
        self._gpu: dict[str, Any] | None = None

    def sample(self) -> dict[str, Any]:
        """The journal-ready fingerprint dict for one run."""
        if self._gpu is None or self._calls % self._refresh_every == 0:
            self._gpu = _gpu_snapshot()
        self._calls += 1
        return {**self._gpu, **_host_load()}
