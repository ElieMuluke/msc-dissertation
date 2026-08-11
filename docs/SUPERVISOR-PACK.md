# Supervisor pack — AML repeatability experiment (meeting 2026-08-11)

Elie Muluke, MSc Applied AI, WMG. Compiled 2026-08-08. All materials committed at
github.com/ElieMuluke/msc-dissertation; every number below is reproducible from the raw
run journals via four independent audit scripts.

## What was done

- **Pre-registered design** (PRD-A, committed before run 1): single monolithic agent vs
  4-agent LangGraph pipeline (Orchestrator → Data → Policy & Risk → Reporting), same
  model/tools/rulebook/seeds per (condition, case, repeat); 50 externally-authored DFAH
  Compliance Triage cases + 10 owner-reviewed perturbation variants; conditions T=0
  fixed-seed ×5 and T=0.7 varied-seed ×15 (+ perturbation T∈{0,0.5,1.0}×5); 2,300 runs
  per model.
- **9,200 scored runs over four models**: qwen3.5:9b (headline), qwen2.5:7b-instruct,
  qwen2.5:14b-instruct (all Ollama 0.31.1), gemma4 (Ollama 0.32.6, documented second
  infra context). Two model families, three sizes/generations within qwen.
- **Six further models excluded by pre-registered capability gates**, with archived
  evidence on both Ollama versions (mistral-nemo, mistral-small3.2, llama3.1:8b,
  gemma3:27b, granite4, gpt-oss:20b).
- **Four independent fresh-context audits** — one per sweep, each recomputing every
  reported number from raw journals with independently written code: all four returned
  ANALYSIS CONFIRMED (details: `backend/experiments/analysis/independent_check_*.py`).

## Headline results (T=0.7, primary condition; full tables in per-model reports)

| metric | qwen3.5:9b | qwen2.5:7b | qwen2.5:14b | gemma4 |
|---|---|---|---|---|
| single pass^1 | 0.364 | 0.293 | 0.248 | 0.552 |
| mas pass^1 | 0.253 | 0.449 | 0.221 | 0.297 |
| single DAR | 0.618 | 0.719 | 0.893 | 0.594 |
| mas DAR | 0.802 | 0.647 | 0.914 | 0.705 |
| alpha single/mas | .205/.203 | .102/.279 | .382/.340 | .387/.406 |
| arm diff significant? | yes (both, p≤.003) | yes (both) | no | yes (both, p≤.011) |

## Findings

1. **Decomposition changes repeatability — but the direction is model-dependent.**
   Headline pattern (single more label-accurate, MAS more repeatable; at k≥5 MAS's
   stability wins) holds for qwen3.5:9b and gemma4; qwen2.5:7b shows the mirror image;
   qwen2.5:14b converges (no significant arm difference). Conclusion: no universal
   answer — multi-agent reliability claims must be validated per model. This is the
   thesis's core empirical contribution.
2. **"T=0 + fixed seed" does not mean repeatable — and it's mechanistic, not noise.**
   Audited byte-level forensics across all four models: qwen3.5 fully deterministic;
   qwen2.5:7b cold-cache divergent (first evaluation after another prompt differs; warm
   repeats byte-identical) flipping 25/100 case-group decisions; qwen2.5:14b same
   byte-level signature but only 7 flips (scale absorbs the perturbation before the
   decision); gemma4 worst (99/100 divergent, 35 flips; its MAS arm diverges on every
   repeat, not just cold-cache). Persists across both Ollama versions. Framing:
   fixed-seed T=0 agreement measures *sensitivity to server request history*;
   decomposition amplifies exposure (~10 chained calls vs 2–3).
