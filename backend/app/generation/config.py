"""Configuration for answer generation via a local Ollama LLM."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationConfig:
    """Settings for the generation LLM.

    Defaults target a local Ollama server. Override the model with the ``OLLAMA_MODEL``
    env var or by passing a config explicitly.
    """

    model: str = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    temperature: float = 0.1
