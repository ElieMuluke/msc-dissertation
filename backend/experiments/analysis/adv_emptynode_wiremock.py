"""Adversarial empty-node probe 3: mocked-model wire test (ZERO LLM calls).

Exercises the REAL ``run_tool_loop`` / ``build_tool_loop_graph`` /
``MasAgent`` code paths with a scripted fake chat model to establish:

1. (C1) ``run_tool_loop`` overwrites ``output_text`` on every AIMessage, so a
   non-empty earlier assistant turn followed by an empty final turn returns
   "" — i.e. the harness CAN discard model-produced text. Proven live.
2. (C1) the cap-hit path: when the last permitted turn is a tool-call turn
   the loop ends returning THAT turn's text; any narration on earlier turns
   is discarded.
3. (C5, Fix A) "keep the last NON-empty assistant text" applied to the same
   final transcripts: what it recovers per mechanism class.
4. (C3) real ``MasAgent``: an empty data node produces no error; the
   reporting node receives a bare "DATA FINDINGS:" header with nothing under
   it and still emits a decision.
5. installed langchain-core ``AIMessage.text`` semantics (property vs
   method) — rules out a str()-artifact bug.

Run: cd backend && .venv/bin/python -m experiments.analysis.adv_emptynode_wiremock
"""

from __future__ import annotations

import asyncio

import langchain_core
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool

from app.agents.contract import RunContext
from app.agents.mas import MasAgent
from app.agents.single import build_tool_loop_graph, run_tool_loop


@tool
def check_sanctions_list(name: str) -> str:
    """Mock sanctions screen."""
    return f"{name}: not sanctioned"


class ScriptedModel:
    """Duck-typed chat model: returns scripted AIMessages in order.

    Only the surface ``run_tool_loop`` touches is implemented:
    ``bind_tools`` and ``ainvoke``. Records every prompt it receives.
    """

    def __init__(self, script: list[AIMessage]):
        self._script = list(script)
        self.received: list[list[BaseMessage]] = []

    def bind_tools(self, tools):  # noqa: ANN001
        return self

    async def ainvoke(self, messages):  # noqa: ANN001
        self.received.append(list(messages))
        if not self._script:
            raise AssertionError("script exhausted — loop ran longer than scripted")
        return self._script.pop(0)


def ai(text: str, calls: int = 0) -> AIMessage:
    tool_calls = [
        {"name": "check_sanctions_list", "args": {"name": f"E{i}"}, "id": f"c{i}"}
        for i in range(calls)
    ]
    return AIMessage(content=text, tool_calls=tool_calls)


def current_rule(final_messages: list[BaseMessage], seed_len: int) -> str:
    """Byte-for-byte the selection in run_tool_loop (last AIMessage wins)."""
    out = ""
    for m in final_messages[seed_len:]:
        if isinstance(m, AIMessage):
            t = getattr(m, "text", None)
            out = t if isinstance(t, str) else str(m.content)
    return out


def fix_a(final_messages: list[BaseMessage], seed_len: int) -> str:
    """Fix A: keep the last NON-empty assistant text."""
    out = ""
    for m in final_messages[seed_len:]:
        if isinstance(m, AIMessage):
            t = getattr(m, "text", None)
            t = t if isinstance(t, str) else str(m.content)
            if t.strip():
                out = t
    return out


async def loop_case(name: str, script: list[AIMessage], max_iterations: int) -> None:
    seed: list[BaseMessage] = [HumanMessage(content="case")]
    # (a) the real public entry point
    loop = await run_tool_loop(
        ScriptedModel(script), [check_sanctions_list], seed, max_iterations
    )
    # (b) same graph, raw transcript, both selection rules
    graph = build_tool_loop_graph(
        ScriptedModel(script), [check_sanctions_list], max_iterations
    )
    final = await graph.ainvoke(
        {"messages": list(seed), "iterations": 0},
        config={"recursion_limit": max(1, 2 * max_iterations + 4)},
    )
    cur = current_rule(final["messages"], len(seed))
    fa = fix_a(final["messages"], len(seed))
    assert cur == loop.output_text, "reimplementation drifted from run_tool_loop"
    print(f"[{name}]")
    print(f"   run_tool_loop.output_text = {loop.output_text!r}")
    print(f"   Fix A would return        = {fa!r}")


