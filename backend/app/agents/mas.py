"""Arm B — LangGraph 4-agent pipeline.

Topology (PRD-A locked constant)::

    Orchestrator-Planner -> Data Agent -> Policy & Risk Agent -> Reporting Agent

Every node uses the same injected model factory (same model, same sampling
parameters as arm A). The overall tool set equals arm A's; tools are
partitioned across nodes by role via an injected mapping. The Reporting
Agent emits the final output (in the experiment: the ``FINAL DECISION:``
line — mandated by its injected prompt, not by this module).

The graph is rebuilt per run from a fresh model instance so no state can
survive across runs (PRD-A statefulness constant).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from app.agents.contract import AgentResult, RunContext, ToolCallRecord
from app.agents.single import CaseRenderer, ModelFactory, run_tool_loop

#: Node names, in pipeline order.
NODES = ("orchestrator", "data", "policy_risk", "reporting")


def _extend(left: list[Any], right: list[Any]) -> list[Any]:
    return left + right


def _add(left: int, right: int) -> int:
    return left + right


class MasState(TypedDict):
    """Pipeline state: per-stage outputs plus accumulated accounting."""

    case_text: str
    plan: str
    data_findings: str
    risk_assessment: str
    report: str
    tool_calls: Annotated[list[ToolCallRecord], _extend]
    agent_messages: Annotated[int, _add]
    prompt_tokens: Annotated[int, _add]
    completion_tokens: Annotated[int, _add]


class MasAgent:
    """Sequential 4-agent pipeline behind the shared ``arun`` contract.

    ``prompts`` maps each node name in :data:`NODES` to its system prompt.
    ``tool_partition`` maps node names to the tool names that node may call;
    nodes absent from the mapping (or mapped to an empty tuple) call no tools.
    """

    def __init__(
        self,
        model_factory: ModelFactory,
        tools: Sequence[BaseTool],
        prompts: Mapping[str, str],
        tool_partition: Mapping[str, Sequence[str]],
        render_case: CaseRenderer,
        max_iterations: int = 8,
    ) -> None:
        missing = [n for n in NODES if n not in prompts]
        if missing:
            raise ValueError(f"missing MAS prompts for nodes: {missing}")
        unknown = set(tool_partition) - set(NODES)
        if unknown:
            raise ValueError(f"tool_partition names unknown nodes: {sorted(unknown)}")
        self._model_factory = model_factory
        self._tools = list(tools)
        self._prompts = dict(prompts)
        self._partition = {n: tuple(tool_partition.get(n, ())) for n in NODES}
        self._render_case = render_case
        self._max_iterations = max_iterations

    def _node_tools(self, node: str) -> list[BaseTool]:
        allowed = self._partition[node]
        return [t for t in self._tools if t.name in allowed]

    @staticmethod
    def _node_input(node: str, state: MasState) -> str:
        """Compose each node's user message from the case and upstream outputs."""
        parts = [state["case_text"]]
        if node != "orchestrator":
            parts.append(f"INVESTIGATION PLAN:\n{state['plan']}")
        if node in ("policy_risk", "reporting"):
            parts.append(f"DATA FINDINGS:\n{state['data_findings']}")
        if node == "reporting":
            parts.append(f"POLICY & RISK ASSESSMENT:\n{state['risk_assessment']}")
        return "\n\n".join(parts)

    def _make_node(self, node: str, llm: Any, output_key: str):
        tools = self._node_tools(node)

        async def _run(state: MasState) -> dict[str, Any]:
            messages: list[BaseMessage] = [
                SystemMessage(content=self._prompts[node]),
                HumanMessage(content=self._node_input(node, state)),
            ]
            loop = await run_tool_loop(llm, tools, messages, self._max_iterations)
            return {
                output_key: loop.output_text,
                "tool_calls": loop.tool_calls,
                "agent_messages": loop.agent_messages,
                "prompt_tokens": loop.prompt_tokens,
                "completion_tokens": loop.completion_tokens,
            }

        return _run

    async def arun(self, case: Mapping[str, Any], context: RunContext) -> AgentResult:
        """Execute the pipeline once, fresh graph and model per call."""
        llm = self._model_factory(context)
        outputs = {
            "orchestrator": "plan",
            "data": "data_findings",
            "policy_risk": "risk_assessment",
            "reporting": "report",
        }
        graph = StateGraph(MasState)
        for node in NODES:
            graph.add_node(node, self._make_node(node, llm, outputs[node]))
        graph.add_edge(START, NODES[0])
        for a, b in zip(NODES, NODES[1:]):
            graph.add_edge(a, b)
        graph.add_edge(NODES[-1], END)
        compiled = graph.compile()

        final: MasState = await compiled.ainvoke(
            {
                "case_text": self._render_case(case),
                "plan": "",
                "data_findings": "",
                "risk_assessment": "",
                "report": "",
                "tool_calls": [],
                "agent_messages": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }
        )
        return AgentResult(
            output_text=final["report"],
            tool_calls=tuple(final["tool_calls"]),
            agent_messages=final["agent_messages"],
            prompt_tokens=final["prompt_tokens"],
            completion_tokens=final["completion_tokens"],
            extras={
                "plan": final["plan"],
                "data_findings": final["data_findings"],
                "risk_assessment": final["risk_assessment"],
            },
        )
