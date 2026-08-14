# Adversarial verdict — "the harness is correct and blameless"

Date: 2026-08-14. Adversarial re-verification of the tool-channel conclusions in
`docs/TOOL-CHANNEL-CENSUS.md` and `results-deepseek-r1-14b-thinking/audit-independent.md`.
Method: offline only (zero LLM/GPU/ollama-CLI, no sweep ports). Three new probes
exercise the REAL harness code paths with a mocked Ollama client:

- `backend/experiments/analysis/adv_probe_wire.py` — captures the exact
  `AsyncClient.chat(**kwargs)` payload the sweep code emits, per model config and
  per MAS node.
- `backend/experiments/analysis/adv_probe_parsing.py` — feeds synthetic
  responses (every tool-call surface deepseek/lfm2.5/muse could emit) through the
  real `ChatOllama` parse -> `run_tool_loop` -> journal-shape path.
- `backend/experiments/analysis/adv_probe_c3_nodes.py` — per-node forensics on
  the three node-death pockets + independent deepseek recount with fresh regexes.

Plus physical inspection of the served template blobs under
`/usr/share/ollama/.ollama/models/` and the GGUF KV metadata (parsed directly).

Code provenance: both thinking-on manifests pin `git_sha 41de0892…`; the entire
request-construction path (`single.py`, `mas.py`, `adapter.py`, functional part of
`models.py`) is byte-identical between that SHA and HEAD, so the probed code is
the code that ran the sweeps.

---

## C1 — deepseek's 0/2,300 tool calls are template-caused, not harness-caused

**VERDICT: SURVIVES** (every link now physically verified; two corrections to the
supporting story).

Attack: found the only code path that could skip tools for a thinking-track model
— there is none. `run_tool_loop` (`backend/app/agents/single.py:88`) binds tools
unconditionally; `make_model_factory` (`harness/models.py`) varies only
model/think/seed/temperature/num_ctx/num_predict; no branch anywhere keys on
model name or `think`. The wire probe then *demonstrated* it: with the
`deepseek-r1:14b@think` config (think=True), the captured request carries all
four tools, byte-identical (sha256 `c735791b…`) to the qwen2.5 (think=None) and
muse (think=False) requests.

Independent cross-checks that the sweep itself behaved that way:

- `lfm2.5:8b@think` ran the **same git SHA, same Ollama 0.32.9, same think=True**
  and journalled 9,316 native tool calls — the request path provably delivers
  tools on the thinking track.
- `results-muse-glimmer-30b/journal-single.jsonl` contains a server-side error
  `"ResponseError: parse Glimmer call to calculate_risk_score: unterminated ATEM
  parameter"` — the server can only know that tool name if the request's tools
  array reached it.
- Physical template evidence: the registry template layer blob
  (`sha256-c5ad996b…`, 556 B Go) renders System/Messages/Thinking only — **no
  `.Tools` anywhere**. Verified by reading the blob, not trusting the census.
- Model-side evidence of total tool blindness: fresh-regex recount over all
  2,300 runs (raw_output + all 9,200 node outputs) finds **zero** occurrences of
  any tool name, any call syntax, and even zero generic "I need a tool/database"
  phrasings. Single-arm completion_tokens median 568, ceiling hits 0 — the model
  answered naturally, it was never told tools exist.

Corrections to the prior story (they weaken the *presentation*, not the claim):

