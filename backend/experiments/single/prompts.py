"""Arm A system prompt: one compliance analyst, rulebook inline, all tools.

``SYSTEM_PROMPT`` is the pre-registered v2 prompt and MUST NOT change —
sealed manifests embed it verbatim. The budget-sensitivity track (v2b,
"@b32" registry keys) selects ``SYSTEM_PROMPT_B32`` instead, which differs
by exactly one added sentence disclosing the agent's LLM-turn budget.
"""

from experiments.config import SINGLE_ITERATION_BUDGET
from experiments.harness.rulebook import RULEBOOK

#: The pre-registered output contract shared by both arms.
OUTPUT_CONTRACT = (
    "Your reply MUST end with exactly one final line of the form:\n"
    "FINAL DECISION: <escalate|dismiss|investigate>\n"
    "with nothing after it."
)

SYSTEM_PROMPT = f"""You are a compliance analyst triaging transaction alerts.

{RULEBOOK}

Work method: gather evidence with the available tools (sanctions screening,
customer profile, precedent search, risk scoring), then reason briefly from
that evidence to a single decision.

{OUTPUT_CONTRACT}"""

#: Budget-disclosure sentence (v2b track), verbatim in the pre-registration.
BUDGET_SENTENCE_SINGLE = (
    f"You have a budget of at most {SINGLE_ITERATION_BUDGET} tool-use steps; "
    "plan your investigation so the most decisive checks come first, and stop "
    "to state your final decision before the budget runs out."
)

#: v2b variant: the pre-registered prompt plus EXACTLY the one budget
#: sentence (inserted before the output contract). Built from SYSTEM_PROMPT
#: so any drift in the base prompt is structurally impossible.
SYSTEM_PROMPT_B32 = SYSTEM_PROMPT.replace(
    OUTPUT_CONTRACT, f"{BUDGET_SENTENCE_SINGLE}\n\n{OUTPUT_CONTRACT}"
)
