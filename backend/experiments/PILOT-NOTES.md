# Pilot notes — gate probes and smoke tests

Date: 2026-08-05 (build day, pre-launch). Server: locally installed Ollama
0.31.1 on `:11434` (the pre-existing dev server — **not** yet launched via
`scripts/serve-armA.sh`, so `OLLAMA_NUM_PARALLEL=1` etc. were not pinned for
these probes; re-run both gates on the pinned servers Thursday before
launch). Model: `qwen3.5:9b`, digest `6488c96fa5faab64bb65…` (full digest in
`results/manifest.json`).

## G0 — think-off probe: PASS (8/8 clean)

Method: 8 non-streaming `/api/chat` calls with `"think": false` in the
request body, varied prompts, T=0.7, varied seeds. Raw responses:
`results/gates/g0-think-off.json`.

Findings:

- The parameter is **accepted** (HTTP 200 on every call; no warning field).
- With `think: false`, the response `message` object contains **only**
  `['content', 'role']` — no `thinking` key at all, and zero `<think>` tags
  inline in `content` across all 8 responses.
- Evidence snippet (call 1, message keys and content head):
  `message_keys: ['content', 'role']`,
  `content_head: "Yes, this transaction is highly suspicious because the amount of $9,999 sits just below common regulatory reporting thresholds…"`

Control (`results/gates/g0-think-control.json`), 1 call each:

| `think` param | `message.thinking` present? | where think content surfaces |
|---|---|---|
| omitted | **yes** (`"Thinking Process:\n\n1. **Analyze the Request:**…"`) | separate `message.thinking` field, not inline |
| `true` | yes (same shape) | separate `message.thinking` field |
| `false` | **no** | nowhere — field absent, content clean |

So qwen3.5:9b **thinks by default** on this Ollama version; `think: false`
is honoured and fully suppresses it. Consequence: the harness must always
send `think: false` — omitting it would silently burn thinking tokens.
Wire-path check: langchain-ollama 1.1.0 maps its `reasoning` kwarg directly
to the `think` request field (`chat_models.py:804`:
`"think": kwargs.pop("reasoning", self.reasoning)`); the model factory in
`experiments/harness/models.py` sets `reasoning=False`.

## G1 — determinism probe: PASS (5/5 byte-identical)

Method: T=0, `seed=42`, `think: false`, one discarded warm-up, then 5
consecutive `/api/chat` calls with an alert-triage prompt. Raw outputs:
`results/gates/g1-determinism.json`.

- All 5 outputs byte-identical: single sha256
  `fbdcf4c7fee5d26c6012c8e025d4f1ef0869506f4074b7974229e3fb339894b4`,
  length 895 chars.
- The fixed-prompt output already ends with the contract line:
  `…FINAL DECISION: investigate` (extraction regex matches).

Caveat for the record: probe ran on the dev server without
`OLLAMA_NUM_PARALLEL=1` pinned (single client, so no concurrent batching
occurred, and results were still byte-identical). Re-verify on the pinned
arm servers as part of Thursday's gate run.

## G2 — DFAH integration: PASS

`python -m experiments.harness.dfah_gate --case TXN-2025-002` output:

```
dfah-bench 0.1.1 installed
cases load: 50 primary, 10 perturbation
mocked tools respond: 4/4 (sanctions hit on Shadow Corp: True)
langchain wrappers build: ['search_precedents', 'get_customer_profile',
                           'check_sanctions_list', 'calculate_risk_score']
DFAH Replay completed: report at …/results/gates/g2-dfah-replay
G2 PASS
```

One case completed through DFAH's own `Replay` orchestrator (1 case × 2
replays, its minimum design), arm A behind the DFAH agent protocol; episode
store in `results/gates/g2-dfah-replay/`.

Note: `results/gates/g2-report.json` self-reports `"status": "partial"` — that
label comes from DFAH's own replay protocol (its strict decision-parse
eligibility rules for computing its published metrics), not from a failure of
this gate; the gate's criterion (case completes through DFAH's runner with
tools responding) is met, and the sweep uses the PRD-A runner, not DFAH's
eligibility pipeline.

## Arms smoke test (G3 direction): both arms end-to-end, 4/4 extraction

2 cases × both arms via `ArmAdapter`, T=0, seed=42, against `:11434` (arm B
pointed at the same server for the smoke only; the sweep uses `:11435`).

| arm | case | decision (label) | trajectory | msgs | tokens |
|---|---|---|---|---|---|
| single | TXN-2025-001 | investigate (dismiss) | profile, profile, sanctions, sanctions, risk | 3 | 3587+441 |
| single | TXN-2025-002 | escalate (escalate) | profile, sanctions, precedents | 2 | 2193+267 |
| mas | TXN-2025-001 | investigate (dismiss) | sanctions×2, profile×2, precedents, risk | 6 | 6076+1451 |
| mas | TXN-2025-002 | escalate (escalate) | sanctions×2, profile, precedents, risk | 6 | 5490+1037 |

`FINAL DECISION:` extraction succeeded on 4/4; tool trajectories and token
accounting populate correctly. (TXN-001 = investigate vs label dismiss is a
disagreement datum, not a harness fault.) Full G3 (5 cases × 3 repeats per
arm on the pinned servers) still to run Thursday.

## G4 — resume drill: PASS

Pilot (2 cases × 2 repeats, t0-fixed) in a throwaway results dir; journal
truncated to 2 lines to simulate a crash; runner restarted:

