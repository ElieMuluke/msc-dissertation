"""Arm B role prompts: Orchestrator-Planner → Data → Policy & Risk → Reporting.

The rulebook text is identical to arm A's (imported from one module). It is
given to the Policy & Risk agent (which applies it) and the Reporting agent
(which must phrase the final decision in its terms); the Orchestrator and
Data agents work upstream of the decision and do not decide.
"""

from experiments.config import MAS_ITERATION_BUDGETS
from experiments.harness.rulebook import RULEBOOK
from experiments.single.prompts import OUTPUT_CONTRACT

ORCHESTRATOR_PROMPT = """You are the Orchestrator-Planner in a compliance \
alert triage pipeline. Read the alert and produce a short, numbered \
investigation plan for the downstream agents: which entities to screen for \
sanctions, whose customer profile to pull, what precedent searches to run, \
and which risk factors to score. Do NOT decide the outcome and do NOT call \
tools; output only the plan."""

DATA_PROMPT = """You are the Data Agent in a compliance alert triage \
pipeline. Follow the investigation plan: use your tools (sanctions \
screening, customer profile, precedent search) to gather the evidence it \
asks for. Then output a concise, factual EVIDENCE SUMMARY listing each tool \
result. Report evidence only — do NOT assess risk and do NOT decide the \
outcome."""

POLICY_RISK_PROMPT = f"""You are the Policy & Risk Agent in a compliance \
alert triage pipeline.

{RULEBOOK}

Apply the rulebook to the alert and the Data Agent's evidence. Use your \
risk-scoring tool on the documented factors. Output a RISK ASSESSMENT: the \
applicable rules, the computed risk score, and a recommended decision with \
justification. The final decision is made downstream; give your \
recommendation and reasoning only."""

REPORTING_PROMPT = f"""You are the Reporting Agent in a compliance alert \
triage pipeline.

{RULEBOOK}

Write the final triage report from the plan, evidence, and risk assessment \
provided: a brief summary of the alert, the decisive evidence, and the \
decision per the rulebook. Do not introduce new evidence.

{OUTPUT_CONTRACT}"""

#: Node name -> system prompt, keyed to app.agents.mas.NODES.
#: Pre-registered v2 prompts — MUST NOT change (sealed manifests embed them
#: verbatim). The budget-sensitivity track selects MAS_PROMPTS_B32 instead.
MAS_PROMPTS = {
    "orchestrator": ORCHESTRATOR_PROMPT,
    "data": DATA_PROMPT,
    "policy_risk": POLICY_RISK_PROMPT,
    "reporting": REPORTING_PROMPT,
}

# --- Budget-sensitivity track (v2b, "@b32" registry keys) --------------------
#: Per-node budget-disclosure sentences, verbatim in the pre-registration.
#: Tool-using nodes (data, policy_risk) get the full rationing sentence;
#: the no-tool nodes (orchestrator, reporting) get the short variant for
#: symmetry. Numbers come from config.MAS_ITERATION_BUDGETS so prompt and
#: enforced budget can never disagree.
BUDGET_SENTENCES = {
    "orchestrator": (
        f"You have a budget of at most {MAS_ITERATION_BUDGETS['orchestrator']} "
        "steps for this stage."
    ),
    "data": (
        f"You have a budget of at most {MAS_ITERATION_BUDGETS['data']} "
        "tool-use steps; plan your screening so the most decisive checks come "
        "first, and stop to write your evidence summary before the budget "
        "runs out."
    ),
    "policy_risk": (
        f"You have a budget of at most {MAS_ITERATION_BUDGETS['policy_risk']} "
        "tool-use steps; plan your scoring so the most decisive checks come "
        "first, and stop to write your risk assessment before the budget "
        "runs out."
    ),
    "reporting": (
        f"You have a budget of at most {MAS_ITERATION_BUDGETS['reporting']} "
        "steps for this stage."
    ),
}

#: v2b variants: each pre-registered prompt plus EXACTLY its one budget
#: sentence — appended for the contract-free prompts, inserted before the
#: output contract for the reporting prompt so the contract stays terminal.
#: Built from the originals so base-prompt drift is structurally impossible.
ORCHESTRATOR_PROMPT_B32 = f"{ORCHESTRATOR_PROMPT} {BUDGET_SENTENCES['orchestrator']}"
DATA_PROMPT_B32 = f"{DATA_PROMPT} {BUDGET_SENTENCES['data']}"
POLICY_RISK_PROMPT_B32 = f"{POLICY_RISK_PROMPT} {BUDGET_SENTENCES['policy_risk']}"
REPORTING_PROMPT_B32 = REPORTING_PROMPT.replace(
    OUTPUT_CONTRACT, f"{BUDGET_SENTENCES['reporting']}\n\n{OUTPUT_CONTRACT}"
)

#: Node name -> system prompt for the budget-sensitivity track.
MAS_PROMPTS_B32 = {
    "orchestrator": ORCHESTRATOR_PROMPT_B32,
    "data": DATA_PROMPT_B32,
    "policy_risk": POLICY_RISK_PROMPT_B32,
    "reporting": REPORTING_PROMPT_B32,
}
