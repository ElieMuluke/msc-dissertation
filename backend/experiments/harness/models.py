"""Ollama model factory and server introspection for the harness.

The factory closes over the arm's base URL and builds a fresh ``ChatOllama``
per run with that run's temperature and seed (from :class:`RunContext`).

Thinking is controlled by ``ExperimentConfig.think``, passed through as
langchain-ollama's ``reasoning``. That value reaches the wire unmodified:
``langchain_ollama/chat_models.py:804`` builds the request as
``"think": kwargs.pop("reasoning", self.reasoning)`` and the ollama client
serialises with ``model_dump(exclude_none=True)``
(``ollama/_client.py:402``, field ``ChatRequest.think`` at
``ollama/_types.py:403``). So ``False`` sends ``think: false``, ``True``
sends ``think: true``, and ``None`` omits the key entirely — the three
cases the harness relies on.

Under ``reasoning=True`` langchain-ollama also splits the response: the
server's ``message.thinking`` is stored in
``AIMessage.additional_kwargs["reasoning_content"]``
(``chat_models.py:1268`` sync / ``:1350`` async) and never concatenated
into ``content``, so
``AgentResult.output_text`` — and therefore extraction, the canonical
trajectory and every metric — sees the answer channel only. Reasoning is
fed back on later turns as the message's ``thinking`` field
(``chat_models.py:1080``), which is the deliberation the track is testing.

top_p / top_k / min_p are left at Ollama server defaults per the locked
design constants; they are recorded in the manifest, not set here.
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
            # Tri-state: False sends "think": false (thinking models);
            # True sends "think": true (thinking-on track); None omits the
            # parameter (models without a thinking mode — the ollama client
            # serializes with exclude_none). See the module docstring for
            # the langchain-ollama/ollama call sites this relies on.
            reasoning=config.think,
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