```
INFO arm=single planned=4 completed=2 todo=2
INFO [1/2] single:TXN-2025-002:t0-fixed:0 -> escalate (4.1s)
INFO [2/2] single:TXN-2025-002:t0-fixed:1 -> escalate (3.8s)
```

Completed `(case_id, arm, condition, repeat_idx)` skipped; remaining runs
executed in the manifest's planned order with the manifest seeds.
Additional finding: at T=0/seed=42 the **whole multi-turn agent loop**
(tool calls included) reproduced byte-identical `raw_output` across
repeats — determinism holds end-to-end, not just for single calls.
`progress.json` updated correctly (done=4, per-arm ETA populated).

## Open items before launch (Thu)

1. Start pinned servers via `scripts/serve-armA.sh` / `serve-armB.sh`; pull
   `qwen3.5:9b` on `:11435`; re-run G0 + G1 against both pinned servers.
2. Full G3 pilot: 5 cases × 3 repeats per arm on the pinned servers
   (`--max-cases 5 --max-repeats 3 --no-git --results-dir <pilot dir>`);
   require ≥13/15 extraction per arm.
3. Repeat the G4 kill/restart drill against the pinned setup (drill above
   used the dev server).
4. Owner review of `backend/experiments/perturbation_cases.json`
   (`owner_reviewed` still `false`) — required before launch.
5. Decide whether `results/gates/` artifacts stay in the repo when the
   25-run git sync starts committing `results/` (they will be included).

---

# Launch gates 2026-08-06 (pinned servers) — ALL GREEN

Environment: systemd Ollama (user `ollama`, **unpinned**) permanently owns
`:11434` and could not be stopped (interactive sudo unavailable) → arm A's
pinned server moved to **:11437** (CHANGELOG entry; `config_hash`
verified unchanged — base URLs are not hashed). Arm B on `:11435` as
planned. No stale tmux sessions existed (no tmux server was running).
Both pinned servers read the world-readable system model store
(`OLLAMA_MODELS=/usr/share/ollama/.ollama/models`; user `el` has no local
store). GPU: RTX PRO 5000, 48 GB — both models resident concurrently
(~15 GB each incl. 16k KV).

Pinning verified via `/proc/<pid>/environ` of both `ollama serve`
processes: `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`,
`OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_MODELS=…` present on both. Digest on both
servers equals the manifest pin
(`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`).

| Gate | Verdict | Evidence |
|---|---|---|
| G0 think-off, n=10, :11437 | **PASS 10/10** (no `thinking` field, no inline tags) | `results/gates/g0-think-off.json` |
| G1 determinism, :11437 | **PASS 5/5** byte-identical after 1 discarded warm-up | `results/gates/g1-determinism.json` |
| G2 DFAH runner | PASS 2026-08-05 (unchanged) | `results/gates/g2-report.json` |
| G3 both arms, 5 cases × 3 repeats, **concurrent** | **PASS 15/15 valid per arm** (bar ≥13/15), 0 malformed | `results/gates/g3-2026-08-06/journal-*.jsonl`, `g3-g4-2026-08-06.json` |
| G4 kill/resume on pinned setup | **PASS** (SIGKILL mid-run-2; restart: `planned=4 completed=16 todo=3`, planned seed 42 continued) | `results/gates/g3-g4-2026-08-06.json` |

Byte-equivalence hashes (port + server-move evidence):

- G1 probe output sha256
  `fbdcf4c7fee5d26c6012c8e025d4f1ef0869506f4074b7974229e3fb339894b4`
  (len 895) — **identical** to the committed 2026-08-05 pre-port,
  dev-server G1 evidence (verified against `git show c10dca9`).
- Agent-level anchor `single:TXN-2025-001:t0-fixed:0` on the pinned
  server: sha256(raw_output)
  `d68d7754e3f4ff08e47e2bc25435e3b3d09ceb65b68fdd4dfec0851e68c355a4`;
  decision/trajectory/agent_messages/tokens (3587+441) **exactly match**
  the 2026-08-05 dev-server run that was byte-identical pre- vs post-port.
  T=0 repeats byte-identical for both drilled cases today.

G3 wall clocks (both arms running concurrently — real GPU contention):

| Arm | runs | mean | median | min–max | mean tokens |
|---|---|---|---|---|---|
| single (:11437) | 15 | 5.9 s | 6.6 s | 3.6–8.9 s | 3,875 |
| mas (:11435) | 15 | 15.7 s | 14.1 s | 11.0–23.8 s | 7,612 |

Sweep ETA (1,150 runs/arm, arms concurrent, MAS is the bottleneck):

| Launch (BST) | arm A done (~1.9 h) | arm B done (~5.0 h) |
|---|---|---|
| Thu 19:00 | Thu ~20:53 | **Fri ~00:00** |
| Thu 20:00 | Thu ~21:53 | **Fri ~01:00** |

Add ~20–30 % buffer for longer perturbation/t07 outliers and checkpoint
overhead → worst case ~02:30. Far inside the "done by Sun" plan.

Server state at hand-off: tmux sessions `ollama-armA` (:11437) and
`ollama-armB` (:11435) RUNNING, pinned, digest-verified, models loaded.
Ready for `scripts/launch-sweep.sh`. Sweep NOT launched. Reminder: the
systemd server on `:11434` is now the dev/analysis server — no sweep
traffic; keep `ANALYSIS_OLLAMA_URL` pointed at `:11434` (not the sweep
ports) during the sweep.
