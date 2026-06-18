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
    """

    model: str = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = 0.1
    num_predict: int = 384
    num_ctx: int = 4096
    keep_alive: str = "30m"
