"""Arm A — monolithic single agent (one system prompt, all tools) on LangGraph.

Ported 2026-08-06 from a hand-rolled LangChain loop to a LangGraph graph so
BOTH arms run on the same runtime (removes a framework confound between the
experiment arms). The graph is the idiomatic ReAct shape — an ``agent`` node
and a ``tools`` node joined by conditional edges::

    START -> agent --(tool calls?)--> tools --(iterations left?)--> agent
                  \\--(no tool calls)--> END        \\--(cap hit)--> END

``langgraph.prebuilt.create_react_agent`` was deliberately NOT used: it has
no graceful max-iterations semantics (its ``recursion_limit`` raises
``GraphRecursionError`` instead of returning the last assistant text), and
our unknown-tool / tool-error message formats and requested-call recording
must stay byte-compatible with the pre-registered behaviour.

Loop semantics (identical to the pre-port loop):

- at most ``max_iterations`` model calls; tool calls requested by the final
  permitted model call are still executed, then the loop ends returning that
  call's text;
- every *requested* tool call is recorded in order, including calls to
  unknown tool names, which receive ``error: unknown tool '<name>'`` results;
- tool exceptions become ``error: <exc>`` results — data, not crashes.

Everything is injected (model factory, tools, prompt, case renderer — see
``app/agents/tools.py`` for the pattern); a fresh graph is compiled per loop
invocation, so no state can survive across runs. The same module is imported
by the PRD-A harness (DFAH mocked tools) and the PRD-B API (production tools).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from app.agents.contract import AgentResult, RunContext, ToolCallRecord

#: Builds a fresh chat model for one run (temperature/seed come from context).
ModelFactory = Callable[[RunContext], BaseChatModel]
#: Renders a case mapping into the user prompt.
CaseRenderer = Callable[[Mapping[str, Any]], str]


@dataclass
class ToolLoopResult:
    """Outcome of one tool-calling loop (also used by the MAS arm's nodes)."""

    output_text: str
    tool_calls: list[ToolCallRecord]
    #: Number of LLM (assistant) messages generated — one per ``agent`` node
    #: invocation; identical to the pre-port count of model calls.
    agent_messages: int
    prompt_tokens: int
    completion_tokens: int


def _extend(left: list[Any], right: list[Any]) -> list[Any]:
    return left + right


class ToolLoopState(TypedDict):
    """State of the ReAct loop: transcript plus model-call count."""

    messages: Annotated[list[BaseMessage], _extend]
    iterations: int


def build_tool_loop_graph(
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    max_iterations: int,
):
    """Compile the agent-node + tool-node ReAct graph for one loop invocation."""
    tool_map = {t.name: t for t in tools}
    bound = llm.bind_tools(list(tools)) if tools else llm

    async def agent(state: ToolLoopState) -> dict[str, Any]:
        ai = await bound.ainvoke(state["messages"])
        return {"messages": [ai], "iterations": state["iterations"] + 1}

    async def run_tools(state: ToolLoopState) -> dict[str, Any]:
        ai = state["messages"][-1]
        results: list[BaseMessage] = []
        for call in ai.tool_calls:
            name = call["name"]
            args = call.get("args") or {}
            tool = tool_map.get(name)
            if tool is None:
                content = f"error: unknown tool '{name}'"
            else:
                try:
                    content = str(await tool.ainvoke(args))
                except Exception as exc:  # tool errors are data, not crashes
                    content = f"error: {exc}"
            results.append(
                ToolMessage(content=content, tool_call_id=call.get("id") or name)
            )
        return {"messages": results}

    def after_agent(state: ToolLoopState) -> str:
        return "tools" if state["messages"][-1].tool_calls else END

    def after_tools(state: ToolLoopState) -> str:
        return "agent" if state["iterations"] < max_iterations else END

    graph = StateGraph(ToolLoopState)
    graph.add_node("agent", agent)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", after_agent, {"tools": "tools", END: END})
    graph.add_conditional_edges("tools", after_tools, {"agent": "agent", END: END})
    return graph.compile()


def _usage(message: AIMessage) -> tuple[int, int]:
    meta = message.usage_metadata or {}
    return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))


async def run_tool_loop(
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    messages: list[BaseMessage],
    max_iterations: int,
) -> ToolLoopResult:
    """Run one ReAct loop on a freshly compiled graph and account for it.

    Shared by arm A directly and by every arm-B node, so both arms execute
    the identical LangGraph runtime path. ``messages`` seeds the transcript
    and is not mutated.
    """
    graph = build_tool_loop_graph(llm, tools, max_iterations)
    seed_len = len(messages)
    final: ToolLoopState = await graph.ainvoke(
        {"messages": list(messages), "iterations": 0},
        # max(1, …): langgraph requires a positive recursion limit; guards the
        # (unreachable at the locked max_iterations=8) max_iterations < 1 edge.
        config={"recursion_limit": max(1, 2 * max_iterations + 4)},
    )
    records: list[ToolCallRecord] = []
    prompt_tokens = completion_tokens = agent_messages = 0
    output_text = ""
    for message in final["messages"][seed_len:]:
        if not isinstance(message, AIMessage):
            continue
        agent_messages += 1
        in_tok, out_tok = _usage(message)
        prompt_tokens += in_tok
        completion_tokens += out_tok
        text = getattr(message, "text", None)
        output_text = text if isinstance(text, str) else str(message.content)
        for call in message.tool_calls:
            records.append(
                ToolCallRecord(name=call["name"], arguments=call.get("args") or {})
            )
    return ToolLoopResult(
        output_text=output_text,
        tool_calls=records,
        agent_messages=agent_messages,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


class SingleAgent:
    """Monolithic agent: one system prompt (rulebook inline), all tools."""

    def __init__(
        self,
        model_factory: ModelFactory,
        tools: Sequence[BaseTool],
        system_prompt: str,
        render_case: CaseRenderer,
        max_iterations: int = 8,
    ) -> None:
        self._model_factory = model_factory
        self._tools = list(tools)
        self._system_prompt = system_prompt
        self._render_case = render_case
        self._max_iterations = max_iterations

    async def arun(self, case: Mapping[str, Any], context: RunContext) -> AgentResult:
        """Execute one fresh-context episode (fresh model + graph per call)."""
        llm = self._model_factory(context)
        messages: list[BaseMessage] = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=self._render_case(case)),
        ]
        loop = await run_tool_loop(llm, self._tools, messages, self._max_iterations)
        return AgentResult(
            output_text=loop.output_text,
            tool_calls=tuple(loop.tool_calls),
            agent_messages=loop.agent_messages,
            prompt_tokens=loop.prompt_tokens,
            completion_tokens=loop.completion_tokens,
        )
