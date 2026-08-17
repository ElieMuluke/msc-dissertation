# Adversarial verification: empty MAS node outputs

Date: 2026-08-17. Role: adversarial verifier (refute, not confirm), commissioned
before any code change. Evidence: journal census, turn accounting, and offline
mocked-model probes over the REAL `run_tool_loop` / `MasAgent` code paths.
Zero LLM calls; no existing file modified; live sweep directory read-only.

Probes (reproduce with `cd backend && .venv/bin/python -m <module>`):

- `experiments.analysis.adv_emptynode_journal` — rates, C3 fates, C4 split, correlates
- `experiments.analysis.adv_emptynode_turns` — per-node tool-call attribution (mechanism discriminator)
- `experiments.analysis.adv_emptynode_wiremock` — mocked model through real `run_tool_loop`/`MasAgent`; Fix A offline test

## Observed numbers: verified, two corrections

Per-node empty rates (orch/data/policy_risk/reporting), MAS journals:

| model | n | rates | note |
|---|---|---|---|
| granite4.1-8b | 1150 | 0/0/0/0% | confirmed |
| deepseek-r1-14b@think | 1150 | 0/0/0/0% | confirmed |
| lfm2.5-8b@think | 1150 | 0/1.7/1.7/0% | confirmed (the "lfm2.5" row is the *thinking* sweep; `results-lfm2.5-8b` has no MAS journal) |
| muse-glimmer-30b think-off | 1150 | 0/19.7/0/0% | confirmed |
| muse-glimmer-30b @think | 201 (stopped) | 0/95.0/0/0% | confirmed |
| qwen3.5-9b@think-budget | 1150 | 0.0/0.5/8.3/0.7% | confirmed ONLY after excluding 11 error rows (10× Ollama `ResponseError: EOF`, 1 parse error) that have no `node_outputs` at all; counting them, rates read 1.0/1.5/9.1/1.7% |

Single-arm empties: granite 0, deepseek 0, lfm@think 27 (2.3%), muse think-off
1 (0.1%), muse@think 21/667 = 3.1% (LIVE, partial), qwen@think-budget 15
(1.3%). All 64 are scored `malformed`; zero exceptions.

## The mechanism (this reframes everything)

Tool names are disjoint across nodes (`MAS_TOOL_PARTITION`), so per-node tool
calls are exactly attributable from the flat journal list. Two distinct
mechanisms produce an empty node output, and they split the data cleanly:

**M1 — iteration-cap termination (the dominant mechanism, ~79% of node-empties).**
Every one of the 417 muse-glimmer empty-`data` runs (226 think-off + 191
@think) has **exactly 8 data-node tool calls = `max_iterations`**. The node
spent all 8 permitted model calls requesting tools; the loop's pre-registered
cap semantics end the run returning the final tool-call turn's (empty) text.
The model never reached an answer turn — there was no evidence summary to
lose. 5/6 qwen empty-`data` runs match the same signature (8-9 calls).
Thinking cannot be the cause here: **muse-glimmer think-off has no thinking
channel at all** (gate evidence `mini-gates.json`: `thinking_field_present:
false`, and 19.7% empties anyway). Corroboration: empty runs have MORE agent
messages (11.7 vs 9.6) but FEWER completion tokens (3449 vs 3819) — turns are
token-light tool requests; 138/226 empty runs repeat one tool ≥4×; empty rate
is highest at T=0 (25%) and falls to 10% at T=1.0 — a deterministic loop-trap
that temperature perturbs the model out of.

**M2 — single empty answer turn / thinking-budget exhaustion (~21%).**
qwen@think-budget `policy_risk`: 92/94 empties have ZERO policy tool calls and
~2× the completion tokens (13,964 vs 7,340 run mean; num_predict 8192): one
turn, all tokens on the thinking channel, empty content, no tool call.
Same class: lfm@think `policy_risk` 18/20 zero-tool, qwen `reporting` 8 (node
has no tools; one turn by construction).

## Verdicts

### C1 — "model returned empty content (thinking channel); not a harness bug" : REFUTED AS STATED

