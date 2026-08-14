# Tool-Call Channel Census — all sweeps, all Ollama versions

Date: 2026-08-14. Scope: every `backend/experiments/results*/` dir with journals
(12 dirs, 26,979 journalled runs read). Read-only audit; no LLM/GPU/ollama-CLI use.
Scripts: `backend/experiments/analysis/eval_toolchannel_census.py` and
`eval_toolchannel_deepdive.py` (run from `backend/` with `./.venv/bin/python`).
`results-muse-glimmer-30b` was **in-flight** at read time (single 1150/1150,
mas 529/1150) — all its numbers are partial.

Available tool set (`harness/dfah_tools.py`): `search_precedents`,
`get_customer_profile`, `check_sanctions_list`, `calculate_risk_score`.
MAS partition (`config.MAS_TOOL_PARTITION`): **data** node owns the three lookup
tools, **policy_risk** owns `calculate_risk_score`, orchestrator/reporting own
none — so tool *name* identifies the calling *node* exactly, even in journals
without `node_outputs`.

---

## 1. Verdict

**The tool-channel failure is a spectrum, not a deepseek-only binary.**

- **deepseek-r1:14b is the only *total, infrastructure-caused* failure**
  (2,300/2,300 runs, both arms, zero calls): its registry template layer is a
  Go template with no `.Tools` block, so tool definitions were never rendered.
- **Every thinking-on sweep has a *partial, behavioural* version of it**, and
  the deepseek "node fabricates instead of calling" pattern recurs in miniature
  in every one of them — most severely in `lfm2.5-8b-thinking` MAS, where the
  **policy_risk node is silently tool-dead in 470/1,150 runs (40.9%)** while
  the arm-level calls/run mean (5.34) looks healthy.
- **gemma3:27b is a loaded gun**: its template layer also has no `.Tools`
  (verified in the blob), and `results-gemma3-27b/` has a manifest but no
  journals yet. Run as-is it will reproduce the deepseek failure exactly.
  Same-family warning applies to nothing else: all other pulled models render
  tools (see §4).
- No gate asserts tool calls anywhere, which is why all of this was silent.

---

## 2. Census table (sweep × arm)

Calls/run is min/median/max (mean). "Node-dead" = MAS runs whose policy_risk
node made zero `calculate_risk_score` calls (incl. zero-tool runs) / whose data
node made zero lookup calls.

