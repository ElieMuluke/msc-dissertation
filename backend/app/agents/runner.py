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
- :func:`needs_forced_final_answer` / :func:`force_final_answer` are the production
  hardening for runs that exhaust the tool loop mid-tool-call and return no final
  text: one additional tools-disabled model call ("provide your FINAL DECISION now"),
  recorded in the report trace as a distinct ``forced-final-answer round`` step. This
  lives here in the adapter — the shared ``single.py``/``mas.py`` modules are the
  pre-registered measured system and must not change.
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


#: Trace-step name for the forced-final-answer retry (distinct from real tool names,
#: so audit reports show the retry as its own step in the tool-call trace).
FORCED_FINAL_STEP = "forced-final-answer round"

# Per-tool-result cap when replaying the evidence trace into the forced final call —
# keeps the one-shot prompt comfortably inside the model's num_ctx.
_FORCED_FINAL_RESULT_MAX_CHARS = 1200


def needs_forced_final_answer(result: "AgentResult") -> bool:
    """True when the episode ended on a pending tool call with no parsable decision.

    The shared contract's :class:`AgentResult` does not expose the raw transcript, so
    the adapter infers "last message was a pending tool call" from its observable
    signature: under the shared tool loop, a run that hits the iteration cap while
    requesting another tool call returns that tool-call message's (empty) text as
    ``output_text``. A run whose final message is prose — even prose missing the
    FINAL DECISION line — is deliberately NOT retried here.
    """
    return (
        parse_decision(result.output_text) == "malformed"
        and bool(result.tool_calls)
        and not (result.output_text or "").strip()
    )


async def force_final_answer(
    result: "AgentResult",
    pipeline: str,
    rulebook: str,
    case: Any,
    context: "RunContext",
    trace: list[dict],
    model_factory: Optional[Callable[["RunContext"], Any]] = None,
) -> "AgentResult":
    """One additional tools-disabled model call to obtain the missing final answer.

    Production-only hardening (PRD-B adapter layer): replays the case and the
    already-gathered evidence (the production tool trace, results truncated) to a
    fresh model with NO tools bound, instructing it to produce the rationale and
    ``FINAL DECISION`` line now. The retry is appended to ``trace`` as a distinct
    ``forced-final-answer round`` step so the audit report shows exactly what
    happened. Returns a copy of ``result`` carrying the retry's text; on model
    failure the original result is returned unchanged (decision stays ``malformed``
    rather than the whole analysis failing).
    """
    from dataclasses import replace

    from langchain_core.messages import HumanMessage, SystemMessage

    from app.agents import production_prompts as prompts

    factory = model_factory or build_model_factory()
    if pipeline == "mas":
        system_prompt = prompts.mas_prompts(rulebook)["reporting"]
    else:
        system_prompt = prompts.single_system_prompt(rulebook)

    evidence_lines = []
    for call in trace:
        text = str(call.get("result", ""))
        if len(text) > _FORCED_FINAL_RESULT_MAX_CHARS:
            text = text[: _FORCED_FINAL_RESULT_MAX_CHARS - 1] + "…"
        evidence_lines.append(f"- {call.get('name')}({call.get('args')}) -> {text}")
    evidence = "\n".join(evidence_lines) or "(no tool results were captured)"

    user_prompt = (
        f"{prompts.render_case(case)}\n\n"
        "Your investigation budget is exhausted; the tools are no longer available. "
        "Evidence already gathered (tool calls and results, in order):\n"
        f"{evidence}\n\n"
        "Provide your final rationale and FINAL DECISION line now."
    )
    try:
        llm = factory(context)  # tools deliberately NOT bound: this call cannot recurse
        response = await llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        text = getattr(response, "text", None)
        output_text = text if isinstance(text, str) else str(response.content)
    except Exception as exc:  # noqa: BLE001 - the retry must never sink the analysis
        trace.append(
            {"name": FORCED_FINAL_STEP, "args": {"pipeline": pipeline}, "result": f"error: {exc}"}
        )
        return result
    trace.append({"name": FORCED_FINAL_STEP, "args": {"pipeline": pipeline}, "result": output_text})
    return replace(result, output_text=output_text, agent_messages=result.agent_messages + 1)


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
