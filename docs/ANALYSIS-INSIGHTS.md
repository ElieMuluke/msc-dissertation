# Analysis insights annex — drill-down session 2026-08-10

Owner-driven analysis of the four sealed context-1/2 sweeps (qwen3.5:9b, qwen2.5:7b,
qwen2.5:14b @ Ollama 0.31.1; gemma4 @ 0.32.6). All numbers recomputed read-only from
journals; harness attribution independently verified (see verdicts below).

## Cross-model insights (t07-varied unless noted)

1. **DAR without alpha is misleading — high repeatability can be mode collapse.**
   qwen2.5:14b (DAR ~0.9) answers `investigate` on ~95% of runs in both arms and
   dismissed 1–2 of 780 dismiss-labelled runs. qwen3.5-MAS milder form (86%
   investigate). Krippendorff's alpha exposes it; regulators should require
   chance-corrected agreement.
2. **Decomposition redistributes the decision spectrum; which category survives is
   model-specific.** Dismiss discrimination collapses under MAS in 3/4 models
   (q3.5 .20→.05, 14b .04→.01, gemma4 .46→.003/390-run≈1 run) with qwen2.5:7b the
   exception (.19→.52). Escalation: suppressed under MAS in all qwens
   (.44→.24, .13→.10, .20→.16) but amplified on gemma4 (.72→.78).
3. **Escalation competence is model-property, not LLM-universal.** gemma4 per-label
   escalate .72/.78 vs ≤.44 for all qwens; it escalates the sanctions-adjacent,
   weapons, and mixer cases the qwens systematically miss (e.g. TXN-015: gemma4 15/15
   vs qwens 0–5/15).
4. **Tool diligence anti-correlates with escalation** (all models): sanctions
   calls/run vs escalate-rate on escalate-labelled cases —
   q3.5-single 1.02→.44 best; q7b-mas 4.22→.10 worst; gemma4-single fewest tools
   (2.0/run) and best escalation. Cause: benchmark instrument property (below).
5. **Majority-vote rescues accuracy from instability**: 7b-MAS 27/50 and
   gemma4-single 30/50 majority-agreement lead all configs; self-consistency voting
   (Wang et al.) converts run variance into accuracy at k× cost. Report tokens per
   voted decision.
6. **Best-analyst config = gemma4-single** (balanced 244/312/184 decision mix,
   30/50 majority, cheapest tool usage) — and the worst T=0 cache-stability in the
   experiment (35 flipping groups). The repeatability–discrimination–cost triangle
   in one model.

## Benchmark-validity finding (quantified)

Only **1 of 15** escalate-labelled cases (TXN-2025-002, "Shadow Corp") has
tool-confirmable evidence in DFAH's mocks; for the other 14 the mocked tools return
clean/uninformative results against suspicious case text (sanctions clean, default
profiles, empty precedents, and `calculate_risk_score` structurally cannot represent
structuring — probed live: `{amount:9999, structuring:true}` → score 0.0 "low" while
echoing structuring in factors_considered). Models are asked to escalate against
their own due diligence. Dismiss side: mock risk scorer adds +0.3 for amount>50k but
cannot see "documented relationship" — dismiss-labelled cases >50k get dismissed at
0.03 pooled vs 0.18 for ≤50k. Supports (a) the pre-registered "agreement ≠
correctness" framing, (b) the planned JMLSG re-adjudication, (c) a benchmark-critique
subsection.

## Harness-vs-LLM attribution (independent agent, evidence in report)

- Case rendering, tool wrapping, extraction verified **symmetric across arms**
  (identical renderer object; DFAH mocks loaded verbatim for both; one extraction
  function, 0 mismatches re-parsing 1,500 runs). Between-arm differences =
  decomposition treatment, not harness bugs.
- **Escalation suppression mechanism** (qwen family): NOT information loss — raw case
  reaches every node incl. Reporting (mas.py `_node_input`), structuring signal
  present in 15/15 MAS finals on TXN-004. It is *decomposition-induced evidence
  re-weighting*: the decision funnels through Policy&Risk whose only tool
  (calculate_risk_score) cannot represent the decisive pattern, manufacturing an
  authoritative low-risk anchor; Reporting ("do not introduce new evidence") defers.
  gemma4's Reporting overrides the same anchor — yielding to architectural pressure
  is model character.
- Caveats for write-up: inter-node messages are not journalled (mechanism established
  from code structure + final texts); the tool-evidence gap is a DFAH instrument
  property affecting both arms equally.

## Escalate-case table (escalations /15 at t07, single|mas)

| case | signal | q3.5 | q7b | q14b | gemma4 |
|---|---|---|---|---|---|
| 002 | sanctions hit (tool-confirmable) | 15\|14 | 1\|8 | 12\|12 | 14\|15 |
| 004 | structuring | 12\|0 | 1\|0 | 1\|0 | 14\|11 |
| 015 | sanctions-adjacent | 5\|1 | 0\|0 | 1\|0 | 15\|14 |
| 039 | weapons/export | 8\|0 | 2\|0 | 6\|0 | 15\|9 |
| 049 | crypto mixer | 6\|3 | 2\|1 | 1\|4 | 15\|12 |

(Full 15-case tables reproducible via the journal recipes in this session's log.)
