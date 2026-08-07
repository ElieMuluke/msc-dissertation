"""Production prompts + case rendering for the shared agent modules (PRD-B §1).

The shared ``SingleAgent``/``MasAgent`` classes (``single.py``/``mas.py``, experiment
work stream) take their system prompts, tool set and case renderer by injection. This
module holds the *production* set: rulebook-grounded AML investigation prompts over the
production tools (``production_tools.py``). The experiment harness injects its own
DFAH-derived prompts and mocked tools into the same classes — the two never mix.

The output contract matches PRD-A's decision extraction: the final line must be
``FINAL DECISION: <escalate|dismiss|investigate>`` so one parser serves both entry
points.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_DECISION_CONTRACT = (
    "When your investigation is complete, give a concise, audit-ready rationale that "
    "cites the rulebook rules (by rule id, e.g. MON-2) and regulatory sources (JMLSG/FATF "
    "sections) you relied on, then end your answer with exactly one final line:\n"
    "FINAL DECISION: <escalate|dismiss|investigate>\n"
    "If the data needed to decide is missing, empty or ambiguous (e.g. no transaction "
    "history where activity was expected, or an unresolved data gap), do NOT treat the "
    "absence of evidence as evidence of low risk: decide investigate and cite the data "
    "gap in your rationale."
)

#: Tool-use budget guidance shared by the tool-calling prompts (single arm + MAS data
#: node): bound the investigation and keep the last step for prose, so runs stop
#: exhausting the iteration cap mid-tool-call and returning no final text.
_BUDGET_GUIDANCE = (
    "Work within a strict budget: you have a limited number of tool-use steps. Do not "
    "try to screen every counterparty — screen at most the 2-3 largest counterparties "
    "by transaction value. Always reserve your final step for writing your answer "
    "instead of calling another tool."
)


def single_system_prompt(rulebook: str) -> str:
    """System prompt for the monolithic arm (rulebook inline, all tools)."""
    return (
        "You are an AML compliance analyst investigating a bank account. Use the "
        "available tools to gather evidence before deciding: look the account up "
        "(query_accounts), inspect its transactions (query_transactions), screen the "
        "account holder and significant counterparties against the sanctions lists "
        "(sanctions_check), check jurisdictions against the FATF lists (country_risk), "
        "and retrieve regulatory grounding where needed (search_aml_corpus). Never rely "
        "on memory for specific rules or thresholds.\n\n"
        f"{_BUDGET_GUIDANCE} That final step must be your rationale ending with the "
        "FINAL DECISION line.\n\n"
        "Apply the following decision rulebook:\n\n"
        f"{rulebook}\n\n"
        f"{_DECISION_CONTRACT}"
    )


def mas_prompts(rulebook: str) -> dict[str, str]:
    """Per-node system prompts for the 4-agent pipeline (rulebook in Policy & Risk)."""
    return {
        "orchestrator": (
            "You are the Orchestrator-Planner of an AML investigation pipeline. Produce a "
            "short, numbered investigation plan for the case: which data to pull, which "
            "names to screen, which jurisdictions to check, and which rulebook areas look "
            "relevant. Do not decide the outcome. Output only the plan."
        ),
        "data": (
            "You are the Data Agent of an AML investigation pipeline. Execute the "
            "investigation plan's data steps using your tools: query_accounts, "
            "query_transactions, sanctions_check and country_risk. Report the factual "
            "findings (accounts, transaction patterns, screening results, jurisdiction "
            "statuses) with row ids where available. Report facts only — no risk "
            f"conclusions.\n\n{_BUDGET_GUIDANCE} That final step must be your written "
            "findings. If a data step returns nothing or the data is ambiguous, state "
            "the gap explicitly in your findings (e.g. 'no transactions returned for "
            "this filter') rather than silently omitting it."
        ),
        "policy_risk": (
            "You are the Policy & Risk Agent of an AML investigation pipeline. Assess the "
            "data findings against the decision rulebook below, using search_aml_corpus "
            "to verify regulatory grounding where needed. State which rules fire (by rule "
            "id), the resulting risk band, and your recommended decision with rationale.\n\n"
            f"Decision rulebook:\n\n{rulebook}"
        ),
        "reporting": (
            "You are the Reporting Agent of an AML investigation pipeline. Write the "
            "final, audit-ready case summary from the plan, data findings and risk "
            "assessment: key facts, rules applied (with rule ids and JMLSG/FATF "
            f"citations), and the decision rationale. {_DECISION_CONTRACT}"
        ),
    }


#: Which production tools each MAS node may call (nodes absent call none).
MAS_TOOL_PARTITION: dict[str, tuple[str, ...]] = {
    "data": ("query_accounts", "query_transactions", "sanctions_check", "country_risk"),
    "policy_risk": ("search_aml_corpus", "country_risk"),
}


def render_case(case: Mapping[str, Any]) -> str:
    """Render the production case mapping into the user prompt.

    ``session_notes`` (prior-analysis summaries, if any) are injected here by the API
    layer as plain case data — the agents themselves stay stateless (PRD-B §5).
    """
    lines = [f"Investigate account {case.get('account_id', '?')} for money-laundering risk."]
    if case.get("bank"):
        lines.append(f"Bank: {case['bank']}.")
    notes = case.get("session_notes") or []
    if notes:
        lines.append("Prior analyses in this session:")
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)
