# PRD-A — Repeatability Experiment Harness

Owner: Elie Muluke. Status: locked design, pre-registered 2026-08-05.
Deadline chain: **build Wed 6 Aug → gates + pilot Thu 7 Aug daytime → launch Thu 7 Aug evening → sweep done ~Sun 10 Aug → results Mon 10 Aug → analysis Tue 11 Aug (supervisor meeting) → draft 12 Aug.**

## Research question

Does decomposing one compliance agent into a multi-agent pipeline change decision repeatability, and at what cost? Thesis claim: *first measurement of decision repeatability as a function of agentic decomposition in a compliance-triage workflow, via controlled repeated-run comparison on an externally authored benchmark.*


## Locked design constants

Changing any row after run 1 invalidates the pre-registration. Edits before launch require a dated note in `backend/experiments/CHANGELOG.md`.

| Constant | Value |
|---|---|
| Model | `qwen3.5:9b`, pinned by sha256 digest in manifest, thinking disabled via API parameter (`think: false`) |
| Arms | A: monolithic single agent, all tools. B: LangGraph 4-agent pipeline (Orchestrator-Planner → Data Agent → Policy & Risk Agent → Reporting Agent). Same model, same tools, same rulebook in both |
| Cases (scored) | 50 DFAH Compliance Triage cases (`alerts.json`), verbatim. DFAH mocked tools only |
| Cases (instrument check) | 10 perturbation variants (minimal edits to DFAH cases that flip the label), drafted 2026-08-05, owner-reviewed before launch |
| Condition 1 | T=0, fixed seed, 5 repeats — determinism baseline. Expected flat; pre-registered as a finding about local inference either way |
| Condition 2 | T=0.7, seed varied per repeat, 15 repeats — primary condition |
| Perturbation sweep | T ∈ {0, 0.5, 1.0} × 5 repeats, seed varied at T>0 |
| Sampling params | top_p, top_k, min_p at Ollama defaults, recorded in manifest, held fixed |
| Seeds | Pre-generated list in `manifest.json` before run 1. Runner consumes by index — resume reproduces the exact planned sequence |
| Decision extraction | Agent output must end `FINAL DECISION: <escalate|dismiss|investigate>`; parsed by regex. JSON mode stays off (ollama#12559 breaks fixed-seed determinism) |
| Malformed output | Outcome category `malformed`, never excluded, never retried |
| Canonical trajectory | Ordered list of external tool-call names only. Role prompts and inter-agent hand-offs excluded — the only definition comparable across arms |
| Statefulness | Every run fresh context. No memory across runs or cases |
| Execution | Two Ollama servers, one arm each, arms parallel, each arm internally sequential |

## Run matrix

| Block | Cases | Arms | Conditions × repeats | Runs |
|---|---|---|---|---|
| Primary | 50 | 2 | T=0.7×15 + T=0×5 | 2,000 |
| Perturbation | 10 | 2 | 3 temps × 5 | 300 |
| **Total** | | | | **2,300** |

## Gates — all green before launch (Thu daytime)

- **G0 think-off:** `qwen3.5:9b` with `think: false` returns zero `<think>` content over 10 pilot calls. Red → first capture and inspect the raw responses (is the parameter accepted? where does think content surface — separate field or inline?) and try documented alternatives; fall back to `qwen2.5:14b-instruct` only after that diagnosis, with findings + decision noted in CHANGELOG.
- **G1 determinism:** T=0 + fixed seed + `OLLAMA_NUM_PARALLEL=1` gives byte-identical output on 5 consecutive calls (after 1 discarded warm-up). Red → diagnose before any launch.
- **G2 DFAH runs:** repo installed, 50 cases load, mocked tools respond, one case completes through DFAH's own runner.
- **G3 both arms end-to-end:** each arm completes 5 cases × 3 repeats via the adapter; journal lines valid; extraction succeeds on ≥ 13/15 runs per arm. Red on MAS → merge Data Agent into Policy & Risk (3-agent fallback), note in CHANGELOG.
- **G4 resume:** kill runner mid-pilot, restart, verify it skips completed runs and continues on the planned seed sequence.

## Components to build (Wed)

Repo: this repo, `backend/experiments/` package (relocated 2026-08-06 from repo-root `experiments/` to share the `backend/` package tree with `app/`). Layout: `backend/experiments/single/`, `backend/experiments/mas/`, `backend/experiments/harness/`, `backend/experiments/analysis/`, `backend/experiments/results/`.

1. **DFAH integration** — `pip install dfah-bench` (0.1.1); vendor case file path + mocked tools into harness config.
2. **Arm A** — monolithic agent: one system prompt (rulebook inline), DFAH mocked tools, `FINAL DECISION:` output contract.
3. **Arm B** — LangGraph pipeline per topology above. Each node same model/params. Reporting Agent emits the `FINAL DECISION:` line.
4. **Adapter** — both arms behind `async arun(case, context) -> AgentResult`. Same adapter class for both; arm is a constructor argument. Published DFAH-Bench numbers are context only — the comparison is strictly internal A-vs-B.
5. **Runner** — consumes `manifest.json` (full planned run list + seeds + model digest + config hash + git sha). Per run: append one JSONL line, flush + fsync. On start: read journal, skip completed `(case_id, arm, condition, repeat_idx)`. Every 25 runs: `git add results && git commit && git push` — push failure logs and retries next cycle, never kills the sweep. Writes `results/progress.json` (done/total per arm, ETA, last-run timestamp) after every run — this is the progress bar; a `watch cat` or one FastAPI route can render it.
6. **Metrics module** — computes the tier table below from journal alone.
7. **Launcher scripts** — `scripts/serve-armA.sh` (`:11434`), `scripts/serve-armB.sh` (`:11435`), each `OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=-1`, run under tmux; `scripts/launch-sweep.sh` starts both runners.

## Journal schema (single source of truth for analysis)

One JSON object per line, `results/journal-{arm}.jsonl`:

```json
{"run_id": "", "case_id": "", "arm": "single|mas", "block": "primary|perturbation",
 "condition": "t0-fixed|t07-varied|pert-t0|pert-t05|pert-t10",
 "repeat_idx": 0, "seed": 0, "temperature": 0.0,
 "model": "qwen3.5:9b", "model_digest": "sha256:…", "ollama_version": "",
 "think": false, "started_at": "", "wall_clock_s": 0.0,
 "prompt_tokens": 0, "completion_tokens": 0,
 "tool_calls": ["tool_name", "..."], "agent_messages": 0,
 "raw_output": "", "decision": "escalate|dismiss|investigate|malformed",
 "error": null}
```

## Metrics (pre-registered hierarchy — winner decided by Tier 1 order)

| Tier | Metric | Note |
|---|---|---|
| 1.1 | pass^k vs DFAH labels | **Primary.** Framed as agreement with benchmark-author labels, never "correctness" |
| 1.2 | DAR | pairwise decision agreement |
| 1.3 | Krippendorff's alpha | chance-corrected twin of DAR, always reported beside it |
| 1.4 | Flip rate | % cases with ≥1 divergent verdict |
| 2 | Majority-vote accuracy; normalised decision entropy; TAR + Jaccard + normalised LCS on canonical trajectory; per-case entropy distribution (histogram + worst 3 cases named) | |
| 3 | Tokens/run per arm; tokens ÷ pass^k; bootstrap CI over cases + permutation test on arm difference; wall-clock (indicative only) | Token accounting is the answer to the compute-confound critique (arXiv:2604.02460), cited pre-emptively |

Appendix-optional: G-Pass@k.

## Sweep operations (Thu evening → Sun)

- Discard one warm-up run per server after every model load.
- Dev inference during sweep: third server `:11436` only; the two sweep servers take runner traffic exclusively. Pre-registered sentence: token counts are the primary cost metric; wall-clock indicative.
- Crash: restart runner; resume is journal-driven (G4 proved it).
- Done when `progress.json` shows 2,300/2,300 and journal line counts match the manifest.

## Analysis deliverable (Mon)

`experiments/analysis/` script producing: the headline table (2 arms × 2 conditions × Tier 1), Tier 2 figures, cost table, perturbation temperature-trend figure, all from journal only. Output: `results/analysis-report.md` + figures. Monday completion criterion: every metric in the tier table computed for every arm × condition, or listed with the reason it could not be.