async def mas_case() -> None:
    """Real MasAgent, data node scripted to a single empty turn (qwen-style)."""
    scripts = {
        0: [ai("PLAN: screen everyone")],                       # orchestrator
        1: [ai("", calls=1), ai("")],                           # data: tool, then empty
        2: [ai("RISK: low, recommend dismiss")],                # policy_risk
        3: [ai("Report...\nFINAL DECISION: dismiss")],          # reporting
    }
    models = []

    calls = {"n": -1}

    def factory(context: RunContext):
        # MasAgent builds ONE llm for the whole pipeline; return a router that
        # serves each node's script in pipeline order (nodes run sequentially).
        class Router:
            def __init__(self):
                self.received: list[list[BaseMessage]] = []
                self._node_models = {k: ScriptedModel(v) for k, v in scripts.items()}
                self._served = 0

            def bind_tools(self, tools):  # noqa: ANN001
                return self

            async def ainvoke(self, messages):  # noqa: ANN001
                self.received.append(list(messages))
                # route by which node prompt is in the SystemMessage
                sys = messages[0].content
                if "Orchestrator" in sys:
                    m = self._node_models[0]
                elif "Policy & Risk Agent in" in sys:
                    m = self._node_models[2]
                elif "Data Agent in" in sys:
                    m = self._node_models[1]
                else:
                    m = self._node_models[3]
                return await m.ainvoke(messages)

        r = Router()
        models.append(r)
        return r

    from experiments.config import MAS_TOOL_PARTITION
    from experiments.mas.prompts import MAS_PROMPTS

    agent = MasAgent(
        model_factory=factory,
        tools=[check_sanctions_list],
        prompts=MAS_PROMPTS,
        tool_partition={
            "orchestrator": (),
            "data": ("check_sanctions_list",),
            "policy_risk": (),
            "reporting": (),
        },
        render_case=lambda c: "COMPLIANCE ALERT: T-1",
        max_iterations=8,
    )
    result = await agent.arun(
        {},
        RunContext(run_id="mock:T-1", case_id="T-1", seed=1, temperature=0.0),
    )
    print("[MAS wire test: empty data node]")
    print(f"   node_outputs['data']      = {result.node_outputs['data']!r}")
    print(f"   final output_text         = {result.output_text!r}")
    # what did the reporting node SEE?
    router = models[0]
    reporting_prompt = next(
        msgs for msgs in router.received if "Reporting" in msgs[0].content
    )
    user = reporting_prompt[1].content
    start = user.index("DATA FINDINGS:")
    end = user.index("POLICY & RISK ASSESSMENT:")
    print(f"   reporting node's DATA FINDINGS block = {user[start:end]!r}")
    print("   -> no exception, no error, decision extractable:",
          result.output_text.strip().endswith("FINAL DECISION: dismiss"))


async def main() -> None:
    print(f"langchain-core {langchain_core.__version__};"
          f" AIMessage.text is a "
          f"{'property' if isinstance(getattr(AIMessage, 'text', None), property) else type(getattr(AIMessage, 'text', None)).__name__}")
    probe = AIMessage(content="hello", tool_calls=[])
    t = getattr(probe, "text", None)
    print(f"AIMessage('hello').text -> {t!r} (isinstance str: {isinstance(t, str)})")

    await loop_case(
        "S1 prose turn, then EMPTY final answer turn (post-tools)",
        [ai("PARTIAL EVIDENCE: ABC Corp not sanctioned", calls=1), ai("")],
        max_iterations=8,
    )
    await loop_case(
        "S2 cap-hit: every permitted turn requests tools; narration on turns 1-2",
        [ai("Screening ABC Corp first...", calls=1),
         ai("Now the counterparty...", calls=1),
         ai("", calls=1)],
        max_iterations=3,
    )
    await loop_case(
        "S3 single EMPTY answer turn, no tools (qwen policy_risk mechanism)",
        [ai("")],
        max_iterations=8,
    )
    await loop_case(
        "S4 cap-hit with NO narration on any turn (pure tool-call turns)",
        [ai("", calls=1), ai("", calls=1), ai("", calls=1)],
        max_iterations=3,
    )
    await mas_case()


if __name__ == "__main__":
    asyncio.run(main())
