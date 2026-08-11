"""One adapter class for both arms behind ``async arun(case, context)``.

The arm is a constructor argument (PRD-A component 4). Per call it builds a
fresh tool set (fresh mock context, no call-log leakage) and a fresh agent,
so every run has a fresh context (statefulness locked constant). The agents
themselves are the shared ``app.agents`` modules — the same code path PRD-B
deploys behind FastAPI.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from langchain_core.tools import BaseTool

from app.agents.contract import AgentResult, RunContext
from app.agents.mas import MasAgent
from app.agents.single import SingleAgent
from experiments.config import DEFAULT_CONFIG, MAS_TOOL_PARTITION, ExperimentConfig
from experiments.harness.dfah_data import render_case
from experiments.harness.dfah_tools import build_dfah_tools
from experiments.harness.models import make_model_factory
from experiments.mas.prompts import MAS_PROMPTS
from experiments.single.prompts import SYSTEM_PROMPT as SINGLE_PROMPT

ToolBuilder = Callable[[], Sequence[BaseTool]]


class ArmAdapter:
    """Builds and runs one arm's agent; same class for both arms."""

    def __init__(
        self,
        arm: str,
        config: ExperimentConfig = DEFAULT_CONFIG,
        tool_builder: ToolBuilder = build_dfah_tools,
    ) -> None:
        if arm not in ("single", "mas"):
            raise ValueError(f"unknown arm {arm!r}")
        self.arm = arm
        self._config = config
        self._tool_builder = tool_builder
        self._model_factory = make_model_factory(config, arm)

    def _build_agent(self) -> SingleAgent | MasAgent:
        tools = list(self._tool_builder())
        if self.arm == "single":
            return SingleAgent(
                model_factory=self._model_factory,
                tools=tools,
                system_prompt=SINGLE_PROMPT,
                render_case=render_case,
                max_iterations=self._config.max_iterations,
            )
        return MasAgent(
            model_factory=self._model_factory,
            tools=tools,
            prompts=MAS_PROMPTS,
            tool_partition=MAS_TOOL_PARTITION,
            render_case=render_case,
            max_iterations=self._config.max_iterations,
        )

    async def arun(self, case: Mapping[str, Any], context: RunContext) -> AgentResult:
        """Run one fresh-context episode of this arm on ``case``."""
        return await self._build_agent().arun(case, context)

    async def aprewarm(self, case: Mapping[str, Any], context: RunContext) -> None:
        """Send this arm's exact opening prompt once and discard the reply.

        Harness v2 ``cache_policy="prewarm"`` support: reproduces the FIRST
        model call of a run byte-for-byte (same system prompt, same rendered
        case, same tool binding as the arm's opening call — full tool set
        for arm A, the orchestrator's partition for arm B) so the measured
        run that follows executes against a warm server/KV state. The reply
        is discarded and nothing is journalled here.
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = self._model_factory(context)
        tools = list(self._tool_builder())
        if self.arm == "single":
            system_prompt = SINGLE_PROMPT
        else:
            system_prompt = MAS_PROMPTS["orchestrator"]
            allowed = tuple(MAS_TOOL_PARTITION.get("orchestrator", ()))
            tools = [t for t in tools if t.name in allowed]
        bound = llm.bind_tools(tools) if tools else llm
        await bound.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=render_case(case)),
            ]
        )
