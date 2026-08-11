# Experiment changelog (pre-registration discipline)

## 2026-08-10 — harness v2 (branch `harness-v2`, NOT active on main)

harness v2 — activated only after context-2 chain seals; sweeps 1-7 ran on
harness v1 (main). No v1 sweep result is affected: `main`'s runner, agents
and journal schema are byte-identical to what sweeps 1-7 executed, and
every v2 default reproduces v1 behaviour exactly (`cache_policy="none"`,
additive-only journal keys).

Changes on this branch:

- **MAS inter-node journaling** — `AgentResult` gains an optional
  `node_outputs` field (`None` for the single arm); the MAS graph fills it
  with each node's output text keyed by node name in pipeline order
  (orchestrator, data, policy_risk, reporting), and the runner journals it
  per line as `node_outputs`.
- **Cache-state control** — pre-registrable runner option
  `--cache-policy {none|prewarm|shuffle}` (`ExperimentConfig.cache_policy`,
  default `none` = v1-identical). `prewarm` sends each t0-fixed/pert-t0
  run's exact opening prompt once beforehand and discards it (warm-state
  repeatability); `shuffle` permutes per-repeat case order
  deterministically from `MASTER_SEED` (arm- and model-independent, so
  comparability holds). The policy is recorded in the manifest's hashed
  config record and on every journal line; changing it mid-sweep
  invalidates comparability (documented in the config docstring).
- **Environment fingerprint** — every journal line gains `env`: GPU
  name/driver/VRAM-used snapshot (nvidia-smi, cached per
  `env_fingerprint_every=25` runs) plus host 1-min load and a
  load-high flag; all GPU fields are `null` where nvidia-smi is absent
  (`experiments/harness/env_fingerprint.py`).
- Journal schema doc comments extended (`journal.py`, `runner.execute_run`);
  mocked tests added (`experiments/tests/test_harness_v2.py`).

## 2026-08-08 — infra-context-2 qwen replications (owner-approved, pre-launch)

Purpose: de-confound model family vs Ollama version for the cache-state
determinism findings. The three qwen sweeps completed under Ollama 0.31.1
(infra context 1) are re-run under 0.32.6 (infra context 2) with identical
seeds and design: same 50 + 10 cases, same conditions/repeats, same
2,300-run planned seed schedule (`planned_runs()` depends on `MASTER_SEED`
only), same digest-pinned model blobs.

Mechanism: `config.REPLICATION_MODELS` extended so a registry KEY can
differ from the served MODEL TAG. New keys (each with its own isolated
results dir; runners/manifests/servers use the tag):

- `qwen2.5:7b-instruct@0.32.6` → `results-qwen2.5-7b-ollama0326/` (think=None)
- `qwen3.5:9b@0.32.6` → `results-qwen3.5-9b-ollama0326/` (think=False, as original)
- `qwen2.5:14b-instruct@0.32.6` → `results-qwen2.5-14b-ollama0326/` (think=None)

Existing keys resolve byte-identically (asserted by test); `config_hash`
of each context-2 manifest intentionally equals its original sweep's hash
(same design, same model identity) — the infra context is carried by the
manifest's `ollama_version` and every journal line's `ollama_version`.
Mini-gates re-run per key against the pinned servers before launch;
evidence in each context-2 dir's `gates/`.

The original 0.31.1 results are untouched and remain the pre-registered
results (qwen3.5:9b headline, replications as pre-registered robustness
checks). The context-2 sweeps are exploratory infra replications, analysed
as a separate context, never merged with context-1 journals.

## 2026-08-07 (evening) — infra context 2: Ollama 0.31.1 → 0.32.6; re-gate results; gemma4 admitted

