"""Ollama model factory and server introspection for the harness.

The factory closes over the arm's base URL and builds a fresh ``ChatOllama``
per run with that run's temperature and seed (from :class:`RunContext`).
Thinking is disabled via the API parameter (``reasoning=False`` in
langchain-ollama, which sends ``think: false`` on the wire — verified in the
G0 probe). top_p / top_k / min_p are left at Ollama server defaults per the
locked design constants; they are recorded in the manifest, not set here.
"""

from __future__ import annotations

from typing import Any

import httpx
from langchain_ollama import ChatOllama

from app.agents.contract import RunContext
from app.agents.single import ModelFactory
from experiments.config import ExperimentConfig


def make_model_factory(config: ExperimentConfig, arm: str) -> ModelFactory:
    """Build the per-run model factory for one arm's dedicated server."""
    base_url = config.base_url(arm)

    def factory(context: RunContext) -> ChatOllama:
        return ChatOllama(
            model=config.model,
            base_url=base_url,
            temperature=context.temperature,
            seed=context.seed,
            reasoning=False if not config.think else None,
            num_ctx=config.num_ctx,
            num_predict=config.num_predict,
        )

    return factory


def ollama_version(base_url: str, timeout: float = 10.0) -> str:
    """Server version string from ``/api/version``."""
    resp = httpx.get(f"{base_url}/api/version", timeout=timeout)
    resp.raise_for_status()
    return resp.json()["version"]


def model_digest(base_url: str, model: str, timeout: float = 10.0) -> str:
    """The model's sha256 digest from ``/api/tags`` (pins the exact weights)."""
    resp = httpx.get(f"{base_url}/api/tags", timeout=timeout)
    resp.raise_for_status()
    for entry in resp.json().get("models", []):
        if entry["name"] == model or entry["name"] == f"{model}:latest":
            return entry["digest"]
    raise LookupError(f"model {model!r} not found on {base_url}")


def model_show(base_url: str, model: str, timeout: float = 30.0) -> dict[str, Any]:
    """Modelfile parameters and details from ``/api/show`` (manifest record)."""
    resp = httpx.post(f"{base_url}/api/show", json={"model": model}, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()
    return {
        "parameters": body.get("parameters"),
        "details": body.get("details"),
        "capabilities": body.get("capabilities"),
    }
