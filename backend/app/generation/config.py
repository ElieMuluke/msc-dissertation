"""Configuration for answer generation via a local Ollama LLM."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationConfig:
    """Settings for the generation LLM.

    Defaults target a local Ollama server. Override the model with the ``OLLAMA_MODEL``
    env var or by passing a config explicitly. ``llama3.2:3b`` is the default: small enough
    to stay fast on CPU yet supports native tool calling for the planned agent layer.

    Attributes:
        num_predict: Cap on generated tokens — bounds worst-case latency. Reasoning models
            (e.g. ``deepseek-r1``, Qwen3 with ``reasoning`` on) spend an unbounded prefix of
            this budget on their ``<think>`` trace; a too-small cap lets that trace consume
            the whole budget and leaves zero or a truncated answer, so the default must
            cover a typical reasoning trace *and* a full answer (see 2026-07 eval run: a
            512-token cap produced empty/mid-word-truncated answers from ``deepseek-r1:14b``
            on several golden-set questions). Matches the ``num_predict=2048`` already used
            for the RAGAS judge LLM in ``ragas_run.py``.
        num_ctx: Context window; large enough for a few retrieved chunks plus the prompt.
        keep_alive: How long Ollama keeps the model resident, so it is not reloaded
            (and re-read from disk) on every request.
        reasoning: Whether to let the model emit a ``<think>`` reasoning trace. When on,
            Qwen3 routes reasoning into ``additional_kwargs['reasoning_content']`` (not
            ``content``), which the API streams on a separate ``thinking`` channel for a
            collapsible UI panel. Default OFF and env-gated (``OLLAMA_REASONING``): small
            local Qwen3 models over-think — reasoning fills any ``num_predict`` budget and
            the answer text never gets emitted — so enabling it only makes sense behind a
            model whose reasoning converges (and is moot for the default ``llama3.2:3b``,
            which emits no ``<think>`` trace). ``num_predict`` must cover reasoning *and*
            leave room for the answer when this is on.
        scope_gate_threshold: Refuse-without-generating when the query's top-1 raw vector
            relevance is below this value; 0 (or negative) disables the gate. Env-tunable
            via ``SCOPE_GATE_THRESHOLD``. Calibrated 2026-07 for all-MiniLM-L6-v2 cosine
            relevance on collection ``aml_sections_b`` (out-of-scope max 0.4585, next
            golden 0.4758); re-calibrate if the embedder or corpus changes.
    """

    model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = 0.1
    num_predict: int = int(os.getenv("OLLAMA_NUM_PREDICT", "2048"))
    num_ctx: int = 4096
    keep_alive: str = "30m"
    reasoning: bool = os.getenv("OLLAMA_REASONING", "").lower() in {"1", "true", "yes"}
    scope_gate_threshold: float = float(os.getenv("SCOPE_GATE_THRESHOLD", "0.46"))
