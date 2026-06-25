"""Configuration for answer generation via a local Ollama LLM."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationConfig:
    """Settings for the generation LLM.

    Defaults target a local Ollama server. Override the model with the ``OLLAMA_MODEL``
    env var or by passing a config explicitly. ``qwen3.5:2b`` is the default: small enough
    to stay fast on CPU yet supports native tool calling for the planned agent layer.

    Attributes:
        num_predict: Cap on generated tokens — bounds worst-case latency.
        num_ctx: Context window; large enough for a few retrieved chunks plus the prompt.
        keep_alive: How long Ollama keeps the model resident, so it is not reloaded
            (and re-read from disk) on every request.
        reasoning: Whether to let the model emit a ``<think>`` reasoning trace. When on,
            Qwen3 routes reasoning into ``additional_kwargs['reasoning_content']`` (not
            ``content``), which the API streams on a separate ``thinking`` channel for a
            collapsible UI panel. Default OFF and env-gated (``OLLAMA_REASONING``): the
            local ``qwen3.5:2b`` over-thinks — reasoning fills any ``num_predict`` budget
            and the answer text never gets emitted — so enabling it only makes sense behind
            a model whose reasoning converges. ``num_predict`` must cover reasoning *and*
            leave room for the answer when this is on.
    """

    model: str = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = 0.1
    num_predict: int = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
    num_ctx: int = 4096
    keep_alive: str = "30m"
    reasoning: bool = os.getenv("OLLAMA_REASONING", "").lower() in {"1", "true", "yes"}
