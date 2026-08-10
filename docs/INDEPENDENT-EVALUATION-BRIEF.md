# Independent evaluation brief — AML repeatability experiment

You are a fresh, independent evaluator. You have had no involvement in this project and
must not trust any claim made in its documents until you have verified it against raw
data and code yourself. Your job: evaluate the entire research artifact — design,
implementation, data, analysis, and conclusions — as a skeptical examiner would.

## Context (facts you may take as given)

- MSc Applied AI dissertation (WMG, University of Warwick), Design Science Research,
  secondary data only. Research question: does decomposing a single LLM compliance
  agent into a multi-agent pipeline change decision repeatability, and at what cost?
- Repo: this working tree (github.com/ElieMuluke/msc-dissertation). Experiment code in
  `backend/experiments/`; shared agent implementations in `backend/app/agents/`;
  production platform in `backend/app/` + `frontend/`.
- Benchmark: DFAH Compliance Triage (50 cases), cloned at `/home/el/projects/dfah-repo`
  (cases: `econometrics/benchmarks/compliance_triage/data/alerts.json`; mocked tools:
  `.../compliance_triage/task.py`). Plus 10 owner-reviewed perturbation cases
  (`backend/experiments/perturbation_cases.json`).
- Completed sweeps live in `backend/experiments/results*/` — each dir has
  `manifest.json` (pre-generated plan incl. seeds), `journal-single.jsonl` +
  `journal-mas.jsonl` (raw runs), `gates/` evidence, and derived `analysis-report.md`.
  Two infrastructure contexts exist (Ollama 0.31.1 and 0.32.6), recorded per-run in
  the journals' `ollama_version` field. A sweep may still be running — treat any
  directory whose journal count is below its manifest total as in-progress and exclude
  it from scoring (state which you excluded).
- Python: `backend/.venv/bin/python`, run from `backend/`. Everything you need is
  local. Do NOT make LLM calls (ports 11434/11435/11437 serve live experiments); do
  NOT modify any file except your own outputs (write to a new file
  `docs/INDEPENDENT-EVALUATION-REPORT.md` and, if needed, scripts under
  `backend/experiments/analysis/` prefixed `eval_`).

## Blindness protocol (important)

Derive your own numbers and conclusions FIRST, from `manifest.json` + journals + the
benchmark label files only. Only AFTER you have written down your own headline table
and findings, open the project's derived documents (`analysis-report.md` files,
`cross-model-comparison.md`, `docs/SUPERVISOR-PACK.md`, `docs/ANALYSIS-INSIGHTS.md`,
`backend/experiments/CHANGELOG.md`, `PILOT-NOTES.md`, prior audit scripts
`analysis/independent_check_*.py`) and reconcile. Report agreements and disagreements
explicitly. Your evaluation must cover everything you find relevant — not only the
questions below.

## Required evaluation dimensions

1. **Design validity.** Read `docs/PRD-A-experiment.md` (the pre-registered design).
   Assess: does the design actually answer the research question? Are the conditions,
   repeat counts, seed policy, metric choices, and winner criterion sound? Identify
   confounds the design does or does not control (model, temperature, seeds, token
   budgets, infrastructure, statefulness) and judge the handling of each.
2. **Pre-registration integrity.** Using git history (`git log`, file dates) and the
   CHANGELOG: were design constants locked before data collection? Were deviations
   dated and justified? Is there any evidence of post-hoc changes to metrics or
   criteria after results existed?
3. **Implementation correctness.** Audit `backend/experiments/harness/` and
   `backend/app/agents/{contract,single,mas}.py`: seed/temperature plumbing to the
   inference server, statelessness between runs, arm symmetry (rendering, tools,
   extraction), journal durability/resume, timeout handling. Write targeted probes
   where code reading is insufficient (mock the client; no live calls).
4. **Data integrity.** For every COMPLETE sweep dir: journal counts vs manifest,
   duplicate/missing run keys, per-run seed/temperature/condition vs plan, digest and
   ollama_version uniformity, decision domain, malformed accounting. Any anomaly, any
   timestamp discontinuity — report and interpret it.
5. **Analysis correctness.** Recompute the full metric set independently (your own
   code): pass^k, DAR, Krippendorff alpha, flip rate, majority vote, normalized
   entropy, trajectory metrics (exact-order agreement, Jaccard, normalized LCS over
   tool-call name sequences), token/wall-clock costs, and the arm-difference
   statistics (bootstrap CI over cases + paired permutation test). Compare to the
   committed reports; flag any discrepancy beyond rounding.
6. **Findings validity.** From your own numbers: what are the defensible conclusions?
   Evaluate in particular (forming your own view before reading the project's):
   (a) whether single-vs-MAS differences are real, significant, and consistent across
   models; (b) what T=0 fixed-seed behavior shows, per model and per Ollama version,
   at byte level and decision level; (c) whether high agreement metrics reflect
   discrimination or degenerate answering (check decision distributions against label
   distributions); (d) what the benchmark's mocked tools return for the labelled
   cases and whether that affects label-agreement interpretation; (e) the perturbation
   block as an instrument check.
7. **Threats to validity the project may have missed.** Hunt actively: anything in
   the code, data, process, or framing that an examiner could attack and that the
   project's own documents do not already acknowledge. Rank by severity.
8. **The artifact** (production platform): does it credibly demonstrate the DSR
   contribution (same measured agent modules deployed; auditable per-analysis
   reports)? Light-touch review — the science is the focus.

## Deliverable

Write `docs/INDEPENDENT-EVALUATION-REPORT.md`:
- Your independently derived headline results table (per complete sweep).
- Verdicts per dimension above (SOUND / SOUND-WITH-CAVEATS / FLAWED, with evidence).
- Full reconciliation vs the project's committed reports (agree/disagree, numbers).
- Ranked list of weaknesses and viva risks, each with a concrete mitigation.
- An overall assessment: is this work defensible as-is; what must change before
  submission; what would elevate it.

Bound your effort sensibly: complete sweeps only, but all of them; depth over breadth
where you must choose; state explicitly anything you did not verify.