The claim's causal story is wrong for the dominant cell. 417/532 node-empties
are M1 cap-terminations in which no answer turn ever existed — and the largest
cell (muse think-off, 226) has no thinking channel, so "reasoning routed to a
separate thinking channel" cannot be its cause. The claim survives only for
the M2 minority (qwen/lfm `policy_risk`, qwen `reporting`).

On the "harness discarded text" fork: the mock probe (`adv_emptynode_wiremock`,
scenarios S1/S2, real `run_tool_loop`, langchain-core 1.4.9, `AIMessage.text`
confirmed a property returning str) **proves the overwrite hazard is real in
code** — a non-empty earlier assistant turn followed by an empty final turn
returns `""`. Whether the real cap-hit runs had narration on intermediate
turns is **not recoverable from disk** (journals hold no per-turn transcripts;
I looked: journal schema, runner logs = HTTP lines only, gates = probe calls
only). The token accounting above is consistent with pure tool-call turns
(little or nothing to discard), and even if narration existed it would be
mid-investigation chatter, not the node's deliverable. So: no evidence the
harness destroyed a *produced answer*; strong evidence the empty output is a
**harness-design artefact (pre-registered cap semantics)** for M1 and genuine
model behaviour for M2. "Bug" is the wrong word for both; "model returned
empty content" is the wrong story for M1. Any fix is a **design change**, not
a bug fix, and must be treated as such (pre-registration, new harness version).

### C2 — "model × node interaction, not an architectural property" : WEAKENED

The interaction is real and verified: granite4.1 and deepseek-r1 are 0%
everywhere; muse fails at `data`, qwen@think-budget at `policy_risk`, lfm at
both. But the "not architectural" half overreaches: the same muse model with
the same tools and the same cap **never once produced an empty output via cap
in 1150 single-arm runs** (max 7 tool calls; 5 runs reached 8 agent messages,
all emitted text). The decomposition manufactures the trap: the orchestrator
writes an exhaustive ~2k-char plan, the `data` node is the only node with a
multi-tool loop and is ordered to satisfy the plan before summarising, and the
per-node cap cuts it off. Architecture supplies the hazard site (`data` = only
cap-loopable node; `policy_risk` = rulebook + deliberation load = budget
hazard); the model determines whether it is hit. Correct statement: a
**model × architecture interaction with decomposition as a necessary
co-factor** — granite proves it is not universal, muse-single proves it is not
model-alone.

### C3 — detectability asymmetry : SURVIVES, with three corrections

Verified core: all 64 single-arm empties → `malformed`; all 536 MAS runs with
an empty node have `error: null`; of empty-*upstream*-node runs, 100% with a
non-empty reporting node yield a parseable decision (muse think-off: 226/226
decisions, 224 "investigate"). What would have refuted it: any non-malformed
empty single run, or any journalled error on an empty-node MAS run — none exist.

Corrections the asymmetry claim must carry:
1. **Not the "same underlying behaviour."** Muse think-off: 1/1150 empty in
   single vs 226/1150 node-empties in MAS. The MAS arm mostly *creates* the
   failure (M1); it is not one behaviour scored two ways.
2. **Reporting-node empties ARE caught**: qwen's 8 empty-reporting runs score
   `malformed`. The blind spot covers the three upstream nodes only.
