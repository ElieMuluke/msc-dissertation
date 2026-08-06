"""DFAH mocked tools, wrapped as LangChain ``StructuredTool``s.

The implementations are DFAH's own (``econometrics/benchmarks/
compliance_triage/task.py`` in the dfah-bench source checkout), loaded via
``importlib`` so the benchmark code is used verbatim rather than re-typed.
A fresh :class:`ComplianceTriageTools` instance is built per run, so no tool
state (call logs) leaks between runs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from experiments.config import DFAH_REPO

_TASK_PY = DFAH_REPO / "econometrics/benchmarks/compliance_triage/task.py"
_MODULE_NAME = "dfah_compliance_triage_task"


def load_task_module(path: Path = _TASK_PY) -> ModuleType:
    """Import DFAH's compliance-triage task module from the source checkout."""
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load DFAH task module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


class _PrecedentArgs(BaseModel):
    query: str = Field(..., description="Search query for precedent cases")


class _ProfileArgs(BaseModel):
    customer_id: str = Field(..., description="Customer identifier")


class _SanctionsArgs(BaseModel):
    name: str = Field(..., description="Entity name to screen")


class _RiskArgs(BaseModel):
    factors: dict[str, Any] = Field(
        ...,
        description=(
            "Risk factors dictionary, e.g. {'amount': 47500, 'offshore': true, "
            "'new_counterparty': false, 'sanctions_hit': false}"
        ),
    )


def build_dfah_tools() -> list[StructuredTool]:
    """Build the four DFAH mocked tools over a fresh deterministic context.

    Tool names and behaviour come from DFAH's ``ComplianceTriageTools``;
    entities absent from the mock context get DFAH's deterministic defaults.
    """
    task = load_task_module()
    impl = task.ComplianceTriageTools(task.create_test_context())

    return [
        StructuredTool.from_function(
            func=lambda query, _impl=impl: str(_impl.search_precedents(query)),
            name="search_precedents",
            description="Search historical compliance cases for similar alerts.",
            args_schema=_PrecedentArgs,
        ),
        StructuredTool.from_function(
            func=lambda customer_id, _impl=impl: str(_impl.get_customer_profile(customer_id)),
            name="get_customer_profile",
            description="Retrieve customer risk profile and KYC status.",
            args_schema=_ProfileArgs,
        ),
        StructuredTool.from_function(
            func=lambda name, _impl=impl: str(_impl.check_sanctions_list(name)),
            name="check_sanctions_list",
            description="Screen an entity name against sanctions lists.",
            args_schema=_SanctionsArgs,
        ),
        StructuredTool.from_function(
            func=lambda factors, _impl=impl: str(_impl.calculate_risk_score(factors)),
            name="calculate_risk_score",
            description="Compute a transaction risk score from a factors dictionary.",
            args_schema=_RiskArgs,
        ),
    ]