3. **Most local models cannot run a tool-using compliance workflow at all.** 6/10
   candidates failed capability gates with byte-identical failure signatures on two
   Ollama versions (open upstream parser bugs #17274/#16932). Capability gating before
   reliability measurement is a methodological requirement, not a nicety.
4. **Consistent secondary results**: MAS is more format-disciplined (malformed outputs
   concentrate in the single arm, all four models); all models over-produce
   `investigate` vs the benchmark labels except gemma4 (healthiest decision balance and
   the best single-arm label agreement in the experiment, pass^1=0.552); MAS costs
   ~1.8× tokens and ~2.5–3.4× wall-clock per decision (per-arm token accounting
   pre-registered as the answer to the equal-compute critique, arXiv:2604.02460).
5. **Instrument checks passed**: perturbation variants flip decisions at T>0 in both
   arms (repeatability isn't degeneracy); malformed handled as an outcome category
   (0.2–0.9% per sweep).

## Version-isolation addendum (2026-08-11, audited)

All three qwen sweeps were re-run under Ollama 0.32.6 with identical seeds/design
(6,900 additional runs; combined independent audit CONFIRMED). Result: byte-divergence
counts at T=0 fixed-seed are identical across versions in every cell (qwen3.5 0/60 →
0/60; 7b 96/100 → 96/100; 14b 105/110 → 105/110); decision flips within ±2; primary
Tier-1 deltas ≤0.04 — far below reported effect sizes. Two refinements: (a) qwen3.5's
raw output bytes changed on ~96% of runs between versions while remaining perfectly
deterministic within each — determinism *class* is version-stable even when numerics
are not; (b) qwen2.5:14b reproduced its entire 2,300-run sweep decision-for-decision
(2,297/2,300 byte-identical), forensically verified as a genuine re-run. Conclusion:
cache-state T=0 sensitivity is a model property, invariant to serving-stack version;
the gemma4 family-vs-version confound is resolved (version contributes ~nothing).
Total corpus: 7 sweeps, 16,100 scored runs, 7 independent audits (incl. combined),
all CONFIRMED.

## Winner selection (pre-registered, decision pending owner sign-off)

Criterion: Tier-1 hierarchy on the headline model (qwen3.5:9b). pass^k splits by k
(pass^1 → single; pass^5/pass^15 → MAS), so the hierarchy falls to 1.2 DAR → **MAS**,
with the near-equal chance-corrected alpha (.205 vs .203) reported as the honest
caveat. Production default flips to the winner after sign-off.

## Artifact (Design Science contribution)

Production AML platform sharing the *same measured agent modules*: account-in →
decision + auditable report out (full tool-call trace, session context, model digest
per report); RAG over FATF/JMLSG/OFSI corpus; sanctions/FATF screening from an ingested
sqlite watchlist store (42,705 entries, provenance recorded); IBM AML tabular store
(2.13M accounts / 179.7M transactions). Owner demo session surfaced two production
bugs (bank-id zero-padding silently emptying transaction queries; iteration-cap
starvation) — both diagnosed *from the audit-trail reports* and fixed with regression
tests: the auditability requirement demonstrably works.

## Limitations to state up front

- Labels are single-author and unadjudicated → all accuracy framed as *agreement with
  benchmark-author labels*; planned JMLSG re-adjudication of 15–20 cases still open.
- gemma4 changes family and Ollama version together — its differences vs qwen cannot be
  attributed to either alone.
- Token budgets differ between arms by design; reported per-arm, not equalized.
- Wall-clock indicative only (background load during some windows); tokens primary.
- Single hardware/inference stack (Ollama on one RTX PRO 5000); cache-state findings
  are properties of this stack class, argued (not shown) to generalize.

## Files

- Per-model reports: `backend/experiments/results*/analysis-report.md` (+ figs/)
- Cross-model table: `backend/experiments/cross-model-comparison.md`
- Deviation record: `backend/experiments/CHANGELOG.md`; gate evidence:
  `results*/gates/` (both Ollama versions); audits:
  `backend/experiments/analysis/independent_check_*.py`
- Design: `docs/PRD-A-experiment.md` (pre-registered), `docs/PRD-B-production.md`