| Sweep | Model @ Ollama, think | Arm | Runs | Zero-tool | Calls/run | Node-dead (pol / data) | Verdict |
|---|---|---|---|---|---|---|---|
| results | qwen3.5:9b @0.31.1, off | single | 1150 | 0 | 1/4/6 (3.71) | — | healthy |
| results | 〃 | mas | 1150 | 5 (0.4%) | 0/5/8 (5.20) | 6 / 12 | healthy, tiny t07 pocket |
| results-deepseek-r1-14b-thinking | deepseek-r1:14b @0.32.9, on | single | 1150 | **1150 (100%)** | 0/0/0 (0) | — | **DEAD (template)** |
| results-deepseek-r1-14b-thinking | 〃 | mas | 1150 | **1150 (100%)** | 0/0/0 (0) | 1150 / 1150 | **DEAD (template)** |
| results-gemma4 | gemma4 @0.31.1, off | single | 1150 | 7 (0.6%) | 0/2/5 (2.05) | — | healthy, small pocket |
| results-gemma4 | 〃 | mas | 1150 | 0 | 2/6/9 (6.11) | 3 / 0 | healthy |
| results-granite4.1-8b | granite4.1:8b @0.32.9, off | single | 1150 | 0 | 1/4/6 (3.58) | — | **fully healthy** |
| results-granite4.1-8b | 〃 | mas | 1150 | 0 | 1/5/9 (5.35) | 0 / 3 | **fully healthy** |
| results-lfm2.5-8b-thinking | lfm2.5:8b @0.32.9, **on** | single | 1150 | **97 (8.4%)** | 0/3/6 (2.77) | — | degraded; + 44 runs hallucinate tool names |
| results-lfm2.5-8b-thinking | 〃 | mas | 1150 | 43 (3.7%) | 0/6/11 (5.34) | **470 (40.9%) / 93 (8.1%)** | **worst partial failure** |
| results-muse-glimmer-30b (PARTIAL) | muse-glimmer:30b @0.32.9, off | single | 1150 | 1 | 0/4/7 (4.09) | — | healthy so far |
| results-muse-glimmer-30b (PARTIAL) | 〃 | mas | 529 | 1 | 0/8/11 (7.50) | 37 (7.0%) / 2 | policy-node pocket, watch |
| results-qwen2.5-14b | qwen2.5:14b-instruct @0.31.1, off | single | 1150 | 0 | 1/4/12 (3.69) | — | healthy |
| results-qwen2.5-14b | 〃 | mas | 1150 | 1 | 0/6/22 (6.36) | 9 / 2 | healthy |
| results-qwen2.5-14b-ollama0326 | 〃 @0.32.6 | single | 1150 | 0 | 1/4/12 (3.69) | — | healthy |
| results-qwen2.5-14b-ollama0326 | 〃 @0.32.6 | mas | 1150 | 1 | 0/6/22 (6.36) | 9 / 2 | healthy |
| results-qwen2.5-7b | qwen2.5:7b-instruct @0.31.1, off | single | 1150 | 0 | 2/3/6 (3.03) | — | healthy |
| results-qwen2.5-7b | 〃 | mas | 1150 | 0 | 4/7/**671** (11.62) | 1 / 0 | healthy but **looping** (29 runs >50 calls) |
| results-qwen2.5-7b-ollama0326 | 〃 @0.32.6 | single | 1150 | 0 | 2/3/6 (3.04) | — | healthy |
| results-qwen2.5-7b-ollama0326 | 〃 @0.32.6 | mas | 1150 | 0 | 4/7/438 (11.95) | 0 / 0 | healthy but looping |
| results-qwen3.5-9b-ollama0326 | qwen3.5:9b @0.32.6, off | single | 1150 | 0 | 1/4/8 (3.74) | — | healthy |
| results-qwen3.5-9b-ollama0326 | 〃 | mas | 1150 | 4 (0.3%) | 0/5/8 (5.20) | 4 / 11 | healthy, same t07 pocket as 0.31.1 |
| results-qwen3.5-9b-thinking-budget | qwen3.5:9b @0.32.9, **on**, num_predict 8192 | single | 1150 | 0 | 1/4/10 (4.65) | — | healthy count-wise; 58 runs call decision verbs as tools |
| results-qwen3.5-9b-thinking-budget | 〃 | mas | 1150 | 26 (2.3%) | 0/5/14 (5.01) | **167 (14.5%)** / 72 (6.3%) | degraded (thinking track) |

Distinct tool names: every arm uses all four expected tools except deepseek
(none). Unexpected/hallucinated names appear only in the two thinking sweeps
(§5.3). No sweep is missing a specific tool name at the arm level other than
deepseek.

---

## 3. Root cause of every zero-tool pocket

Classification order: journal `error` → empty output → truncation
(`completion_tokens ≥ num_predict−8`; 2048 default, 8192 for thinking-budget) →
attempted-but-unparsed syntax → refusal → early final answer.

| Pocket | n | Root cause |
|---|---|---|
| deepseek single | 1150 | **No tools in prompt** (template). Model simply answers: 1,149 early-final-answer, 1 no-decision. Zero attempted-tool-syntax anywhere — it never knew tools existed. |
| deepseek mas | 1150 | Same template root cause; proximately 1,048 runs truncated at num_predict 2048 (thinking burns the budget), 101 early final answers. |
| lfm2.5-thinking single | 97 | 89 early-final-answer (79 of 97 at t07-varied; spread over 41 cases — temperature-driven, not case-specific), 5 empty raw_output, 1 truncation, 1 unparsed JSON `"name"` attempt, 1 no-decision. |
| lfm2.5-thinking mas | 43 | **42 truncation at 2048** (thinking + 4-node pipeline exhausts the cap), 1 early final. Spread over 31 cases; 27 at t07, but 10 at t0-fixed (deterministic repeats of the same truncating cases). |
| qwen3.5-thinking-budget mas | 26 | 15 early final answer, **11 harness errors** (`ResponseError: EOF` ×10; ×1 `expected element type <function> but have <parameter>` — a server-side parse failure of malformed tool-call XML). 25/26 at t07-varied. |
| results (qwen3.5 @0.31.1) mas | 5 | 3 early final, 2 refusal-ish; all t07-varied, one each on TXN-2025-009/014/016/017/028. |
| qwen3.5-9b-ollama0326 mas | 4 | 4 early final, all t07, on TXN-2025-009/014/017/028 — **the same cases as 0.31.1**: a case × temperature behaviour, stable across Ollama versions. |
| gemma4 single | 7 | 6 early final + 1 refusal (6 t07, 1 t0-fixed); 5 cases. |
| qwen2.5-14b mas (both versions) | 1+1 | The identical run (`mas:…:t07-varied`) early-finals in both version dirs (byte-identical output, see §6). |
| muse-glimmer single | 1 | `ResponseError … parse Glimmer call to calculate_risk_score: unterminated ATEM parameter "factors" (500)` — an **attempted call that failed server-side parsing** in the model's native call format. |
| muse-glimmer mas | 1 | Truncation at 2048 (t07). |

Pattern: outside deepseek, zero-tool runs are overwhelmingly **t07-varied**
(temperature effect), concentrated in the **thinking-on track**, and (for
qwen3.5) partially **case-specific and version-stable**. Nothing suggests a
second rendering-level failure in any journalled sweep.

---

## 4. The NO-TEMPLATE explanation (how each model gets tool rendering)

Verified by direct manifest + blob inspection under
`/usr/share/ollama/.ollama/models/` (no `ollama` CLI). Ollama resolves the chat
template in precedence order: **(1)** registry `template` layer (Go template) →
**(2)** GGUF-embedded `tokenizer.chat_template` (Jinja) / Ollama's compiled-in
renderer keyed on `general.architecture`. A Go template without a `.Tools`
block **silently drops** the tools array — no error, no warning.

| Model | Template layer | GGUF `tokenizer.chat_template` | GGUF arch | Tool rendering path |
|---|---|---|---|---|
| deepseek-r1:14b | **yes, 556 B Go, NO `.Tools`** | present (2,237 B, also lacks tool-definition injection) | qwen2 | Layer wins → **tools silently dropped** |
| gemma3:27b | **yes, 358 B Go, NO `.Tools`** | — | — | **Would drop tools — sweep not yet run, fix before running** |
| qwen3.5:9b | none | **present, 7,756 B Jinja with `tools`/`tool_call`/`tool_response`** | qwen35 | Embedded Jinja renders tools ✔ (journals confirm) |
| muse-glimmer:30b | none | **present, 7,167 B Jinja with `tool_defs`/`tool_call`/…** | muse-glimmer | Embedded Jinja ✔ |
| gemma4 (both tags) | none | **absent** (GGUF KV parsed: no such key) | gemma4 | **Ollama 0.31/0.32 built-in renderer** for the `gemma4` architecture ✔ |
| lfm2.5:8b | none | **absent** | lfm2moe | Built-in renderer for `lfm2moe` ✔ |
| gpt-oss, granite4.1, granite4, llama3.1, mistral-nemo, mistral-small3.2, qwen2.5 (7b, 14b) | yes, with `.Tools` | n/a | — | Registry Go template ✔ |

So "NO-TEMPLATE in the manifest" was never the risk marker: those four models
provably call tools in their journals because rendering comes from the GGUF
Jinja or Ollama's built-in per-architecture renderer. The risk marker is the
opposite case — **a template layer that exists but lacks `.Tools`**
(deepseek-r1:14b, gemma3:27b), because the layer takes precedence and drops
tools without any error.

---

## 5. MAS node-level findings (the deepseek pattern in miniature)

Node attribution is exact via the tool partition (§ top). "Silently dead" =
run has tool calls (arm looks alive) but one node made none.

### 5.1 policy_risk node death

| Sweep (mas) | policy-node dead | of runs | at t0-fixed | Asserts numeric risk score anyway |
|---|---|---|---|---|
| lfm2.5-8b-thinking | **470** | 40.9% | 76/250 | **243/470 (51.7%)** |
| qwen3.5-9b-thinking-budget | **167** | 14.5% | 16/250 | 27/167 |
| muse-glimmer-30b (partial) | 37 | 7.0% | 17/250 | 3/37 |
| qwen2.5-14b (each version) | 9 | 0.8% | 0 | 0 |
| results / qwen3.5-0326 | 6 / 4 | ≤0.5% | 0 | 0 / 1 |
| gemma4 | 3 | 0.3% | 1 | 0 |
| qwen2.5-7b / 7b-0326 | 1 / 0 | ~0% | 0 | 0 |
| granite4.1-8b | **0** | 0% | 0 | — |

In lfm2.5 the arm total (mean 5.34 calls/run) fully masks this: the data node
over-calls while policy_risk skips `calculate_risk_score` and **writes a
"RISK ASSESSMENT" containing a fabricated numeric score in half the dead runs**
(e.g. `mas:TXN-2025-003:t0-fixed:*` — identical fabrication reproduced
deterministically across repeats). This is exactly the deepseek data-node
fabrication mechanism, surviving in a sweep that passes every arm-level look.

### 5.2 data node death

lfm2.5-thinking mas: 93 runs (8.1%) with zero lookup calls, **57 of which emit a
full "EVIDENCE SUMMARY" with sanctions/KYC/history claims** (again byte-repeated
at t0-fixed, e.g. `mas:TXN-2025-007:t0-fixed:0..`). thinking-budget: 72 (2
fabricating; most instead ask for missing identifiers). All other sweeps ≤12
runs, mostly at t07.

### 5.3 Hallucinated tool names (parsed calls to nonexistent tools)

- lfm2.5-thinking **single**: 44 runs call invented tools — `investigate` (17),
  `decision_rulebook` (12), `escalate` (10), plus typo'd variants
  (`decision_rouboo`, `decision_rubook`, `decide_decision`…). Includes
  t0-fixed (`single:TXN-2025-027:t0-fixed:0–4` deterministically).
- qwen3.5-thinking-budget **single**: 58 runs call `escalate`/`investigate`/
  `dismiss`/`final_decision` as tools — the model treats the decision verb as a
  callable. `single:TXN-2025-049:t0-fixed:0–4` deterministic.
- MAS arms: one `risk_factor_scoring` (lfm2.5), one `check_sanclusions_list`
  typo (thinking-budget).
- Confined to the thinking-on track; zero occurrences elsewhere.

### 5.4 Looping (opposite pathology, qwen2.5-7b mas only)

29 runs (0.31.1) / similar (0.32.6) exceed 50 calls; max **671 calls in one run**
(`mas:PERT-001:pert-t05:4`, 224× `check_sanctions_list`). Tool channel works —
too well; flag for cost/latency reads, not health.

### 5.5 node_outputs integrity

Where `node_outputs` exists (harness-v2 journals: deepseek, granite4.1,
lfm2.5-thinking, muse-glimmer, thinking-budget) all four keys
(orchestrator/data/policy_risk/reporting) are present; no empty node strings in
healthy sweeps.

---

## 6. Cross-version comparison (0.31.1 vs 0.32.6)

Same model digest, genuinely separate executions (distinct timestamps and wall
clocks) in every pair.

- **qwen2.5-14b**: tool-call sequences identical in **1150/1150** runs both
  arms; raw outputs byte-identical in 1147/1150 single, 1150/1150 mas — even at
  t0.7 (seeds are version-invariant by design). **Zero version effect.**
- **qwen2.5-7b**: tool sequences identical 1083/1150 single, 417/1150 mas —
  the divergence is loop-length jitter at sampled temperatures, not health
  (zero-tool 0/0 both, mean 11.62 vs 11.95, same name mix).
- **qwen3.5-9b** (`results` @0.31.1 vs `-ollama0326`): tool sequences identical
  969/1150 single, 1125/1150 mas; the zero-tool pocket lands on the **same four
  cases** (TXN-2025-009/014/017/028, t07) under both versions.
- 0.32.9 appears only in single-version sweeps (granite4.1 healthy; the
  thinking track's problems are think-flag-correlated, not version-correlated —
  qwen3.5:9b is clean on 0.31.1/0.32.6 thinking-off and degraded only in the
  0.32.9 **thinking-on** budget sweep).

**Conclusion: no Ollama-version effect on the tool channel.**

---

## 7. Fabrication rates in zero-tool runs

Regex screen (sanctions verdicts, numeric risk scores, KYC/relationship
history, precedent CASE-ids) over raw_output + node_outputs, full count (not a
sample):

| Sweep, arm | Asserting / zero-tool | Rate |
|---|---|---|
| deepseek single | 940 / 1150 | 81.7% |
| deepseek mas | 1138 / 1150 | 99.0% |
| lfm2.5-thinking single | 50 / 97 | 52% |
| lfm2.5-thinking mas | 41 / 43 | 95% |
| thinking-budget mas | 15 / 26 | 58% |
| results mas | 5 / 5 | 100% |
| qwen3.5-0326 mas | 3 / 4 | 75% |
| gemma4 single | 3 / 7 | 43% |
| qwen2.5-14b mas (each) | 1 / 1 | — |
| muse mas (partial) | 1 / 1 | — |

**Outside deepseek: 120/186 zero-tool runs (64.5%) assert at least one
tool-derived fact they never obtained.** Add the node-level fabrication of §5
(lfm2.5: 243 policy + 57 data runs) and the corpus-wide count of runs asserting
unearned facts is dominated by lfm2.5-8b-thinking, not deepseek's neighbours.

---

## 8. Healthy list & actions

**Fully healthy tool channel (both arms):**
- `results-granite4.1-8b` — the only sweep with zero findings of any kind.
- `results-qwen2.5-14b` and `results-qwen2.5-14b-ollama0326` (1 benign t07 run each).
- `results-qwen2.5-7b` and `results-qwen2.5-7b-ollama0326` (channel healthy; looping is a separate cost pathology).
- `results` and `results-qwen3.5-9b-ollama0326` (≤5-run, case-specific t07 pocket, fully explained).
- `results-gemma4` (7-run single pocket, explained).

**Degraded (quantified partial failures):** `results-lfm2.5-8b-thinking`
(worst: 40.9% policy-node death + fabrication), `results-qwen3.5-9b-thinking-budget`
(14.5% policy-node death, hallucinated decision-tools, 11 server errors),
`results-muse-glimmer-30b` (partial data: 7% policy-node death so far).

**Dead:** `results-deepseek-r1-14b-thinking` (template; exclude or re-run with a
`.Tools` template).

**Actions:** (1) do NOT start `results-gemma3-27b` until its template gets a
`.Tools` block; (2) add a gate: per-arm minimum tool-call count > 0 AND per-node
(via tool-name partition) non-zero rates; (3) treat thinking-track MAS results
as contaminated by node-level fabrication until filtered.

---

## 9. Correction (2026-08-14, adversarial follow-up)

Source: `docs/ADVERSARIAL-HARNESS-VERDICT.md` (probes
`adv_probe_c3_nodes.py` et al.). Three corrections to this census:

1. **MAS truncation sub-attributions in §3 are RETRACTED — the classifier was
   broken.** §3 tested truncation as run-level `completion_tokens ≥ num_predict−8`,
   but for MAS runs `completion_tokens` is *summed across ≥4 model calls*, so the
   test is meaningless against a per-call cap. The "1,048 deepseek MAS runs
   truncated at 2048" figure is an artifact of exactly this bug: all 1,150 deepseek
   MAS runs have `agent_messages=4`, median per-node output ≈615 tokens, max run
   total 4,217 — **zero** credible per-call truncations. Likewise "42/43 lfm2.5 MAS
   zero-tool runs = truncation" is non-evidence (the same test fires on 1,149/1,150
   of *all* lfm2.5 MAS runs). Per-call truncation is formally undecidable from the
   journals (no per-node token accounting); the closest available proxy is the
   empty-policy-text discriminator in the adversarial verdict's §C3. Single-arm
   truncation attributions (per-call = per-run there) are unaffected.

2. **qwen3.5:9b@think-budget policy-node deaths reclassified.** The §5.1 reading of
   the 167 dead policy nodes as "the model declined to call" is wrong for the
   majority: **92/167 (55%) are `num_predict` starvation at 8192** — empty
   `node_outputs['policy_risk']` with a ~+6,700-token excess, i.e. a maxed-out
   deliberation cut off *before* the node could emit either a tool call or text
   (the same mechanism pre-registered at 2048 and wrongly considered solved by the
   budget raise); **11 are journalled server errors** (`ResponseError: EOF` ×10,
   one server-side tool-XML parse failure); only **~64 are genuine declines**.

3. **The lfm2.5 and muse pockets stand as model behaviour.** lfm2.5@think MAS: 452
   of 470 dead policy nodes (96%) emit substantive assessments without calling the
   tool — 242 asserting a fabricated numeric risk score — reproduced
   deterministically at T=0, with dead runs *cheaper* than alive ones (the opposite
   of a starvation profile). muse-glimmer MAS (partial): all 38 dead policy outputs
   are articulate refusals that name `calculate_risk_score` and argue the factors
   would have to be invented — deliberate, evidence-gated tool abstention on the
   thinking-off track. These attributions are confirmed, not retracted.
