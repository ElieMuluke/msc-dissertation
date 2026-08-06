"""Shared agent contract: ``async arun(case, context) -> AgentResult``.

This is the single interface both the PRD-A experiment harness and the PRD-B
FastAPI routes program against, so the measured code path and the production
code path are demonstrably the same modules (one code path, two entry points).

The contract is deliberately stateless: a fresh :class:`RunContext` is built
per invocation and nothing is retained between calls. Session memory, if any,
lives strictly outside these modules (PRD-B §5).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolCallRecord:
    """One observed external tool invocation, in call order.

    The canonical trajectory compared across arms is the ordered list of
    ``name`` values only (PRD-A locked constant); arguments are retained for
    audit but never enter the cross-arm comparison.
    """

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    """Provider-neutral outcome of one agent episode.

    ``output_text`` is the final assistant text; decision parsing (the
    ``FINAL DECISION:`` contract) happens in the caller, not here, so the
    same modules serve tasks with different output contracts.
    """

    output_text: str
    tool_calls: tuple[ToolCallRecord, ...] = ()
    #: Number of LLM (assistant) messages generated during the episode.
    agent_messages: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    #: Free-form extras (e.g. per-node outputs for the MAS arm). Audit only.
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunContext:
    """Explicit per-run execution identity. No hidden globals.

    ``seed``/``temperature`` are consumed by the injected model factory;
    ``metadata`` carries harness- or API-specific values (never read by the
    agents themselves).
    """

    run_id: str
    case_id: str
    seed: int | None
    temperature: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    """One async method — no framework dependency leaks through the contract."""

    async def arun(self, case: Mapping[str, Any], context: RunContext) -> AgentResult:
        """Execute one fresh-context episode for ``case``."""
        ...
