"""Production-side adapter over the shared agent modules (PRD-B §1/§3).

The experiment harness and the API import the *same* ``app.agents.single`` /
``app.agents.mas`` modules (contract: ``async arun(case, context) -> AgentResult``,
see ``contract.py`` — those three files belong to the experiment work stream). This
module is the production call site around them:

- :func:`build_production_agent` constructs the requested arm with the production
  prompts (:mod:`.production_prompts`), the injected production tool set and an Ollama
  model factory. Imports are lazy so the API boots even if an arm's dependencies are
  missing; calling then raises :class:`PipelineUnavailableError` → HTTP 503-style
  error frame.
- :func:`wrap_tools_with_trace` decorates the tool set so every call's *result* is
  captured for the audit report (the contract's ``ToolCallRecord`` keeps name+args
  only) and optionally reported live via a callback.
- :func:`parse_decision` applies the shared ``FINAL DECISION:`` output contract —
  per ``contract.py``, decision parsing is the caller's job.
- :func:`normalize_result` flattens everything into the shape report persistence needs.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from langchain_core.tools import StructuredTool

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps import lazy at runtime
    from app.agents.contract import Agent, AgentResult, RunContext

PIPELINES = ("single", "mas")

_DECISION_RE = re.compile(r"FINAL DECISION:\s*(escalate|dismiss|investigate)\b", re.IGNORECASE)

# search_aml_corpus hit headers, e.g. "[doc-3] (source=JMLSG Part I.pdf, page=112, score=0.81)"
_CITATION_RE = re.compile(r"\[([^\]]+)\]\s*\(source=([^,)]*), page=([^,)]*)")


class PipelineUnavailableError(RuntimeError):
    """Raised when the requested arm cannot be constructed (module/deps missing)."""


@dataclass(frozen=True)
class NormalizedResult:
    """Flat, persistence-ready view of one analysis outcome."""

    decision: str
    rationale: str
    tool_calls: list[dict] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    model: Optional[str] = None
    model_digest: Optional[str] = None
    raw_output: str = ""


def parse_decision(output_text: str) -> str:
    """Extract the ``FINAL DECISION: <...>`` verdict; ``malformed`` when absent.

    Same regex contract as the PRD-A harness (last match wins, so a quoted contract
    line earlier in the text does not shadow the real final line).
    """
    matches = _DECISION_RE.findall(output_text or "")
    return matches[-1].lower() if matches else "malformed"


def default_model_name() -> str:
    """Configured production model (env-overridable like the RAG settings)."""
    return os.getenv("ANALYSIS_MODEL", "qwen3.5:9b")


def analysis_base_url() -> str:
    """The analysis Ollama server URL. During the PRD-A sweep this MUST point at
    the dev server (``:11436``) — the two sweep servers (:11434/:11435) take
    runner traffic exclusively."""
    return os.getenv("ANALYSIS_OLLAMA_URL", "http://localhost:11434")


def build_model_factory() -> Callable[["RunContext"], Any]:
    """Ollama chat-model factory honouring the RunContext sampling parameters.

    Generation parameters are aligned with the experiment harness factory
    (``experiments/harness/models.py``) so production runs the same wire
    contract as the measured arms: thinking disabled (``reasoning=False`` →
    ``think: false`` on the wire — qwen3.5 thinks by default otherwise) and
    the same ``num_ctx``/``num_predict``. Temperature/seed stay per-request
    from the RunContext, which is the production-appropriate part.
    """
    from langchain_ollama import ChatOllama  # lazy: not needed when the agent is mocked

    base_url = analysis_base_url()
    model = default_model_name()

    def factory(context: "RunContext") -> Any:
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=context.temperature,
            seed=context.seed,
            reasoning=False,
            num_ctx=16384,
            num_predict=2048,
        )

    return factory


_DIGEST_CACHE: dict[tuple[str, str], str] = {}


def get_model_digest() -> Optional[str]:
    """sha256 digest of the analysis model, from the analysis Ollama server.

    Cached per process (a pinned tag's digest cannot change without a pull).
    Returns ``None`` when the server is unreachable or the model is absent —
    the report then prints ``digest n/a`` rather than failing the analysis.
    """
    import httpx  # lazy: keeps this module importable when mocked in tests

    key = (analysis_base_url(), default_model_name())
    if key in _DIGEST_CACHE:
        return _DIGEST_CACHE[key]
    base_url, model = key
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        resp.raise_for_status()
        for entry in resp.json().get("models", []):
            if entry.get("name") in (model, f"{model}:latest"):
                _DIGEST_CACHE[key] = entry["digest"]
                return entry["digest"]
    except Exception:
        return None
    return None


def wrap_tools_with_trace(
    tools: Sequence[StructuredTool],
    on_call: Optional[Callable[[dict], None]] = None,
) -> tuple[list[StructuredTool], list[dict]]:
    """Wrap ``tools`` so each invocation is recorded as ``{"name", "args", "result"}``.

    The shared contract's ``ToolCallRecord`` carries name+arguments only; the audit
    report needs results too (PRD-B §4), so the production side captures them at the
    tool boundary instead of changing the shared modules. ``on_call`` (if given) fires
    per call with ``{"tool": name}`` — the analysis route uses it for live SSE steps.
    Returns the wrapped tools and the (mutable, per-request) trace list they append to.
    """
    trace: list[dict] = []

    def wrap(tool: StructuredTool) -> StructuredTool:
        inner = tool.func

        def traced(__tool_name: str = tool.name, __inner: Callable = inner, **kwargs: Any) -> str:
            if on_call is not None:
                on_call({"tool": __tool_name})
            try:
                result = __inner(**kwargs)
            except Exception as exc:
                trace.append({"name": __tool_name, "args": kwargs, "result": f"error: {exc}"})
                raise
            trace.append({"name": __tool_name, "args": kwargs, "result": result})
            return result

        return StructuredTool.from_function(
            func=traced,
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
        )

    return [wrap(t) for t in tools], trace


def extract_citations(trace: Sequence[dict], limit: int = 10) -> list[str]:
    """Pull rulebook/corpus citations out of ``search_aml_corpus`` results in the trace."""
    citations: list[str] = []
    for call in trace:
        if call.get("name") != "search_aml_corpus":
            continue
        for hit_id, source, page in _CITATION_RE.findall(str(call.get("result", ""))):
            entry = f"{source.strip()}, page {page.strip()} [{hit_id}]"
            if entry not in citations:
                citations.append(entry)
    return citations[:limit]


def build_production_agent(
    pipeline: str,
    tools: Sequence[StructuredTool],
    rulebook: str,
    model_factory: Optional[Callable[["RunContext"], Any]] = None,
) -> "Agent":
    """Construct the requested arm with production prompts + tools (PRD-B §1).

    Lazy imports keep the API bootable while the shared modules (or their
    dependencies, e.g. langgraph) are in flux during the parallel build.
    """
    if pipeline not in PIPELINES:
        raise ValueError(f"pipeline must be one of {PIPELINES}, got {pipeline!r}")
    factory = model_factory or build_model_factory()

    from app.agents import production_prompts as prompts

    try:
        if pipeline == "single":
            from app.agents.single import SingleAgent

            return SingleAgent(
                model_factory=factory,
                tools=list(tools),
                system_prompt=prompts.single_system_prompt(rulebook),
                render_case=prompts.render_case,
            )
        from app.agents.mas import MasAgent

        return MasAgent(
            model_factory=factory,
            tools=list(tools),
            prompts=prompts.mas_prompts(rulebook),
            tool_partition=prompts.MAS_TOOL_PARTITION,
            render_case=prompts.render_case,
        )
    except ImportError as exc:
        raise PipelineUnavailableError(
            f"Agent modules for pipeline '{pipeline}' are not available: {exc}"
        ) from exc


def normalize_result(
    result: "AgentResult",
    trace: Optional[Sequence[dict]] = None,
    model: Optional[str] = None,
    model_digest: Optional[str] = None,
) -> NormalizedResult:
    """Flatten an ``AgentResult`` + captured tool trace for report persistence.

    Prefers the production-side ``trace`` (which has results) over the contract's
    name+args records; falls back to the latter so a report is still complete if a
    tool set was injected unwrapped.
    """
    output_text = result.output_text or ""
    if trace:
        tool_calls = list(trace)
    else:
        tool_calls = [
            {"name": record.name, "args": dict(record.arguments), "result": ""}
            for record in result.tool_calls
        ]
    return NormalizedResult(
        decision=parse_decision(output_text),
        rationale=output_text,
        tool_calls=tool_calls,
        citations=extract_citations(tool_calls),
        model=model,
        model_digest=model_digest,
        raw_output=output_text,
    )
