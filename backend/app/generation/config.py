"""Configuration for answer generation via a local Ollama LLM."""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.ingestion.rag.config import RagConfig

# Per-embedder calibrated defaults for scope_gate_threshold, keyed by RagConfig.embedding_model
# (see that field's docstring for how "active embedder" resolves). Consulted only when
# SCOPE_GATE_THRESHOLD isn't set explicitly — an explicit env var always wins. An embedder not
# in this table falls back to the all-MiniLM-L6-v2 value rather than guessing.
_SCOPE_GATE_DEFAULTS = {
    "all-MiniLM-L6-v2": 0.46,
    "BAAI/bge-small-en-v1.5": 0.638,
}


def resolve_scope_gate_threshold(embedding_model: str) -> float:
    """Per-embedder default scope-gate threshold, honoring an explicit env override.

    ``GenerationConfig``'s own field default calls this with the *env-derived*
    ``RagConfig().embedding_model`` — correct for callers (e.g. the live app) that never
    override the embedder outside ``RAG_EMBEDDING_MODEL``. Callers that resolve the
    embedder differently per-invocation (e.g. ``ragas_run.py``'s ``--embedding-model`` CLI
    flag, which can diverge from the env var) must call this explicitly with their own
    resolved ``RagConfig.embedding_model`` and pass the result into
    ``GenerationConfig(scope_gate_threshold=...)`` — the field default alone, evaluated once
    at import time, cannot see a later per-invocation CLI override.
    """
    return float(os.getenv("SCOPE_GATE_THRESHOLD", str(_SCOPE_GATE_DEFAULTS.get(embedding_model, 0.46))))


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
            relevance is below this value; 0 (or negative) disables the gate. Defaults to a
            per-embedder value (see ``resolve_scope_gate_threshold``/``_SCOPE_GATE_DEFAULTS``)
            selected by ``RagConfig.embedding_model``:
            - ``all-MiniLM-L6-v2`` -> ``0.46``, calibrated 2026-07 on collection
              ``aml_sections_b`` (out-of-scope max 0.4585, next golden 0.4758).
            - ``BAAI/bge-small-en-v1.5`` -> ``0.638``, calibrated 2026-07 on collection
              ``aml_sections_c`` (out-of-scope max 0.6513, next golden 0.6392 — note the
              ranges *overlap*: no threshold separates all 13 out-of-scope queries from all
              57 golden questions without a false gate. 0.638 catches 12/13 with zero false
              gates; the one miss, a prompt-injection attempt, is still caught by the
              generator's own scope-refusal instruction as a second line of defense. An
              initial calibration of 0.58 was found to be based on contaminated
              out-of-scope confidence data from a since-reproduced-stable collection state
              and was corrected after independent re-verification — see SESSION_LOG.md.
            Set ``SCOPE_GATE_THRESHOLD`` explicitly to override the lookup for any embedder,
            including ones not yet calibrated (which otherwise fall back to the MiniLM
            value). This field's own default only sees the env-derived embedder
            (``RAG_EMBEDDING_MODEL``) — a caller that resolves the embedder differently
            per-invocation (e.g. a CLI flag) must call ``resolve_scope_gate_threshold``
            explicitly with its own resolved model.
    """

    model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = 0.1
    num_predict: int = int(os.getenv("OLLAMA_NUM_PREDICT", "2048"))
    num_ctx: int = 4096
    keep_alive: str = "30m"
    reasoning: bool = os.getenv("OLLAMA_REASONING", "").lower() in {"1", "true", "yes"}
    scope_gate_threshold: float = resolve_scope_gate_threshold(RagConfig().embedding_model)