1. **The server declared deepseek tools-capable.** The sweep manifest records
   `/api/show` capabilities `['tools', 'thinking', 'completion']` — because the
   GGUF-embedded Jinja template (parsed from the blob's KV metadata) contains
   tool-*call* markers (`<｜tool▁calls▁begin｜>` etc.), though **no tool-definition
   injection** (no `{% for tool in tools %}`). So Ollama accepted tool-bearing
   requests without error and the winning template layer silently dropped them.
   A capability check would have said "fine". This is why 2,300 runs show zero
   errors *and* zero tools — and it means the manifest's own capability record
   was actively misleading as a pre-flight signal.
2. **The gate battery never tested the tool channel.** `mini_gates._chat` sends
   no `tools` key at all (verified in `harness/gates.py:42-64`); the 2×2 pilot
   runs the real runner but records no tool-call counts and asserts nothing
   about them. The gate 8/8 PASS is therefore *zero evidence* either way about
   tools — deepseek passed its gate while completely tool-blind.

What would have refuted C1: a captured request without `tools`, a think- or
model-conditional in the bind path, or tool-attempt syntax in the journals that
strict parsing ignored. Looked for all three; none exists.

## C2 — tool list passed identically for both arms, all models, both think values

**VERDICT: SURVIVES** (now proven empirically, not just by code reading).

`adv_probe_wire.py` verdicts, from real `ArmAdapter -> agent -> ChatOllama`
execution against the mocked client:

- [V1] Single-arm tool payload sha256 identical across
  deepseek@think / qwen2.5 (None) / muse (False): `c735791b1312…` — byte-level.
- [V3] MAS node partitions match `config.MAS_TOOL_PARTITION` exactly for both
  lfm2.5@think and deepseek@think: orchestrator `[]`, data
  `[search_precedents, get_customer_profile, check_sanctions_list]`
  (sha `98f84bac…`), policy_risk `[calculate_risk_score]` (sha `d0acbde4…`),
  reporting `[]`.
- [V4] The policy_risk node's request **does** contain `calculate_risk_score` —
  the 470-run lfm2.5 pocket is not a tool-injection bug.
- `think` reaches the wire exactly as configured (True/None/False) with no
  interaction with the tools field.

Caveat (by design, not a bug): nodes with an empty partition send **no** `tools`
key at all (bind skipped), so orchestrator/reporting requests differ from
tool-bearing ones in more than the tool list. Irrelevant to the claims but worth
knowing when comparing node behaviour.

## C3 — node-death pockets are "model declined", not truncation/starvation

**VERDICT: SPLIT — REFUTED for qwen3.5:9b@think-budget's majority; SURVIVES for
lfm2.5 and muse. Plus the census's MAS truncation classifier is demonstrably
broken.**

Discriminator: a policy node starved by `num_predict` mid-deliberation emits
EMPTY content (the documented qwen3.5@think gate-failure signature); a node that
declined emits a substantive assessment without calling the tool.
`adv_probe_c3_nodes.py`:

| pocket | dead (non-error) | EMPTY policy text | dead vs alive completion tokens (mean) | reading |
|---|---|---|---|---|
| lfm2.5@think mas | 470 | **18 (3.8%)** | 4,306 vs 5,208 (dead runs *cheaper*) | decline+fabricate |
| qwen3.5@think-budget mas | 156 (+11 error) | **92 (59%)** | 12,021 vs 7,231 (dead runs ~1.7× *dearer*); empty-text subset 13,949 | **starvation** |
| muse-glimmer mas (partial) | 38 | **0** | 3,076 vs 3,820 | explicit decline |

- **qwen3.5:9b@think-budget — REFUTED for 92/167 (55%).** Those runs show the
  exact starvation signature the team pre-registered at gate time for
  `num_predict=2048` (`CHANGELOG 2026-08-12`): empty `node_outputs['policy_risk']`
  with a ~+6,700-token excess ≈ one maxed-out 8,192-token deliberation that was
  cut before emitting either a tool call or text. The budget raise to 8,192 did
  not eliminate the mechanism — it persists in 8% of all MAS runs. Calling this
  pocket "the model declined to call" is wrong; it never got to choose. (A
  further 11 are journalled server errors: `ResponseError: EOF` ×10 and one
  server-side tool-XML parse failure.) Only ~64/167 are genuine declines.
- **lfm2.5@think — SURVIVES.** 452/470 dead runs carry substantive policy text
  (median 911 chars), 242 assert a fabricated numeric risk score, deaths
  reproduce deterministically at T=0 (19 of 20 affected cases dead in all 5
  repeats), and dead runs consume *fewer* tokens than alive ones — the opposite
  of a starvation profile. The 18 empty-text runs (3.8%) are unresolvable
  starvation candidates; flag them, they don't move the verdict.
- **muse-glimmer — SURVIVES** (and is the most interesting behaviourally): all
  38 dead policy outputs are articulate refusals that *name the tool* and argue
  the factors dictionary would have to be invented ("inventing them would
  violate Evidence rule 2"). Zero unparsed-call markers. This is deliberate,
  evidence-gated tool abstention — model behaviour, on the thinking-OFF track.

**The broken classifier.** The census root-cause table (§3) tests truncation as
run-level `completion_tokens >= num_predict − 8`. For MAS, `completion_tokens`
is SUMMED across ≥4 model calls, so the test is meaningless against a per-call
cap: it labels **1,048** deepseek MAS runs "truncated at 2048" — exactly
reproduced here as the count of runs whose 4-node *total* ≥ 2,040, while
`agent_messages=4` in all 1,150 runs, median per-node output ≈ 615 tokens, max
run total 4,217 < 2×2,048 spread over 4 calls: **zero** deepseek MAS runs show
any credible per-call truncation. The same test passes on 1,149/1,150 of ALL
lfm2.5 MAS runs, so its "42/43 zero-tool runs = truncation" is non-evidence.
Root-cause sub-attributions for MAS pockets in the census should be re-derived;
the journal's lack of per-node token accounting makes per-call truncation
formally undecidable from journals alone (my empty-text discriminator is the
closest available proxy).

## C4 — journal `tool_calls` faithfully records attempts; strict v2 dropped nothing

**VERDICT: SURVIVES** for the sweeps as run (the drop windows exist but are
provably empty here).

`adv_probe_parsing.py` through the real parse path (think=True config):

| surface | recorded? |
|---|---|
| native `message.tool_calls`, dict args | yes |
| native, args as JSON string (ollama #6155 shape) | yes (parsed) |
| native, in a non-final stream chunk | yes |
| native, UNKNOWN tool name | **yes** — recorded and answered `error: unknown tool` |
| native, malformed non-JSON args | **not recorded — but LOUD**: `OutputParserException` propagates → journalled in `error` as malformed, never silent |
| tool call as raw JSON in content | not recorded; text survives verbatim into `raw_output`/`node_outputs` |
| tool call as XML in content | not recorded; text survives |
| truncation (`done_reason: length`, empty content) | no calls, empty output |

So "strict v2" rejects exactly two things: (a) content-channel call syntax —
which is preserved in journalled text, where the census/audit regex hunts found
**0 instances in deepseek's 2,300 runs** (reconfirmed with fresh patterns,
including soft "I need a tool" phrasings: 0) and ~1 in lfm2.5; and (b)
malformed-arg native calls — which journal as visible errors, and deepseek has
**0 errors in 2,300 runs**. The lfm2.5 hallucinated-tool runs (44) reconcile
cleanly: they arrived on the native channel (server-parsed), and strict v2
records native calls regardless of name — no contradiction with strictness.
Nothing existed for the parser to eat. The harness-v3 lenient branch would have
changed lfm2.5/muse margins, not deepseek's zero.

What would have refuted C4: a synthetic native-channel call the pipeline
silently dropped, or attempted-call syntax in deepseek journals. Neither exists.

---

## Overall

The prior analysis's two load-bearing conclusions hold under attack: the
deepseek zero is template-caused (C1) and the harness passes tools uniformly
(C2), and journalling is faithful (C4). "Correct and blameless" is still too
generous in three places:

1. **The qwen3.5@think-budget policy-node pocket is majority num_predict
   starvation, not model refusal** — a locked-constant interaction the team had
   already named at 2048 and wrongly considered solved at 8192.
2. **The census's MAS truncation attributions are artifacts of a per-call test
   applied to per-run sums** (the "1,048 truncated" deepseek MAS figure exactly
   reproduces the bug).
3. **Blind spots, not bugs**: no gate ever asserted a tool call; the journal has
   no per-node token accounting; and the manifest's `/api/show` capability
   record says "tools" for a model whose serving template cannot render them.
   All three let a fully tool-dead 12-hour sweep pass every check that existed.
