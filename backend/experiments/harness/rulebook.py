"""The shared rulebook — DFAH's shipped decision criteria, one copy for both arms.

Wording is drawn from dfah-bench's compliance-triage task definition
(``task.py`` docstring / ground-truth semantics) and its agentic benchmark
system prompt (``run_agentic_benchmark.py``). Both arms receive this exact
text (arm A inline in its single system prompt; arm B in the Policy & Risk
and Reporting role prompts), satisfying the "same rulebook in both" locked
constant. The production rulebook (PRD-B) is a different document and never
mixes with this one.
"""

RULEBOOK = """DECISION RULEBOOK (compliance alert triage)

You must triage each alert into exactly one of three decisions:

- escalate — forward to the compliance team. Choose when the alert matches
  known fraud or money-laundering patterns or shows high-risk indicators,
  e.g. a sanctions list hit, structuring just under a reporting threshold,
  incomplete KYC combined with a high-risk jurisdiction, or a high computed
  risk score.
- dismiss — close as a false positive. Choose when the evidence shows normal
  business activity, e.g. an established customer with complete KYC making
  payments consistent with their history, low amounts, low-risk
  jurisdictions, or minor isolated flags.
- investigate — request additional information before deciding. Choose when
  the available evidence is insufficient to either escalate or dismiss,
  e.g. unknown customer profile, ambiguous indicators, or conflicting
  evidence.

Evidence rules:
1. Use the available tools to gather evidence BEFORE deciding; do not decide
   from the alert text alone.
2. Ground the decision only in tool results and the alert fields; never
   invent sanctions hits, profiles, or precedents.
3. A confirmed sanctions hit on any party is grounds to escalate.
4. Weigh customer history: long, clean relationships with complete KYC
   support dismissal of routine-pattern alerts."""