Owner upgraded Ollama to 0.32.6 (all three qwen sweeps were completed and sealed under
0.31.1; per-run `ollama_version` in every journal keeps contexts separable). Prior
0.31.1 gate evidence archived per model as `gates/mini-gates-ollama-0.31.1.json`.
Re-gate under 0.32.6: mistral-nemo FAIL (identical signature, empty output eval=42),
mistral-small3.2 FAIL (identical), llama3.1 FAIL (identical raw-JSON-in-content),
gemma3:27b FAIL (0/8 both arms), granite4 FAIL 6/8 (improved from 5/8, below bar),
gpt-oss:20b FAIL (structural thinking + 4/8). Conclusion: the tool-call parser gap is
version-stable for these models (upstream #17274/#16932 open) — the before/after pair
is recorded as a methodology finding. NEW: gemma4:latest (the model the 0.32.x notes
explicitly fixed) gates ALL PASS 8/8 → admitted as the fourth sweep model, first and
only model of infra context 2. Its results are analyzed within-model (single vs MAS)
and cross-model comparisons note the version difference explicitly.

Any edit to a locked design constant before launch gets a dated note here.
After run 1, changes invalidate the pre-registration (PRD-A).

## 2026-08-07 (00:50) — qwen2.5 replication restarted from zero at owner request

The qwen2.5:7b-instruct sweep had been paused at 135/2300 (to gate mistral-small) and
resumed to 410/2300. Owner requested a fully uninterrupted run instead; the partial
journals (591 runs incl. the resumed segment) were archived untouched to
`results-qwen2.5-7b/partial-run-aborted-2026-08-07/` (never mixed with the fresh run)
and the sweep relaunched from run 1 on the same manifest (identical seed schedule).
Note: resume-vs-restart yields identical planned runs by design; the restart is a
conservatism choice, not a correctness requirement.

## 2026-08-07 (00:30) — llama3.1:8b provisional gate FAIL; audit of headline analysis CONFIRMED

- llama3.1:8b (candidate third model) failed the pilot gate in the same way as both
  mistrals: single arm 0/4 (all malformed, ~1.5 s), MAS 4/4 valid. Probe evidence: with
  the experiment system prompt + bound tools, the model emits its tool call as raw JSON
  in text content which Ollama 0.31.1 fails to parse into a structured call
  (short-system control parses fine). Same class of failure as the mistral family →
  root cause is Ollama-version tool-template robustness, not any single model. Probes
  ran on the dev server (:11434) because the pinned servers were mid-sweep; any future
  launch requires pinned re-gating. Replication set for now: qwen2.5:7b-instruct only.
  Possible path for a third family: Ollama upgrade AFTER all current sweeps, as a
  documented separate infra context, then re-gate.
- Independent audit (fresh-context agent, own code:
  `analysis/independent_check_qwen35.py`) of the sealed qwen3.5:9b analysis:
  ANALYSIS CONFIRMED — integrity clean, all metrics reproduced to 3 d.p., stats match.
  One convention note: single/t07 majority_vote_accuracy 0.360 rests on first-observed
  tie-breaking for two 7–7 tied cases (TXN-2025-017, TXN-2025-048); strict-majority
  rule gives 0.340. Footnote in the dissertation; not corruption.
- Malformed-count clarification: 4 total in the headline sweep = 3 in single/t07-varied
  + 1 in single/pert-t10 (PERT-005 repeat 2). MAS: zero.

## 2026-08-06 (late) — mistral-nemo excluded on failed mini-gate; mistral-small3.2:24b substituted

mistral-nemo:latest failed its mini-gate: single-arm pilot 0/4 valid extractions.
Diagnosis (reproduced; evidence `results-mistral-nemo/gates/mini-gates.json`): with the
experiment's system prompt (~1.7k chars) AND tools bound, the model returns empty
content and no tool calls; short-prompt+tools works, real-prompt-without-tools works.
Accommodating it would require per-model prompt changes — a design fork breaking
cross-model comparability — so the model is excluded, not accommodated. Substitute
third model: `mistral-small3.2:24b` (same family, native function calling; mini-gates
to run before its launch). Decision made after the headline sweep was sealed and before
any nemo sweep run. qwen2.5:7b-instruct replication launched first (mini-gates ALL
PASS: think-probe clean, determinism 5/5 byte-identical, pilot 8/8).

## 2026-08-06 (evening) — replication extension: two additional models

Owner-approved, recorded BEFORE any replication run. After the qwen3.5:9b
sweep is verified and sealed, the ENTIRE pre-registered design is
replicated on two further models:

- `qwen2.5:7b-instruct` (anchor model of arXiv:2511.07585; pulled
  2026-08-06, digest `845dbda0ea48ed749caa…`)
- `mistral-nemo:latest` (already local, digest `e7e06d107c6c86ed0cf4…`)

Identical design: same 50 + 10 cases, same conditions and repeat counts,
same metrics tier table, and the **same planned seed schedule** —
`planned_runs()` derives seeds from `MASTER_SEED` only, independent of
model, so per-(condition, case, repeat) seeds are identical across models
for cross-model comparability (asserted by test).

Each model gets its own sibling results dir (`results-qwen2.5-7b/`,
`results-mistral-nemo/`) with its own manifest (own digest, own
config_hash — the hash pins model identity), journals, progress and gates
evidence; no cross-dir contamination (asserted by test).

Think handling per model: qwen3.5:9b keeps `think: false` on the wire;
the two replication models have no documented thinking mode, so the
parameter is **omitted** (`think=None`; the ollama client serializes with
`exclude_none`) — exact behaviour captured per model by the new
mini-gates (`experiments.harness.mini_gates`) before their launch.

**`qwen3.5:9b` remains the headline pre-registered result; the
replications are analysed as robustness checks** (per-model reports via
`analysis.report --model`, side-by-side Tier 1 via `analysis.compare`).

## 2026-08-06 — gate day: arm-A server port :11434 → :11437 (pre-launch)

Environment constraint found during launch-gate prep: the machine's
systemd Ollama service (runs as user `ollama`, unpinned env, default
KEEP_ALIVE/NUM_PARALLEL) permanently owns :11434 and cannot be stopped
without interactive sudo, which the gate session does not have. Rather
than run arm A on an unpinned server, arm A's dedicated pinned server
moved to **:11437** (`scripts/serve-armA.sh`, `experiments/config.py`,
`scripts/launch-sweep.sh`); arm B stays on :11435 as pre-registered.
The systemd server on :11434 becomes the dev/analysis server (taking the
role PRD-A assigned to :11436) and must receive no sweep traffic.

Both pinned servers read the world-readable system model store
(`OLLAMA_MODELS=/usr/share/ollama/.ollama/models`) — user `el` has no
local store, and the system store holds the exact digest-pinned weights
(verified against the manifest on both servers at gate time).

Port numbers are execution infrastructure, not a locked design row (the
locked constant is "two Ollama servers, one arm each, pinned env"), and
no journalled runs exist; recorded here pre-launch per the
pre-registration discipline.

## 2026-08-06 — manifest re-stamp + ROUGE-L appendix metric (pre-launch)

- **Manifest re-stamped** post pre-registration commit, pre-run-1: the
  recorded `git_sha` (`a1aec5c`) predated the commits that contain the
  reviewed harness; regenerated so it points at the committed code
  (`944b0bd`). Verified: `config_hash` unchanged (`76337b11ca1c…`) and the
  2,300-run plan (seeds, order, totals) plus model digest/show/version are
  byte-identical — only `git_sha` and `created_at` differ. No journals
  existed at re-stamp time.
- **ROUGE-L lexical consistency added** (lecturer-requested, appendix tier,
  pre-registered 2026-08-06 while journals are empty): per-case mean
  pairwise ROUGE-L F1 over the FULL `raw_output` across repeats
  (token-level LCS, lowercase, whitespace tokenization; implemented
  in-repo, no new dependency). Reported per arm × condition in its own
  "Appendix: lexical consistency (ROUGE-L)" report section, labelled as
  surface-form overlap, distinct from decision- and trajectory-level
  metrics. **Does not alter the pre-registered Tier 1 winner criterion.**
  BLEU was rejected: BLEU is precision/reference-oriented and needs a
  designated reference; repeats of one case have none, while pairwise
  ROUGE-L F1 is symmetric and reference-free.

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
