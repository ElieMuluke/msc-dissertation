# Experiment changelog (pre-registration discipline)

Any edit to a locked design constant before launch gets a dated note here.
After run 1, changes invalidate the pre-registration (PRD-A).

## 2026-08-06 — final pre-launch fix batch (port reviews + goals audit)

- **tokens ÷ pass^k at all k**: `analysis/metrics.py` previously reported a
  single `tokens_per_pass` at k = n_repeats (k=15 would likely be zero →
  empty cell). Now `pass^k` and `tokens_per_pass^k` are reported at every
  supported k ∈ {1, 5, 15} (plus k=n) as separate columns. **Pre-registered
  as all-k reporting, decided 2026-08-06 before any results exist** — no
  post-hoc k choice.
- **Recursion guard** (`app/agents/single.py`): graph recursion limit is now
  `max(1, 2*max_iterations+4)` — adversarial finding: `max_iterations < 1`
  would produce an invalid limit. Unreachable at the locked value (8);
  guarded anyway.
- **Client libs pinned** (`backend/requirements.txt`): ollama==0.6.2,
  langchain-ollama==1.1.0, langchain-core==1.4.9, langgraph==1.2.9 — the
  wire-payload tests mock the client boundary, so an unpinned reinstall
  could change wire serialization invisibly.
- Production-side parity (PRD-B, no experiment-design impact): analysis
  model factory now sends `think:false`/`num_ctx=16384`/`num_predict=2048`
  like the harness factory; audit reports pin the model digest and persist
  injected session context; `.env.example` documents ANALYSIS_* vars incl.
  the :11436 sweep rule.

## 2026-08-06 — arm A ported to LangGraph (owner decision)

Rationale: both arms now execute on the same LangGraph runtime, removing a
framework confound between arms (previously arm A ran a hand-rolled
LangChain loop while arm B ran LangGraph). `app/agents/single.py` now
compiles the tool loop as the idiomatic ReAct graph (agent node + tool node
+ conditional edges); `run_tool_loop` keeps its signature and is still the
single code path used by arm A directly AND by every arm-B node, so the
port covers both arms at once. `langgraph.prebuilt.create_react_agent` was
rejected: its recursion limit raises instead of gracefully returning the
last assistant text, breaking our max-iterations semantics.

- Prompts, case rendering, and wire parameters unchanged: every model call
  still carries `think: false`, `options.seed`, `options.temperature`,
  `num_ctx`, `num_predict` — asserted by a new adversarial wire-payload
  test that mocks `ollama.AsyncClient.chat` and inspects captured payloads
  over a multi-turn tool run (`experiments/tests/test_single_graph.py`).
- Loop semantics byte-preserved: max-iterations cap (final call's tools
  still executed, last text returned), unknown-tool `error:` results,
  requested-call recording order, `SingleAgent` constructor signature (the
  production adapter call site in `app/agents/runner.py` is untouched).
- No observable behavioural deltas: `agent_messages` still counts LLM
  (assistant) messages — one per agent-node invocation, same number as the
  pre-port loop; token accounting and `tool_calls` identical.
- `config_hash` verified UNCHANGED (`76337b11ca1c…`) — prompts and wire
  params are what the manifest hashes, and neither moved; manifest not
  regenerated.

## 2026-08-06 — package relocated to backend/experiments/ (owner decision)

Mechanical move of the whole `experiments/` package (results/, gates
evidence, manifest, CHANGELOG, PILOT-NOTES, perturbation cases included)
from repo root to `backend/experiments/`, so it shares the `backend/`
package tree with `app/` and the `sys.path` shim in `experiments/__init__`
is deleted. Runner/scripts/tests now run from `backend/` (or with
`PYTHONPATH=backend`). Path derivations updated: `config.py` root
constants, `scripts/launch-sweep.sh`, the FastAPI progress route
(`app/api/routes/analysis.py`), tests conftest, PRD-A layout line.
**No locked design constant touched; `config_hash` verified unchanged
(`76337b11ca1c…`) — the hashed config contains no filesystem paths, so
`results/manifest.json` was NOT regenerated.**

## 2026-08-05 — pre-launch review fixes (conformance + adversarial review)

All pre-launch (no journalled runs yet); no locked design constant changed.

- **F1** `harness/journal.py`: torn-tail healing on open-for-append. A
  kill -9 mid-write leaves a partial line with no trailing newline; the
  next append would merge onto it (run lost from resume, later
  JSONDecodeError in both runners). Implemented as truncate-back-to-last-
  complete-line rather than the suggested newline-first write: newline-
  healing would leave the fragment as a corrupt *middle* line, which the
  (deliberately strict) reader then rejects. The torn run simply re-runs.
- **F2** `harness/journal.py` + `harness/runner.py`: `write_progress` now
  uses a unique tmp name per call (pid+uuid) before the atomic rename —
  the two arm runners can no longer race on a shared tmp path; all
  `write_progress` call sites in the runner are wrapped so progress
  reporting can never kill a sweep.
- **F3** `harness/runner.py`: model-digest drift vs the manifest is now a
  hard failure at runner start; `--allow-digest-mismatch` overrides (with
  a mandatory CHANGELOG note). `scripts/launch-sweep.sh` verifies the
  post-pull digest on both servers against the manifest and aborts on
  mismatch.
- **F4** `harness/extraction.py`: docstring (the pre-registration record)
  aligned to the implemented rule — only the last non-empty line is
  examined, earlier `FINAL DECISION:` lines are ignored; the trailing-
  code-fence → malformed mode is documented and accepted.
- **F5** `scripts/launch-sweep.sh`: pre-existing `ollama-armA/B` tmux
  sessions are now a hard error (stale servers can't be verified to carry
  the pinned env); `--recreate` kills and restarts them. Pre-existing
  runner sessions always abort (duplicate writers on one journal).
- **R2** `harness/manifest.py`: sampling section now records top_p/top_k/
  **min_p** numerically (server defaults 0.9/40/0.0, `set_by_harness:
  false`); modelfile overrides remain visible in `model_show`. Config hash
  changed accordingly; `results/manifest.json` regenerated pre-launch.
- Git-sync path bug: runner now threads its `results_dir` into
  `git_sync.sync_results`, so a pilot with `--results-dir` can no longer
  commit the default results directory.
- `results/.gitignore` added: `runner-*.log`, `.git-sync.lock`,
  `.progress-*.tmp` excluded from the 25-run checkpoint commits.

## 2026-08-05 — initial build

- Harness built per PRD-A "Components to build"; no deviations from the
  locked constants table.
- Operationalisations fixed before run 1 (recorded here because the PRD
  leaves them implicit):
  - Decision extraction: label read from the **last non-empty line**,
    markdown emphasis chars stripped, one trailing `.`/`!` tolerated,
    case-insensitive (`experiments/harness/extraction.py`).
  - Varied seeds: drawn from `MASTER_SEED=20260805`; the same seed is
    shared by both arms for a given (condition, case, repeat) so the arm
    comparison is not confounded with the seed schedule.
  - MAS tool partition (union = arm A's full set): data agent →
    `search_precedents`, `get_customer_profile`, `check_sanctions_list`;
    policy&risk → `calculate_risk_score`; orchestrator/reporting → none
    (`experiments/config.py::MAS_TOOL_PARTITION`).
  - Entropy normalised by `log2(4)` (3 decisions + malformed).
  - `num_ctx=16384`, `num_predict=2048`, `max_iterations=8`,
    `run_timeout_s=900` — recorded in the manifest config hash.
- G0 and G1 probed on the dev server: both PASS (see
  `experiments/PILOT-NOTES.md`); model stays `qwen3.5:9b`.