3. **The MAS decisions are degraded, not silently corrupted.** Downstream
   nodes do not fabricate evidence (fabrication regex hits were false
   positives; manual inspection shows e.g. "Data findings provided in the case
   file: none"): `policy_risk` explicitly flags the missing evidence and
   applies the rulebook's insufficient-evidence rule, herding to
   "investigate" (muse: 224/226; @think: 191/191). Invisible to outcome
   scoring, but self-documented in the journalled node text.

### C4 — "severed channel is not the cause of MAS underperforming" : SURVIVES

Reproduced exactly from journals: muse think-off t07-varied single pass^1 =
0.392 (n=750); MAS-all 0.264; MAS-intact 0.284 (n=610); MAS-severed 0.179
(n=140). granite4.1: single 0.299 vs MAS 0.289 with zero empties anywhere.
The commissioned attack failed: intact `data` outputs are substantive —
min length 463 chars, median 1147, **zero** whitespace-only or <80-char
outputs, ~5/610 with refusal-ish phrasing (mostly false positives on
inspection). Only caveat found: 13/610 "intact" runs made zero data-tool calls
yet emitted an evidence summary (fabrication risk, 2%, too small to move the
split). Intact MAS still trails single by 0.108; the severed channel accounts
for roughly 2 points of a 13-point deficit. What would have refuted it: a
large useless-intact fraction or intact≈single — neither exists.

### C5 — "Fix A (keep last non-empty text) resolves the majority" : REFUTED

Offline test on the real loop (`adv_emptynode_wiremock`):

| scenario | current `run_tool_loop` | Fix A |
|---|---|---|
| S1 prose turn → empty final answer turn | `""` | recovers the prose |
| S2 cap-hit, narration on earlier turns | `""` | recovers **mid-investigation narration** (not an evidence summary) |
| S3 single empty answer turn (M2, qwen `policy_risk` 92/94) | `""` | `""` — recovers nothing |
| S4 cap-hit, pure tool-call turns | `""` | `""` — recovers nothing |

Mapping to the 532 observed node-empties: ~118 are M2/S3 (nothing to keep);
~417 are M1 where recovery is (a) contingent on intermediate narration that
cannot be verified from disk and is token-accounting-implausible, and (b) at
best a partial narration, never the node's deliverable. "Resolves the
majority" is unsupported in the best case and false in the likely case.

Side effect that independently disqualifies Fix A as a casual patch:
`run_tool_loop` is shared by BOTH arms and all sweeps. 58/63 single-arm
empty→`malformed` runs in the three affected sweeps are multi-turn with tool
calls; Fix A could flip sealed `malformed` outcomes into scored decisions,
retroactively rewriting sealed results.

## Open questions

- **Why `data` for muse, `policy_risk` for qwen:** the node's tool set and
  prompt select which mechanism is reachable. `data` is the only node with 3
  tools and an order to satisfy an upstream plan → only place M1 (cap-loop)
  can occur; muse follows the exhaustive plan literally and re-screens
  entities until the cap. `policy_risk` carries the full RULEBOOK and the
  heaviest deliberation → the place M2 (thinking-budget exhaustion) lands for
  think=True qwen/lfm; its single tool goes uncalled (92/94 zero calls).
  Orchestrator/reporting have no tools: one-turn loops, M1 impossible; their
  only failure mode is M2 (qwen reporting 0.7%).
- **Downstream behaviour on empty data:** no hallucinated evidence found;
  explicit missing-data statements plus rulebook herding to "investigate"
  (>99% of muse severed runs). ~37-53/run-set also use "no evidence/missing
  data" phrasing verbatim.
- **Correlates:** muse M1 empties anti-correlate with temperature (T=0: 25% →
  T=1.0: 10%; t0-fixed worst at 26%) — deterministic loop-trap. qwen M2
  empties correlate positively with temperature (T=0: 5% → T=1.0: 14%) and
  with completion tokens (~2×). No repeat-index drift; at t0-fixed, 4 cases
  are all-empty across repeats and 15 mixed (nondeterminism despite fixed
  seed). Signature stats: M1 = exactly-8 node tool calls; M2 = zero tool
  calls + token blowout.

## Recommendation

Do NOT apply Fix A. It mistargets both mechanisms, cannot be validated
against the journals (no transcripts), and silently alters sealed single-arm
`malformed` outcomes because the loop is shared code. If the owner wants the
failure addressed rather than reported: (1) journal per-node per-turn
transcripts (or at least per-node `agent_messages`/tokens and a
`cap_terminated` flag) in harness v3 so this question is answerable next time;
(2) for M1, the design-level option is one final no-tools answer turn after
the cap — a pre-registered semantics change, confounding against all sealed
sweeps and reportable as such; (3) for M2 the empty content is the model's
genuine (budget-exhausted) behaviour — score it, don't paper over it: count
empty upstream nodes as a first-class outcome so the MAS arm loses its
detectability advantage honestly. For the dissertation, the correct move is to
report the mechanism split and the detectability asymmetry as findings, not to
change the harness mid-programme.
