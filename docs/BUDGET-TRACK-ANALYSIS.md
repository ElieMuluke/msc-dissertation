# Budget-Sensitivity Track (v2b) — Full Analysis

**Status:** all six sweeps SEALED (6 × 2,300 = 13,800 v2b runs, paired against 13,800 sealed v2 runs).
**Provenance:** every number in this document is printed by
`backend/experiments/analysis/budget_track_analysis.py` (read-only over raw journals; zero LLM calls;
seed 20260821; bootstrap/permutation 20,000 iterations each, per the corpus's paired-stats convention).
This recomputation is also one more independent verification pass: it reproduces every previously
published v2b number it touches, with the exceptions listed in §13.
**Conventions** match the sealed corpus: pass^k = C(c,k)/C(n,k) against benchmark labels (agreement,
never "correctness"); malformed is an outcome category and is never excluded; DAR over unordered repeat
pairs; Krippendorff alpha nominal with cases as units; majority ties break by canonical
`config.OUTCOMES` order; entropy normalised by log2(4); constant-answer baselines 0.520 (primary) and
0.600 (perturbation); MV movement = perturbed-case MV vs same-arm base-case MV. Cap-hit proxy =
per-node tool-call count ≥ that node's turn cap (parallel tool calls in one turn can exceed the cap —
the proxy matches the sealed accounting).

---

## 0. Executive summary

The track asked one pre-registered question — *does the single-vs-pipeline difference survive when the
iteration constraint is equalised (32 vs 32 pooled), sized to role demand, and disclosed in every
agent's prompt?* — and its answer is yes on all six models. But the deep-dive shows the track's real
yield is different from, and sharper than, the headline.

**1. The headline deltas all reproduce exactly** (t07-varied pass^1, paired per-case): qwen2.5:7b
single +0.028 ns / pipeline +0.045 (p=.035); granite4.1 +0.017 ns / **+0.104 (p<.001)**; qwen3.5-off
+0.071 (p=.018) / +0.035 (p=.038); lfm2.5-think ns/ns; qwen3.5-think −0.025 ns / +0.035 ns; gemma4
**−0.135 (p=.001)** / +0.011 ns.

**2. After multiplicity correction, only two accuracy effects survive.** Holm–Bonferroni over the
pre-registered family of 12 pass^1 contrasts leaves exactly two: the granite pipeline gain (+0.104,
Holm p=.0006) and the gemma4 single-arm harm (−0.135, Holm p=.011). The qwen2.5 pipeline and both
qwen3.5-off gains are nominal-only (Holm p≥.18) and must be reported as suggestive. §4.3.6's narrative
currently leans on the nominal stars (see §13).

**3. The repeatability cost is the track's most robust result class** — and it had never been
significance-tested until now. DAR fell in 10 of 12 arms; the fall is significant in 6, and all 6
survive the full 36-test Holm correction (qwen2.5 single −0.128; granite pipeline −0.102; qwen3.5-off
single −0.112 and pipeline −0.094; lfm pipeline −0.078; qwen3.5-think single −0.066). Alpha is flat
almost everywhere; the one surviving alpha result is qwen3.5-think single (−0.106). Longer, disclosed
budgets buy little agreement-with-labels and reliably cost run-to-run agreement.

**4. Starvation was real on exactly one model, and relieving it is not what moved accuracy.** The
uniform 8-turn cap bound qwen2.5's data node in 381/1,150 pipeline runs (33.1%) → 33 (2.9%) under v2b;
granite (5→0), gemma4 (1→0) and qwen3.5-off (0→0) never meaningfully touched either ceiling. Yet
granite gained the most and gemma4 was harmed with zero cap involvement, while lfm's genuine relief
(37→0) produced nothing significant.

**5. The gemma4 mechanism (§5): the instruction turned an efficient judge into a busy checker.**
Tool calls per t07 run +69% (2.05→3.46; modal count 2→4), tokens +51%, while dismiss recall collapsed
0.456→0.208 — the dismiss-label runs account for −97 of the net −101 correct runs. gemma4 never once
verbalises the budget (0/1,150 runs in both arms, against granite's 79.7% of pipeline runs), so the
harm plausibly comes from the bundled *strategy clause* ("plan… most decisive checks first"), not the
budget number. Its single arm drifted toward the corpus's canonical pipeline pathology: dismissal
suppression with investigate/escalate herding. 29 cases got worse, 13 better; 11 cases flipped MV
right→wrong (10 of them dismiss-labelled), 4 wrong→right.

**6. Thinking models convert headroom into cost, not accuracy (§7).** qwen3.5-think: +54%/+41% tokens
(single/pipeline), tool calls +1.5/+3.2 per run, data-node cap hits **rose** 35→46 — and no significant
accuracy movement in either arm. 89–98% of the extra tokens are prompt-side: more turns mean the
context is reprocessed more times; per-node answer text actually got *shorter*. lfm2.5-think barely
changed behaviour at all (+0.3/+0.1 tool calls). "Deliberation absorbs whatever headroom it is given"
is quantitatively supported in the turn/token ledger, with n=2 thinking models.

**7. The dismissal collapse is only partially budget-remediable (§4).** Pipeline dismiss share:
granite 9.9%→22.1% (recall .18→.39 — a real recovery), lfm 12.5%→20.5%, qwen3.5-off 3.3%→7.1% (still
collapsed), qwen3.5-think 2.7%→3.3%, gemma4 0.1%→0.1% (one dismissal in 750 runs in *both* tracks).
Budget headroom does not restore a decision category the model+architecture pair has lost.

**8. T=0 determinism classes are unchanged; flip counts drift up (§8).** The three
always-byte-identical models (qwen3.5-off, lfm, qwen3.5-think singles ≈50/50) stay identical under
v2b; the cache-sensitive ones stay sensitive, with more decision-flipping groups under the longer
budget (qwen2.5 single 6→18/50; gemma4 pipeline 20→27/50). Budget regime does not change cache-state
sensitivity class; it mildly amplifies its decision-level consequences.

**9. Perturbation sensitivity did not improve (§9),** and pert-block MV accuracy *fell* for the
strongest v2 responders (gemma4 single 0.70→0.40 at pert-t0; qwen3.5-think single 0.60→0.40).

**10. Cross-track (§10): the arm ordering survives on all six models, but granite's sign crosses zero**
— from −0.009 (p=.68) to +0.077 (p=.011): an equalised, disclosed budget *created* the corpus's second
significant pipeline advantage. gemma4's monolith advantage halved (0.255→0.109) purely by harming the
single arm. The serving-stack confound on the three cross-version pairs is bounded by the corpus's pure
infra replications at |Δ| ≤ 0.025, ns (§1.2) — an order of magnitude below both surviving effects.

**Bottom line for the Analysis chapter:** after honest correction the track establishes (a) the arm
difference is not an artefact of the iteration constraint, (b) the prompt-side manipulation is an
active, model-specific intervention that can create a pipeline advantage (granite) or destroy the best
single-agent configuration in the corpus (gemma4), and (c) its reliable, universal effect is cost:
lower repeatability and more tokens. Budget size and budget disclosure remain confounded by
construction; §6 specifies the exact follow-up that separates them.

---

## 1. Data, comparators, integrity

### 1.1 Pair inventory

| pair | v2 dir | v2b dir | v2 runs s/m | v2b runs s/m | v2 ollama | v2b ollama | errors v2 | errors v2b | seeds identical |
|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | results-qwen2.5-7b | results-budget-qwen2.5-7b | 1150/1150 | 1150/1150 | 0.31.1 | 0.32.9 | 0 | 0 | YES |
| granite4.1-8b | results-granite4.1-8b | results-budget-granite4.1-8b | 1150/1150 | 1150/1150 | 0.32.9 | 0.32.9 | 0 | 0 | YES |
| qwen3.5-9b | results-qwen3.5-9b-ollama0326 | results-budget-qwen3.5-9b | 1150/1150 | 1150/1150 | 0.32.6 | 0.32.9 | 0 | 0 | YES |
| lfm2.5-8b-think | results-lfm2.5-8b-thinking | results-budget-lfm2.5-8b-thinking | 1150/1150 | 1150/1150 | 0.32.9 | 0.32.9 | 0 | 0 | YES |
| qwen3.5-9b-think | results-qwen3.5-9b-thinking-budget | results-budget-qwen3.5-9b-thinking | 1150/1150 | 1150/1150 | 0.32.9 | 0.32.9 | 11 | 8 | YES |
| gemma4 | results-gemma4 | results-budget-gemma4 | 1150/1150 | 1150/1150 | 0.32.6 | 0.32.9 | 0 | 0 | YES |
- qwen2.5-7b: v2 on Ollama 0.31.1 / harness v1 (no node_outputs); v2b on 0.32.9
- granite4.1-8b: both 0.32.9 / harness v2 — clean
- qwen3.5-9b: v2 on Ollama 0.32.6 / harness v1 (no node_outputs); v2b on 0.32.9
- lfm2.5-8b-think: both 0.32.9 / harness v2 — clean
- qwen3.5-9b-think: both 0.32.9 / harness v2, both num_predict 8192 — clean
- gemma4: v2 on Ollama 0.32.6 / harness v1 (no node_outputs); v2b on 0.32.9

All 12 journals are complete (1,150/1,150 per arm), duplicate-free under run_id, and the v2b seed
schedule is identical per run_id to v2 in every pair — the contrast is paired at the
(condition, case, repeat, seed) level by construction. Errors are confined to the qwen3.5-think pair
(11 v2 / 8 v2b), all journalled, never retried, and scored as their journalled outcome per the locked
semantics. The 2026-08-18 duplicate-runner incident on results-budget-qwen2.5-7b is invisible here
because the contaminated journals were quarantined and the sweep restarted from zero; the sealed
journal recomputed above is the restarted one.

### 1.2 Serving-stack confound bound

Three pairs cross Ollama versions (and harness journal schema v1→v2): qwen2.5:7b (0.31.1→0.32.9),
qwen3.5-off (0.32.6→0.32.9), gemma4 (0.32.6→0.32.9). The corpus's pure infra replications — same
model, same harness inputs, uniform v2 budgets, no disclosure — bound what a stack change alone does:

| infra pair | arm | pass^1 A | pass^1 B | Δ | 95% CI | p (perm) |
|---|---|---|---|---|---|---|
| qwen2.5:7b 0.31.1 vs 0.32.6 | single | 0.293 | 0.299 | +0.005 | [-0.005, +0.017] | 0.5002 |
| qwen2.5:7b 0.31.1 vs 0.32.6 | mas | 0.449 | 0.456 | +0.007 | [-0.025, +0.040] | 0.7488 |
| qwen3.5:9b 0.31.1 vs 0.32.6 | single | 0.364 | 0.339 | -0.025 | [-0.057, +0.005] | 0.1498 |
| qwen3.5:9b 0.31.1 vs 0.32.6 | mas | 0.253 | 0.255 | +0.001 | [-0.020, +0.023] | 1.0000 |

Largest pure-stack movement: −0.025 (ns). Both Holm-surviving accuracy effects (+0.104, −0.135) are
4–5× larger. The stack difference cannot explain the findings, but it is listed as a limitation (§12)
because 0.32.6→0.32.9 itself was never isolated.

---

## 2. Full Tier-1/2 recomputation (every sweep × arm × condition)

Reading guide: t0-fixed and t07-varied are the primary block (50 cases × 5 and × 15); pert-* are the
perturbation block (10 cases × 5). `base` is the constant-answer baseline for that block. Malformed is
in every number.

#### qwen2.5-7b (qwen2.5:7b-instruct)

| arm | cond | track | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | base | ties | entropy | esc/dis/inv/mal | tokens (p+c) | tools/run | err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | t0-fixed | v2 | 0.244 | 0.220 | — | 0.952 | 0.783 | 0.120 | 0.240 | 0.520 | 0 | 0.043 | 12/14/220/4 | 2099 (1888+211) | 3.0 | 0 |
| single | t0-fixed | v2b | 0.328 | 0.200 | — | 0.856 | 0.689 | 0.360 | 0.320 | 0.520 | 0 | 0.130 | 25/45/176/4 | 2179 (1993+186) | 2.8 | 0 |
| single | t07-varied | v2 | 0.293 | 0.089 | 0.000 | 0.719 | 0.102 | 0.880 | 0.200 | 0.520 | 0 | 0.312 | 38/90/614/8 | 2074 (1867+207) | 3.0 | 0 |
| single | t07-varied | v2b | 0.321 | 0.061 | 0.000 | 0.591 | 0.130 | 1.000 | 0.220 | 0.520 | 1 | 0.471 | 75/118/527/30 | 2308 (2105+203) | 3.0 | 0 |
| single | pert-t0 | v2 | 0.080 | 0.000 | — | 0.880 | 0.443 | 0.300 | 0.100 | 0.600 | 0 | 0.108 | 0/6/44/0 | 2177 (1961+216) | 3.1 | 0 |
| single | pert-t0 | v2b | 0.000 | 0.000 | — | 1.000 | 1.000 | 0.000 | 0.000 | 0.600 | 0 | 0.000 | 0/5/45/0 | 2394 (2168+226) | 3.3 | 0 |
| single | pert-t05 | v2 | 0.120 | 0.000 | — | 0.640 | 0.254 | 0.700 | 0.200 | 0.600 | 0 | 0.302 | 2/15/33/0 | 2180 (1961+219) | 3.1 | 0 |
| single | pert-t05 | v2b | 0.060 | 0.000 | — | 0.680 | 0.233 | 0.600 | 0.000 | 0.600 | 0 | 0.294 | 3/10/37/0 | 2414 (2188+227) | 3.3 | 0 |
| single | pert-t10 | v2 | 0.060 | 0.000 | — | 0.820 | 0.189 | 0.400 | 0.000 | 0.600 | 0 | 0.157 | 2/4/44/0 | 2287 (2052+235) | 3.1 | 0 |
| single | pert-t10 | v2b | 0.020 | 0.000 | — | 0.740 | -0.018 | 0.600 | 0.000 | 0.600 | 0 | 0.229 | 3/4/43/0 | 3460 (3108+352) | 9.3 | 0 |
| mas | t0-fixed | v2 | 0.380 | 0.200 | — | 0.824 | 0.576 | 0.380 | 0.380 | 0.520 | 0 | 0.152 | 5/65/180/0 | 6028 (5070+959) | 9.0 | 0 |
| mas | t0-fixed | v2b | 0.536 | 0.300 | — | 0.754 | 0.604 | 0.520 | 0.520 | 0.520 | 0 | 0.214 | 36/99/113/2 | 8510 (7364+1146) | 10.0 | 0 |
| mas | t07-varied | v2 | 0.449 | 0.107 | 0.020 | 0.647 | 0.279 | 0.900 | 0.540 | 0.520 | 0 | 0.364 | 34/228/484/4 | 6458 (5472+986) | 11.0 | 0 |
| mas | t07-varied | v2b | 0.495 | 0.129 | 0.020 | 0.620 | 0.276 | 0.960 | 0.560 | 0.520 | 0 | 0.391 | 51/246/452/1 | 8348 (7164+1184) | 11.6 | 0 |
| mas | pert-t0 | v2 | 0.100 | 0.100 | — | 0.800 | 0.575 | 0.400 | 0.100 | 0.600 | 0 | 0.169 | 1/16/33/0 | 5876 (4954+921) | 8.8 | 0 |
| mas | pert-t0 | v2b | 0.220 | 0.100 | — | 0.780 | 0.647 | 0.500 | 0.200 | 0.600 | 0 | 0.193 | 7/21/22/0 | 10084 (8890+1193) | 11.1 | 0 |
| mas | pert-t05 | v2 | 0.060 | 0.000 | — | 0.710 | 0.239 | 0.500 | 0.000 | 0.600 | 0 | 0.250 | 1/11/38/0 | 8886 (7455+1431) | 28.6 | 0 |
| mas | pert-t05 | v2b | 0.100 | 0.000 | — | 0.720 | 0.070 | 0.600 | 0.100 | 0.600 | 0 | 0.241 | 0/9/41/0 | 8880 (7508+1372) | 13.9 | 0 |
| mas | pert-t10 | v2 | 0.120 | 0.000 | — | 0.720 | 0.304 | 0.600 | 0.100 | 0.600 | 0 | 0.241 | 1/12/37/0 | 7841 (6570+1271) | 19.9 | 0 |
| mas | pert-t10 | v2b | 0.140 | 0.100 | — | 0.700 | 0.345 | 0.600 | 0.100 | 0.600 | 0 | 0.254 | 0/17/33/0 | 8525 (7340+1185) | 11.0 | 0 |

#### granite4.1-8b (granite4.1:8b)

| arm | cond | track | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | base | ties | entropy | esc/dis/inv/mal | tokens (p+c) | tools/run | err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | t0-fixed | v2 | 0.288 | 0.220 | — | 0.960 | 0.848 | 0.100 | 0.300 | 0.520 | 0 | 0.036 | 13/24/213/0 | 4373 (4120+253) | 3.5 | 0 |
| single | t0-fixed | v2b | 0.340 | 0.260 | — | 0.928 | 0.782 | 0.180 | 0.340 | 0.520 | 0 | 0.065 | 12/37/201/0 | 4729 (4386+343) | 3.6 | 0 |
| single | t07-varied | v2 | 0.299 | 0.171 | 0.120 | 0.830 | 0.328 | 0.620 | 0.240 | 0.520 | 0 | 0.186 | 30/77/643/0 | 4343 (4060+284) | 3.5 | 0 |
| single | t07-varied | v2b | 0.316 | 0.178 | 0.120 | 0.805 | 0.321 | 0.720 | 0.260 | 0.520 | 0 | 0.216 | 35/88/626/1 | 4659 (4319+340) | 3.5 | 0 |
| single | pert-t0 | v2 | 0.200 | 0.200 | — | 0.960 | 0.886 | 0.100 | 0.200 | 0.600 | 0 | 0.036 | 0/11/39/0 | 5471 (5168+303) | 4.4 | 0 |
| single | pert-t0 | v2b | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 | 0.600 | 0 | 0.000 | 5/15/30/0 | 5865 (5480+385) | 4.5 | 0 |
| single | pert-t05 | v2 | 0.120 | 0.000 | — | 0.860 | 0.596 | 0.300 | 0.100 | 0.600 | 0 | 0.121 | 4/6/40/0 | 5133 (4805+328) | 4.1 | 0 |
| single | pert-t05 | v2b | 0.120 | 0.000 | — | 0.760 | 0.351 | 0.500 | 0.100 | 0.600 | 0 | 0.205 | 3/8/39/0 | 5492 (5108+384) | 4.2 | 0 |
| single | pert-t10 | v2 | 0.160 | 0.000 | — | 0.710 | 0.226 | 0.500 | 0.000 | 0.600 | 0 | 0.250 | 5/6/39/0 | 5227 (4879+348) | 4.1 | 0 |
| single | pert-t10 | v2b | 0.200 | 0.000 | — | 0.720 | 0.403 | 0.600 | 0.200 | 0.600 | 0 | 0.241 | 5/10/35/0 | 5567 (5186+381) | 4.2 | 0 |
| mas | t0-fixed | v2 | 0.336 | 0.220 | — | 0.868 | 0.511 | 0.280 | 0.340 | 0.520 | 0 | 0.114 | 5/34/211/0 | 7667 (6672+995) | 5.3 | 0 |
| mas | t0-fixed | v2b | 0.392 | 0.280 | — | 0.872 | 0.678 | 0.300 | 0.380 | 0.520 | 0 | 0.113 | 6/59/185/0 | 8606 (7771+835) | 4.9 | 0 |
| mas | t07-varied | v2 | 0.289 | 0.180 | 0.160 | 0.845 | 0.297 | 0.500 | 0.220 | 0.520 | 0 | 0.165 | 18/74/658/0 | 8380 (7360+1020) | 5.3 | 0 |
| mas | t07-varied | v2b | 0.393 | 0.185 | 0.140 | 0.743 | 0.325 | 0.660 | 0.320 | 0.520 | 0 | 0.261 | 17/166/566/1 | 8637 (7771+866) | 4.9 | 0 |
| mas | pert-t0 | v2 | 0.040 | 0.000 | — | 0.840 | 0.521 | 0.400 | 0.000 | 0.600 | 0 | 0.144 | 1/9/40/0 | 8904 (7897+1006) | 5.4 | 0 |
| mas | pert-t0 | v2b | 0.100 | 0.000 | — | 0.810 | 0.584 | 0.400 | 0.100 | 0.600 | 0 | 0.177 | 1/15/34/0 | 9710 (8814+896) | 5.6 | 0 |
| mas | pert-t05 | v2 | 0.040 | 0.000 | — | 0.840 | 0.437 | 0.400 | 0.000 | 0.600 | 0 | 0.144 | 2/6/42/0 | 8769 (7724+1046) | 5.6 | 0 |
| mas | pert-t05 | v2b | 0.160 | 0.100 | — | 0.800 | 0.463 | 0.400 | 0.100 | 0.600 | 0 | 0.169 | 0/12/38/0 | 9380 (8480+900) | 5.3 | 0 |
| mas | pert-t10 | v2 | 0.080 | 0.000 | — | 0.780 | 0.285 | 0.400 | 0.100 | 0.600 | 0 | 0.182 | 1/8/41/0 | 8744 (7672+1072) | 5.7 | 0 |
| mas | pert-t10 | v2b | 0.160 | 0.100 | — | 0.760 | 0.476 | 0.500 | 0.100 | 0.600 | 0 | 0.205 | 3/12/35/0 | 9406 (8487+919) | 5.3 | 0 |

#### qwen3.5-9b (qwen3.5:9b (think off))

| arm | cond | track | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | base | ties | entropy | esc/dis/inv/mal | tokens (p+c) | tools/run | err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | t0-fixed | v2 | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 | 0.520 | 0 | 0.000 | 35/10/205/0 | 4384 (3983+401) | 3.9 | 0 |
| single | t0-fixed | v2b | 0.320 | 0.320 | — | 1.000 | 1.000 | 0.000 | 0.320 | 0.520 | 0 | 0.000 | 80/10/160/0 | 5351 (4893+457) | 4.3 | 0 |
| single | t07-varied | v2 | 0.339 | 0.079 | 0.040 | 0.655 | 0.241 | 0.900 | 0.300 | 0.520 | 1 | 0.368 | 152/66/529/3 | 4272 (3878+393) | 3.7 | 0 |
| single | t07-varied | v2b | 0.409 | 0.067 | 0.020 | 0.543 | 0.177 | 0.980 | 0.440 | 0.520 | 2 | 0.502 | 185/97/455/13 | 5879 (5328+551) | 4.4 | 0 |
| single | pert-t0 | v2 | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 | 0.600 | 0 | 0.000 | 20/0/30/0 | 3999 (3645+354) | 3.9 | 0 |
| single | pert-t0 | v2b | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 | 0.600 | 0 | 0.000 | 25/10/15/0 | 4200 (3808+392) | 3.8 | 0 |
| single | pert-t05 | v2 | 0.280 | 0.100 | — | 0.660 | 0.383 | 0.600 | 0.400 | 0.600 | 0 | 0.279 | 15/5/30/0 | 4164 (3774+390) | 3.9 | 0 |
| single | pert-t05 | v2b | 0.260 | 0.100 | — | 0.500 | 0.191 | 0.800 | 0.400 | 0.600 | 2 | 0.431 | 18/6/25/1 | 5817 (5201+616) | 4.5 | 0 |
| single | pert-t10 | v2 | 0.240 | 0.100 | — | 0.580 | 0.212 | 0.800 | 0.300 | 0.600 | 1 | 0.394 | 15/2/31/2 | 4125 (3707+418) | 3.8 | 0 |
| single | pert-t10 | v2b | 0.240 | 0.000 | — | 0.440 | 0.102 | 0.900 | 0.200 | 0.600 | 0 | 0.504 | 16/6/26/2 | 5845 (5231+614) | 4.1 | 0 |
| mas | t0-fixed | v2 | 0.300 | 0.300 | — | 1.000 | 1.000 | 0.000 | 0.300 | 0.520 | 0 | 0.000 | 35/5/210/0 | 7492 (6076+1416) | 5.2 | 0 |
| mas | t0-fixed | v2b | 0.260 | 0.260 | — | 1.000 | 1.000 | 0.000 | 0.260 | 0.520 | 0 | 0.000 | 30/0/220/0 | 7289 (6150+1139) | 5.0 | 0 |
| mas | t07-varied | v2 | 0.255 | 0.108 | 0.040 | 0.809 | 0.191 | 0.800 | 0.220 | 0.520 | 0 | 0.223 | 74/25/651/0 | 7761 (6297+1465) | 5.1 | 0 |
| mas | t07-varied | v2b | 0.289 | 0.084 | 0.020 | 0.715 | 0.107 | 0.900 | 0.220 | 0.520 | 0 | 0.314 | 86/53/611/0 | 8633 (7209+1424) | 4.9 | 0 |
| mas | pert-t0 | v2 | 0.000 | 0.000 | — | 1.000 | 1.000 | 0.000 | 0.000 | 0.600 | 0 | 0.000 | 0/0/50/0 | 7616 (6180+1436) | 5.8 | 0 |
| mas | pert-t0 | v2b | 0.100 | 0.100 | — | 1.000 | 1.000 | 0.000 | 0.100 | 0.600 | 0 | 0.000 | 10/0/40/0 | 7295 (6306+989) | 5.2 | 0 |
| mas | pert-t05 | v2 | 0.100 | 0.000 | — | 0.770 | 0.179 | 0.400 | 0.100 | 0.600 | 0 | 0.202 | 7/1/42/0 | 7736 (6286+1450) | 5.6 | 0 |
| mas | pert-t05 | v2b | 0.060 | 0.000 | — | 0.860 | 0.088 | 0.300 | 0.000 | 0.600 | 0 | 0.121 | 2/2/46/0 | 8391 (7202+1189) | 5.3 | 0 |
| mas | pert-t10 | v2 | 0.120 | 0.000 | — | 0.740 | 0.234 | 0.600 | 0.100 | 0.600 | 0 | 0.229 | 8/2/40/0 | 8258 (6702+1557) | 5.5 | 0 |
| mas | pert-t10 | v2b | 0.100 | 0.000 | — | 0.590 | -0.094 | 0.900 | 0.000 | 0.600 | 0 | 0.370 | 5/6/39/0 | 9124 (7633+1491) | 5.1 | 0 |

#### lfm2.5-8b-think (lfm2.5:8b (think ON))

| arm | cond | track | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | base | ties | entropy | esc/dis/inv/mal | tokens (p+c) | tools/run | err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | t0-fixed | v2 | 0.520 | 0.520 | — | 1.000 | 1.000 | 0.000 | 0.520 | 0.520 | 0 | 0.000 | 40/95/110/5 | 4762 (3225+1536) | 3.1 | 0 |
| single | t0-fixed | v2b | 0.600 | 0.600 | — | 1.000 | 1.000 | 0.000 | 0.600 | 0.520 | 0 | 0.000 | 70/115/65/0 | 5524 (3752+1772) | 3.3 | 0 |
| single | t07-varied | v2 | 0.491 | 0.065 | 0.020 | 0.434 | 0.159 | 0.980 | 0.680 | 0.520 | 2 | 0.643 | 168/229/320/33 | 4332 (2730+1601) | 2.6 | 0 |
| single | t07-varied | v2b | 0.500 | 0.061 | 0.000 | 0.424 | 0.157 | 1.000 | 0.680 | 0.520 | 5 | 0.662 | 204/281/240/25 | 5239 (3287+1952) | 2.9 | 0 |
| single | pert-t0 | v2 | 0.600 | 0.600 | — | 1.000 | 1.000 | 0.000 | 0.600 | 0.600 | 0 | 0.000 | 25/15/10/0 | 4947 (3487+1459) | 3.1 | 0 |
| single | pert-t0 | v2b | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 | 0.600 | 0 | 0.000 | 10/20/20/0 | 5868 (4056+1813) | 3.5 | 0 |
| single | pert-t05 | v2 | 0.520 | 0.200 | — | 0.550 | 0.317 | 0.800 | 0.500 | 0.600 | 1 | 0.399 | 18/21/11/0 | 4678 (3277+1401) | 3.0 | 0 |
| single | pert-t05 | v2b | 0.340 | 0.000 | — | 0.410 | 0.183 | 0.900 | 0.600 | 0.600 | 2 | 0.570 | 17/16/13/4 | 5474 (3706+1769) | 3.3 | 0 |
| single | pert-t10 | v2 | 0.480 | 0.000 | — | 0.370 | 0.078 | 1.000 | 0.700 | 0.600 | 0 | 0.588 | 13/22/13/2 | 4427 (2798+1629) | 2.7 | 0 |
| single | pert-t10 | v2b | 0.400 | 0.100 | — | 0.410 | 0.147 | 0.900 | 0.400 | 0.600 | 2 | 0.540 | 13/22/12/3 | 5611 (3730+1881) | 3.4 | 0 |
| mas | t0-fixed | v2 | 0.480 | 0.480 | — | 1.000 | 1.000 | 0.000 | 0.480 | 0.520 | 0 | 0.000 | 80/55/100/15 | 10270 (5381+4889) | 5.5 | 0 |
| mas | t0-fixed | v2b | 0.440 | 0.440 | — | 1.000 | 1.000 | 0.000 | 0.440 | 0.520 | 0 | 0.000 | 80/40/65/65 | 10388 (5745+4643) | 5.3 | 0 |
| mas | t07-varied | v2 | 0.344 | 0.047 | 0.020 | 0.421 | 0.130 | 0.980 | 0.360 | 0.520 | 1 | 0.691 | 225/94/351/80 | 10029 (5218+4811) | 5.3 | 0 |
| mas | t07-varied | v2b | 0.383 | 0.022 | 0.000 | 0.344 | 0.090 | 1.000 | 0.480 | 0.520 | 8 | 0.778 | 239/154/259/98 | 10511 (5727+4784) | 5.5 | 0 |
| mas | pert-t0 | v2 | 0.100 | 0.100 | — | 1.000 | 1.000 | 0.000 | 0.100 | 0.600 | 0 | 0.000 | 15/0/35/0 | 9711 (4850+4861) | 5.3 | 0 |
| mas | pert-t0 | v2b | 0.200 | 0.200 | — | 1.000 | 1.000 | 0.000 | 0.200 | 0.600 | 0 | 0.000 | 10/5/30/5 | 10312 (5554+4758) | 5.4 | 0 |
| mas | pert-t05 | v2 | 0.280 | 0.000 | — | 0.360 | 0.085 | 0.900 | 0.300 | 0.600 | 1 | 0.612 | 16/8/21/5 | 9843 (5003+4840) | 5.0 | 0 |
| mas | pert-t05 | v2b | 0.380 | 0.100 | — | 0.360 | 0.085 | 0.900 | 0.400 | 0.600 | 3 | 0.602 | 22/9/14/5 | 10838 (5803+5035) | 5.5 | 0 |
| mas | pert-t10 | v2 | 0.260 | 0.000 | — | 0.360 | -0.025 | 1.000 | 0.200 | 0.600 | 2 | 0.611 | 11/7/28/4 | 10141 (5147+4994) | 4.9 | 0 |
| mas | pert-t10 | v2b | 0.280 | 0.000 | — | 0.460 | 0.244 | 1.000 | 0.200 | 0.600 | 1 | 0.491 | 17/8/19/6 | 10795 (5793+5002) | 5.3 | 0 |

#### qwen3.5-9b-think (qwen3.5:9b (think ON, np8192))

| arm | cond | track | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | base | ties | entropy | esc/dis/inv/mal | tokens (p+c) | tools/run | err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | t0-fixed | v2 | 0.560 | 0.560 | — | 1.000 | 1.000 | 0.000 | 0.560 | 0.520 | 0 | 0.000 | 35/85/130/0 | 9092 (7000+2092) | 4.5 | 0 |
| single | t0-fixed | v2b | 0.560 | 0.560 | — | 1.000 | 1.000 | 0.000 | 0.560 | 0.520 | 0 | 0.000 | 50/95/105/0 | 13570 (10967+2603) | 5.9 | 0 |
| single | t07-varied | v2 | 0.548 | 0.177 | 0.020 | 0.631 | 0.413 | 0.940 | 0.640 | 0.520 | 2 | 0.411 | 118/260/358/14 | 9550 (7462+2088) | 4.5 | 0 |
| single | t07-varied | v2b | 0.523 | 0.117 | 0.040 | 0.566 | 0.307 | 0.940 | 0.580 | 0.520 | 3 | 0.461 | 140/229/372/9 | 14815 (12201+2614) | 6.1 | 2 |
| single | pert-t0 | v2 | 0.600 | 0.600 | — | 1.000 | 1.000 | 0.000 | 0.600 | 0.600 | 0 | 0.000 | 20/10/20/0 | 10674 (8493+2180) | 6.0 | 0 |
| single | pert-t0 | v2b | 0.400 | 0.400 | — | 1.000 | 1.000 | 0.000 | 0.400 | 0.600 | 0 | 0.000 | 5/20/25/0 | 14603 (11890+2713) | 6.4 | 0 |
| single | pert-t05 | v2 | 0.500 | 0.100 | — | 0.530 | 0.305 | 0.800 | 0.700 | 0.600 | 1 | 0.411 | 16/15/19/0 | 10266 (8127+2139) | 5.3 | 0 |
| single | pert-t05 | v2b | 0.380 | 0.100 | — | 0.600 | 0.356 | 0.700 | 0.400 | 0.600 | 0 | 0.355 | 17/8/25/0 | 16593 (13893+2700) | 7.4 | 0 |
| single | pert-t10 | v2 | 0.540 | 0.200 | — | 0.590 | 0.406 | 0.700 | 0.600 | 0.600 | 1 | 0.378 | 17/14/18/1 | 9952 (7842+2110) | 5.1 | 0 |
| single | pert-t10 | v2b | 0.240 | 0.100 | — | 0.590 | 0.335 | 0.800 | 0.200 | 0.600 | 1 | 0.374 | 11/9/28/2 | 17185 (14138+3046) | 6.9 | 0 |
| mas | t0-fixed | v2 | 0.260 | 0.260 | — | 1.000 | 1.000 | 0.000 | 0.260 | 0.520 | 0 | 0.000 | 50/0/200/0 | 15284 (8411+6874) | 4.9 | 0 |
| mas | t0-fixed | v2b | 0.260 | 0.260 | — | 1.000 | 1.000 | 0.000 | 0.260 | 0.520 | 0 | 0.000 | 75/10/165/0 | 21604 (14585+7019) | 8.2 | 0 |
| mas | t07-varied | v2 | 0.264 | 0.067 | 0.000 | 0.724 | 0.277 | 0.880 | 0.220 | 0.520 | 0 | 0.308 | 146/20/571/13 | 17318 (9346+7972) | 4.9 | 10 |
| mas | t07-varied | v2b | 0.299 | 0.097 | 0.060 | 0.722 | 0.406 | 0.760 | 0.280 | 0.520 | 1 | 0.298 | 216/25/502/7 | 24958 (16736+8222) | 8.2 | 4 |
| mas | pert-t0 | v2 | 0.200 | 0.200 | — | 1.000 | 1.000 | 0.000 | 0.200 | 0.600 | 0 | 0.000 | 15/0/30/5 | 16689 (8515+8174) | 5.5 | 0 |
| mas | pert-t0 | v2b | 0.200 | 0.200 | — | 1.000 | 1.000 | 0.000 | 0.200 | 0.600 | 0 | 0.000 | 15/0/35/0 | 21521 (14477+7045) | 7.8 | 0 |
| mas | pert-t05 | v2 | 0.180 | 0.100 | — | 0.680 | 0.299 | 0.600 | 0.200 | 0.600 | 1 | 0.281 | 15/0/34/1 | 19720 (11319+8400) | 6.3 | 0 |
| mas | pert-t05 | v2b | 0.240 | 0.100 | — | 0.660 | 0.277 | 0.700 | 0.300 | 0.600 | 0 | 0.290 | 18/0/32/0 | 24551 (16951+7600) | 8.8 | 0 |
| mas | pert-t10 | v2 | 0.120 | 0.000 | — | 0.690 | 0.295 | 0.600 | 0.100 | 0.600 | 0 | 0.289 | 11/1/36/2 | 19963 (10827+9136) | 6.0 | 1 |
| mas | pert-t10 | v2b | 0.200 | 0.100 | — | 0.560 | 0.189 | 0.700 | 0.200 | 0.600 | 2 | 0.410 | 14/2/31/3 | 26923 (17013+9909) | 8.0 | 2 |

#### gemma4 (gemma4:latest)

| arm | cond | track | pass^1 | pass^5 | pass^15 | DAR | alpha | flip | MV acc | base | ties | entropy | esc/dis/inv/mal | tokens (p+c) | tools/run | err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | t0-fixed | v2 | 0.648 | 0.520 | — | 0.880 | 0.819 | 0.300 | 0.640 | 0.520 | 0 | 0.108 | 84/69/97/0 | 3663 (2290+1373) | 1.9 | 0 |
| single | t0-fixed | v2b | 0.360 | 0.240 | — | 0.808 | 0.648 | 0.400 | 0.300 | 0.520 | 0 | 0.164 | 90/18/142/0 | 6037 (4095+1943) | 3.6 | 0 |
| single | t07-varied | v2 | 0.552 | 0.185 | 0.080 | 0.594 | 0.387 | 0.900 | 0.600 | 0.520 | 4 | 0.430 | 244/184/312/10 | 3931 (2426+1506) | 2.0 | 0 |
| single | t07-varied | v2b | 0.417 | 0.156 | 0.060 | 0.627 | 0.385 | 0.940 | 0.460 | 0.520 | 2 | 0.416 | 295/84/357/14 | 5930 (3977+1953) | 3.5 | 0 |
| single | pert-t0 | v2 | 0.680 | 0.500 | — | 0.850 | 0.748 | 0.300 | 0.700 | 0.600 | 0 | 0.141 | 28/14/8/0 | 4286 (2724+1561) | 2.3 | 0 |
| single | pert-t0 | v2b | 0.380 | 0.300 | — | 0.880 | 0.766 | 0.300 | 0.400 | 0.600 | 0 | 0.108 | 20/0/29/1 | 6879 (4767+2112) | 4.1 | 0 |
| single | pert-t05 | v2 | 0.560 | 0.300 | — | 0.560 | 0.295 | 0.700 | 0.700 | 0.600 | 1 | 0.395 | 26/10/14/0 | 4365 (2800+1564) | 2.4 | 0 |
| single | pert-t05 | v2b | 0.360 | 0.200 | — | 0.700 | 0.423 | 0.700 | 0.400 | 0.600 | 0 | 0.265 | 28/0/21/1 | 6760 (4661+2099) | 4.0 | 0 |
| single | pert-t10 | v2 | 0.560 | 0.200 | — | 0.500 | 0.258 | 0.800 | 0.600 | 0.600 | 1 | 0.443 | 24/11/12/3 | 4471 (2832+1640) | 2.5 | 0 |
| single | pert-t10 | v2b | 0.440 | 0.300 | — | 0.640 | 0.398 | 0.600 | 0.400 | 0.600 | 0 | 0.346 | 27/3/17/3 | 6648 (4623+2025) | 4.0 | 0 |
| mas | t0-fixed | v2 | 0.312 | 0.240 | — | 0.804 | 0.609 | 0.400 | 0.300 | 0.520 | 0 | 0.167 | 127/0/123/0 | 8953 (4745+4208) | 6.1 | 0 |
| mas | t0-fixed | v2b | 0.280 | 0.120 | — | 0.724 | 0.449 | 0.540 | 0.320 | 0.520 | 0 | 0.232 | 119/0/131/0 | 10940 (6337+4603) | 5.3 | 0 |
| mas | t07-varied | v2 | 0.297 | 0.113 | 0.040 | 0.705 | 0.406 | 0.840 | 0.320 | 0.520 | 0 | 0.304 | 337/1/412/0 | 9491 (5028+4464) | 6.1 | 0 |
| mas | t07-varied | v2b | 0.308 | 0.136 | 0.060 | 0.710 | 0.421 | 0.860 | 0.340 | 0.520 | 0 | 0.300 | 349/1/400/0 | 11299 (6461+4838) | 5.5 | 0 |
| mas | pert-t0 | v2 | 0.320 | 0.200 | — | 0.660 | 0.324 | 0.700 | 0.300 | 0.600 | 0 | 0.290 | 28/0/22/0 | 9610 (5166+4445) | 6.4 | 0 |
| mas | pert-t0 | v2b | 0.280 | 0.000 | — | 0.720 | 0.418 | 0.600 | 0.400 | 0.600 | 0 | 0.241 | 19/0/31/0 | 11827 (7013+4814) | 5.7 | 0 |
| mas | pert-t05 | v2 | 0.260 | 0.100 | — | 0.720 | 0.428 | 0.500 | 0.300 | 0.600 | 0 | 0.230 | 20/0/30/0 | 9619 (5118+4502) | 6.4 | 0 |
| mas | pert-t05 | v2b | 0.280 | 0.200 | — | 0.660 | 0.324 | 0.600 | 0.200 | 0.600 | 0 | 0.279 | 22/0/28/0 | 11939 (7014+4926) | 6.0 | 0 |
| mas | pert-t10 | v2 | 0.280 | 0.000 | — | 0.600 | 0.216 | 0.800 | 0.300 | 0.600 | 0 | 0.339 | 25/0/25/0 | 9959 (5302+4658) | 6.2 | 0 |
| mas | pert-t10 | v2b | 0.300 | 0.000 | — | 0.640 | 0.290 | 0.700 | 0.400 | 0.600 | 0 | 0.302 | 23/0/27/0 | 11495 (6641+4854) | 5.7 | 0 |

Two details worth an owner's eye beyond the headline rows: (i) qwen2.5 v2b's pipeline **beats the
constant baseline at both primary conditions** (MV 0.520 at t0-fixed, 0.560 at t07 vs 0.520) — still
the only configuration in the corpus that does; (ii) gemma4's single-arm harm is **larger at the
fixed-seed condition** (pass^1 0.648→0.360, MV 0.640→0.300) than at t07 (0.552→0.417) — the damage is
not a temperature artefact.

---

## 3. Paired v2→v2b statistics and multiplicity

Per-case paired differences at t07-varied (n=50), the pre-registered primary contrast. DAR and alpha
had not previously been significance-tested on this track; they are here.

| model | arm | metric | v2 | v2b | Δ (v2b−v2) | 95% CI | p (perm) |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b | single | pass^1 | 0.293 | 0.321 | +0.028 ns | [-0.019, +0.075] | 0.2787 |
| qwen2.5-7b | single | DAR | 0.719 | 0.591 | -0.128 *** | [-0.173, -0.083] | 0.0000 |
| qwen2.5-7b | single | alpha | 0.102 | 0.130 | +0.028 ns | [-0.024, +0.080] | 0.4567 |
| qwen2.5-7b | mas | pass^1 | 0.449 | 0.495 | +0.045 * | [+0.005, +0.085] | 0.0350 |
| qwen2.5-7b | mas | DAR | 0.647 | 0.620 | -0.027 ns | [-0.068, +0.013] | 0.1941 |
| qwen2.5-7b | mas | alpha | 0.279 | 0.276 | -0.003 ns | [-0.076, +0.066] | 0.9299 |
| granite4.1-8b | single | pass^1 | 0.299 | 0.316 | +0.017 ns | [-0.009, +0.044] | 0.2490 |
| granite4.1-8b | single | DAR | 0.830 | 0.805 | -0.025 ns | [-0.061, +0.010] | 0.1783 |
| granite4.1-8b | single | alpha | 0.328 | 0.321 | -0.007 ns | [-0.081, +0.065] | 0.8731 |
| granite4.1-8b | mas | pass^1 | 0.289 | 0.393 | +0.104 *** | [+0.061, +0.149] | 0.0000 |
| granite4.1-8b | mas | DAR | 0.845 | 0.743 | -0.102 *** | [-0.151, -0.055] | 0.0002 |
| granite4.1-8b | mas | alpha | 0.297 | 0.325 | +0.028 ns | [-0.097, +0.178] | 0.6978 |
| qwen3.5-9b | single | pass^1 | 0.339 | 0.409 | +0.071 * | [+0.015, +0.127] | 0.0179 |
| qwen3.5-9b | single | DAR | 0.655 | 0.543 | -0.112 *** | [-0.163, -0.063] | 0.0001 |
| qwen3.5-9b | single | alpha | 0.241 | 0.177 | -0.065 ns | [-0.150, +0.026] | 0.1603 |
| qwen3.5-9b | mas | pass^1 | 0.255 | 0.289 | +0.035 * | [+0.005, +0.065] | 0.0382 |
| qwen3.5-9b | mas | DAR | 0.809 | 0.715 | -0.094 *** | [-0.142, -0.046] | 0.0007 |
| qwen3.5-9b | mas | alpha | 0.191 | 0.107 | -0.084 * | [-0.193, +0.018] | 0.0242 |
| lfm2.5-8b-think | single | pass^1 | 0.491 | 0.500 | +0.009 ns | [-0.048, +0.067] | 0.7897 |
| lfm2.5-8b-think | single | DAR | 0.434 | 0.424 | -0.010 ns | [-0.050, +0.030] | 0.6300 |
| lfm2.5-8b-think | single | alpha | 0.159 | 0.157 | -0.003 ns | [-0.061, +0.053] | 0.9234 |
| lfm2.5-8b-think | mas | pass^1 | 0.344 | 0.383 | +0.039 ns | [-0.023, +0.097] | 0.2233 |
| lfm2.5-8b-think | mas | DAR | 0.421 | 0.344 | -0.078 *** | [-0.113, -0.042] | 0.0001 |
| lfm2.5-8b-think | mas | alpha | 0.130 | 0.090 | -0.040 ns | [-0.089, +0.011] | 0.1055 |
| qwen3.5-9b-think | single | pass^1 | 0.548 | 0.523 | -0.025 ns | [-0.067, +0.015] | 0.2555 |
| qwen3.5-9b-think | single | DAR | 0.631 | 0.566 | -0.066 *** | [-0.100, -0.032] | 0.0007 |
| qwen3.5-9b-think | single | alpha | 0.413 | 0.307 | -0.106 *** | [-0.157, -0.055] | 0.0004 |
| qwen3.5-9b-think | mas | pass^1 | 0.264 | 0.299 | +0.035 ns | [-0.017, +0.085] | 0.2096 |
| qwen3.5-9b-think | mas | DAR | 0.724 | 0.722 | -0.002 ns | [-0.053, +0.050] | 0.9357 |
| qwen3.5-9b-think | mas | alpha | 0.277 | 0.406 | +0.129 * | [+0.044, +0.222] | 0.0282 |
| gemma4 | single | pass^1 | 0.552 | 0.417 | -0.135 *** | [-0.205, -0.063] | 0.0010 |
| gemma4 | single | DAR | 0.594 | 0.627 | +0.032 ns | [-0.030, +0.092] | 0.3183 |
| gemma4 | single | alpha | 0.387 | 0.385 | -0.002 ns | [-0.095, +0.087] | 0.9579 |
| gemma4 | mas | pass^1 | 0.297 | 0.308 | +0.011 ns | [-0.012, +0.036] | 0.4637 |
| gemma4 | mas | DAR | 0.705 | 0.710 | +0.006 ns | [-0.028, +0.040] | 0.7460 |
| gemma4 | mas | alpha | 0.406 | 0.421 | +0.015 ns | [-0.049, +0.081] | 0.6599 |

#### Holm-Bonferroni over the full 36-test family (alpha=.05)

| test | raw p | Holm-adjusted p | survives |
|---|---|---|---|
| qwen2.5-7b|single|DAR | 0.0000 | 0.0018 | YES |
| granite4.1-8b|mas|pass^1 | 0.0000 | 0.0018 | YES |
| qwen3.5-9b|single|DAR | 0.0001 | 0.0051 | YES |
| lfm2.5-8b-think|mas|DAR | 0.0001 | 0.0051 | YES |
| granite4.1-8b|mas|DAR | 0.0002 | 0.0064 | YES |
| qwen3.5-9b-think|single|alpha | 0.0004 | 0.0124 | YES |
| qwen3.5-9b|mas|DAR | 0.0007 | 0.0210 | YES |
| qwen3.5-9b-think|single|DAR | 0.0007 | 0.0217 | YES |
| gemma4|single|pass^1 | 0.0010 | 0.0280 | YES |
| qwen3.5-9b|single|pass^1 | 0.0179 | 0.4846 | no |
| qwen3.5-9b|mas|alpha | 0.0242 | 0.6305 | no |
| qwen3.5-9b-think|mas|alpha | 0.0282 | 0.7050 | no |
| qwen2.5-7b|mas|pass^1 | 0.0350 | 0.8412 | no |
| qwen3.5-9b|mas|pass^1 | 0.0382 | 0.8786 | no |
| lfm2.5-8b-think|mas|alpha | 0.1055 | 1.0000 | no |
| qwen3.5-9b|single|alpha | 0.1603 | 1.0000 | no |
| granite4.1-8b|single|DAR | 0.1783 | 1.0000 | no |
| qwen2.5-7b|mas|DAR | 0.1941 | 1.0000 | no |
| qwen3.5-9b-think|mas|pass^1 | 0.2096 | 1.0000 | no |
| lfm2.5-8b-think|mas|pass^1 | 0.2233 | 1.0000 | no |
| granite4.1-8b|single|pass^1 | 0.2490 | 1.0000 | no |
| qwen3.5-9b-think|single|pass^1 | 0.2555 | 1.0000 | no |
| qwen2.5-7b|single|pass^1 | 0.2787 | 1.0000 | no |
| gemma4|single|DAR | 0.3183 | 1.0000 | no |
| qwen2.5-7b|single|alpha | 0.4567 | 1.0000 | no |
| gemma4|mas|pass^1 | 0.4637 | 1.0000 | no |
| lfm2.5-8b-think|single|DAR | 0.6300 | 1.0000 | no |
| gemma4|mas|alpha | 0.6599 | 1.0000 | no |
| granite4.1-8b|mas|alpha | 0.6978 | 1.0000 | no |
| gemma4|mas|DAR | 0.7460 | 1.0000 | no |
| lfm2.5-8b-think|single|pass^1 | 0.7897 | 1.0000 | no |
| granite4.1-8b|single|alpha | 0.8731 | 1.0000 | no |
| lfm2.5-8b-think|single|alpha | 0.9234 | 1.0000 | no |
| qwen2.5-7b|mas|alpha | 0.9299 | 1.0000 | no |
| qwen3.5-9b-think|mas|DAR | 0.9357 | 1.0000 | no |
| gemma4|single|alpha | 0.9579 | 1.0000 | no |

Surviving tests (9/36): gemma4|single|pass^1; granite4.1-8b|mas|DAR; granite4.1-8b|mas|pass^1; lfm2.5-8b-think|mas|DAR; qwen2.5-7b|single|DAR; qwen3.5-9b-think|single|DAR; qwen3.5-9b-think|single|alpha; qwen3.5-9b|mas|DAR; qwen3.5-9b|single|DAR
Pre-registered primary family (12 pass^1 tests) Holm survivors (2/12): gemma4|single|pass^1; granite4.1-8b|mas|pass^1
  gemma4|mas|pass^1: raw 0.4637 -> Holm 1.0000 ns
  gemma4|single|pass^1: raw 0.0010 -> Holm 0.0110 SURVIVES
  granite4.1-8b|mas|pass^1: raw 0.0000 -> Holm 0.0006 SURVIVES
  granite4.1-8b|single|pass^1: raw 0.2490 -> Holm 1.0000 ns
  lfm2.5-8b-think|mas|pass^1: raw 0.2233 -> Holm 1.0000 ns
  lfm2.5-8b-think|single|pass^1: raw 0.7897 -> Holm 1.0000 ns
  qwen2.5-7b|mas|pass^1: raw 0.0350 -> Holm 0.3154 ns
  qwen2.5-7b|single|pass^1: raw 0.2787 -> Holm 1.0000 ns
  qwen3.5-9b-think|mas|pass^1: raw 0.2096 -> Holm 1.0000 ns
  qwen3.5-9b-think|single|pass^1: raw 0.2555 -> Holm 1.0000 ns
  qwen3.5-9b|mas|pass^1: raw 0.0382 -> Holm 0.3154 ns
  qwen3.5-9b|single|pass^1: raw 0.0179 -> Holm 0.1795 ns

**Reading:** the significant repeatability movements are all *declines* in DAR except the curious
qwen3.5-think pipeline alpha (+0.129 raw p=.028, does not survive correction). Of the five nominally
significant accuracy gains, three (qwen2.5 mas, qwen3.5-off single and mas) die under Holm in either
family. What the track can assert at corrected significance:

| finding | Δ | Holm p (36-family) | class |
|---|---|---|---|
| granite4.1 pipeline pass^1 gain | +0.104 | .0018 | accuracy |
| gemma4 single pass^1 harm | −0.135 | .0280 | accuracy |
| qwen2.5 single DAR fall | −0.128 | .0018 | repeatability cost |
| granite4.1 pipeline DAR fall | −0.102 | .0064 | repeatability cost |
| qwen3.5-off single DAR fall | −0.112 | .0051 | repeatability cost |
| qwen3.5-off pipeline DAR fall | −0.094 | .0210 | repeatability cost |
| lfm2.5-think pipeline DAR fall | −0.078 | .0051 | repeatability cost |
| qwen3.5-think single DAR fall | −0.066 | .0217 | repeatability cost |
| qwen3.5-think single alpha fall | −0.106 | .0124 | repeatability cost |

---

## 4. Mechanism: what the budgets actually changed

#### S2a. Tool calls per run (all 1,150 runs per arm) and cap hits at each track's own ceiling

| model | arm/node | v2 mean | v2b mean | v2 med | v2b med | v2 max | v2b max | v2 cap | v2 hits | v2b cap | v2b hits |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | single | 3.03 | 3.29 | 3 | 3 | 6 | 308 | 8 | 0 | 32 | 1 |
| qwen2.5-7b | MAS data | 10.55 | 9.17 | 6 | 7 | 670 | 112 | 8 | 381 | 16 | 33 |
| qwen2.5-7b | MAS policy_risk | 1.07 | 2.15 | 1 | 2 | 3 | 8 | 8 | 0 | 8 | 1 |
| qwen2.5-7b | MAS total | 11.62 | 11.32 | 7 | 9 | 671 | 115 | — | — | — | — |
| granite4.1-8b | single | 3.58 | 3.66 | 4 | 4 | 6 | 7 | 8 | 0 | 32 | 0 |
| granite4.1-8b | MAS data | 4.35 | 3.94 | 4 | 4 | 8 | 7 | 8 | 5 | 16 | 0 |
| granite4.1-8b | MAS policy_risk | 1.00 | 1.00 | 1 | 1 | 1 | 1 | 8 | 0 | 8 | 0 |
| granite4.1-8b | MAS total | 5.35 | 4.94 | 5 | 5 | 9 | 8 | — | — | — | — |
| qwen3.5-9b | single | 3.74 | 4.33 | 4 | 4 | 8 | 11 | 8 | 2 | 32 | 0 |
| qwen3.5-9b | MAS data | 4.20 | 3.94 | 4 | 4 | 7 | 8 | 8 | 0 | 16 | 0 |
| qwen3.5-9b | MAS policy_risk | 1.00 | 1.01 | 1 | 1 | 2 | 5 | 8 | 0 | 8 | 0 |
| qwen3.5-9b | MAS total | 5.20 | 4.94 | 5 | 5 | 8 | 9 | — | — | — | — |
| lfm2.5-8b-think | single | 2.77 | 3.06 | 3 | 3 | 6 | 6 | 8 | 0 | 32 | 0 |
| lfm2.5-8b-think | MAS data | 4.74 | 4.75 | 5 | 5 | 10 | 11 | 8 | 37 | 16 | 0 |
| lfm2.5-8b-think | MAS policy_risk | 0.59 | 0.68 | 1 | 1 | 2 | 2 | 8 | 0 | 8 | 0 |
| lfm2.5-8b-think | MAS total | 5.34 | 5.42 | 6 | 6 | 11 | 12 | — | — | — | — |
| qwen3.5-9b-think | single | 4.65 | 6.14 | 4 | 6 | 10 | 14 | 8 | 38 | 32 | 0 |
| qwen3.5-9b-think | MAS data | 4.13 | 7.18 | 4 | 7 | 13 | 23 | 8 | 35 | 16 | 46 |
| qwen3.5-9b-think | MAS policy_risk | 0.88 | 1.03 | 1 | 1 | 4 | 5 | 8 | 0 | 8 | 0 |
| qwen3.5-9b-think | MAS total | 5.01 | 8.21 | 5 | 8 | 14 | 24 | — | — | — | — |
| gemma4 | single | 2.05 | 3.57 | 2 | 4 | 5 | 6 | 8 | 0 | 32 | 0 |
| gemma4 | MAS data | 5.11 | 4.53 | 5 | 5 | 8 | 7 | 8 | 1 | 16 | 0 |
| gemma4 | MAS policy_risk | 1.00 | 1.00 | 1 | 1 | 2 | 2 | 8 | 0 | 8 | 0 |
| gemma4 | MAS total | 6.11 | 5.53 | 6 | 6 | 9 | 8 | — | — | — | — |

#### S2b. Severed channel (empty node_outputs) rates, MAS arm (harness-v2 journals only)

| model | track | rows w/ node_outputs | empty orch | empty data | empty policy | empty reporting | empty data % |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b | v2 | 0 (harness v1) | — | — | — | — | — |
| qwen2.5-7b | v2b | 1150 | 0 | 32 | 61 | 0 | 2.8% |
| granite4.1-8b | v2 | 1150 | 0 | 0 | 0 | 0 | 0.0% |
| granite4.1-8b | v2b | 1150 | 0 | 0 | 0 | 0 | 0.0% |
| qwen3.5-9b | v2 | 0 (harness v1) | — | — | — | — | — |
| qwen3.5-9b | v2b | 1150 | 0 | 0 | 0 | 0 | 0.0% |
| lfm2.5-8b-think | v2 | 1150 | 0 | 20 | 20 | 0 | 1.7% |
| lfm2.5-8b-think | v2b | 1150 | 0 | 17 | 29 | 0 | 1.5% |
| qwen3.5-9b-think | v2 | 1139 | 0 | 6 | 94 | 8 | 0.5% |
| qwen3.5-9b-think | v2b | 1144 | 0 | 34 | 39 | 2 | 3.0% |
| gemma4 | v2 | 0 (harness v1) | — | — | — | — | — |
| gemma4 | v2b | 1150 | 0 | 0 | 2 | 0 | 0.0% |

#### S2c. Decision distributions at t07-varied (counts /750) and dismissal collapse

| model | arm | track | escalate | dismiss | investigate | malformed | dismiss share | modal share |
|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | single | v2 | 38 | 90 | 614 | 8 | 12.0% | 81.9% |
| qwen2.5-7b | single | v2b | 75 | 118 | 527 | 30 | 15.7% | 70.3% |
| qwen2.5-7b | mas | v2 | 34 | 228 | 484 | 4 | 30.4% | 64.5% |
| qwen2.5-7b | mas | v2b | 51 | 246 | 452 | 1 | 32.8% | 60.3% |
| granite4.1-8b | single | v2 | 30 | 77 | 643 | 0 | 10.3% | 85.7% |
| granite4.1-8b | single | v2b | 35 | 88 | 626 | 1 | 11.7% | 83.5% |
| granite4.1-8b | mas | v2 | 18 | 74 | 658 | 0 | 9.9% | 87.7% |
| granite4.1-8b | mas | v2b | 17 | 166 | 566 | 1 | 22.1% | 75.5% |
| qwen3.5-9b | single | v2 | 152 | 66 | 529 | 3 | 8.8% | 70.5% |
| qwen3.5-9b | single | v2b | 185 | 97 | 455 | 13 | 12.9% | 60.7% |
| qwen3.5-9b | mas | v2 | 74 | 25 | 651 | 0 | 3.3% | 86.8% |
| qwen3.5-9b | mas | v2b | 86 | 53 | 611 | 0 | 7.1% | 81.5% |
| lfm2.5-8b-think | single | v2 | 168 | 229 | 320 | 33 | 30.5% | 42.7% |
| lfm2.5-8b-think | single | v2b | 204 | 281 | 240 | 25 | 37.5% | 37.5% |
| lfm2.5-8b-think | mas | v2 | 225 | 94 | 351 | 80 | 12.5% | 46.8% |
| lfm2.5-8b-think | mas | v2b | 239 | 154 | 259 | 98 | 20.5% | 34.5% |
| qwen3.5-9b-think | single | v2 | 118 | 260 | 358 | 14 | 34.7% | 47.7% |
| qwen3.5-9b-think | single | v2b | 140 | 229 | 372 | 9 | 30.5% | 49.6% |
| qwen3.5-9b-think | mas | v2 | 146 | 20 | 571 | 13 | 2.7% | 76.1% |
| qwen3.5-9b-think | mas | v2b | 216 | 25 | 502 | 7 | 3.3% | 66.9% |
| gemma4 | single | v2 | 244 | 184 | 312 | 10 | 24.5% | 41.6% |
| gemma4 | single | v2b | 295 | 84 | 357 | 14 | 11.2% | 47.6% |
| gemma4 | mas | v2 | 337 | 1 | 412 | 0 | 0.1% | 54.9% |
| gemma4 | mas | v2b | 349 | 1 | 400 | 0 | 0.1% | 53.3% |

#### S2d. Per-label run-level recall at t07-varied (fraction of runs on label-L cases decided L)

| model | arm | track | escalate recall | dismiss recall | investigate recall |
|---|---|---|---|---|---|
| qwen2.5-7b | single | v2 | 0.129 | 0.190 | 0.867 |
| qwen2.5-7b | single | v2b | 0.209 | 0.233 | 0.763 |
| qwen2.5-7b | mas | v2 | 0.102 | 0.515 | 0.837 |
| qwen2.5-7b | mas | v2b | 0.182 | 0.556 | 0.837 |
| granite4.1-8b | single | v2 | 0.129 | 0.174 | 0.941 |
| granite4.1-8b | single | v2b | 0.147 | 0.197 | 0.941 |
| granite4.1-8b | mas | v2 | 0.076 | 0.177 | 0.970 |
| granite4.1-8b | mas | v2b | 0.076 | 0.385 | 0.948 |
| qwen3.5-9b | single | v2 | 0.409 | 0.167 | 0.719 |
| qwen3.5-9b | single | v2b | 0.547 | 0.231 | 0.696 |
| qwen3.5-9b | mas | v2 | 0.240 | 0.049 | 0.874 |
| qwen3.5-9b | mas | v2b | 0.240 | 0.128 | 0.837 |
| lfm2.5-8b-think | single | v2 | 0.489 | 0.482 | 0.519 |
| lfm2.5-8b-think | single | v2b | 0.542 | 0.541 | 0.311 |
| lfm2.5-8b-think | mas | v2 | 0.520 | 0.197 | 0.474 |
| lfm2.5-8b-think | mas | v2b | 0.516 | 0.331 | 0.311 |
| qwen3.5-9b-think | single | v2 | 0.364 | 0.613 | 0.667 |
| qwen3.5-9b-think | single | v2b | 0.449 | 0.531 | 0.622 |
| qwen3.5-9b-think | mas | v2 | 0.373 | 0.051 | 0.696 |
| qwen3.5-9b-think | mas | v2b | 0.582 | 0.062 | 0.511 |
| gemma4 | single | v2 | 0.724 | 0.456 | 0.541 |
| gemma4 | single | v2b | 0.769 | 0.208 | 0.437 |
| gemma4 | mas | v2 | 0.778 | 0.003 | 0.348 |
| gemma4 | mas | v2b | 0.822 | 0.003 | 0.333 |

**Mechanism synthesis.**

*Cap accounting.* The v2 constraint genuinely bound exactly one non-thinking pipeline: qwen2.5's data
node (381/1,150 = 33.1% → 33/1,150 = 2.9%). granite (5→0), gemma4 (1→0), qwen3.5-off (0→0) never had a
binding cap in either track — for them the size manipulation was inert by construction, which is what
makes their movements attributable to the prompt side (§6). The thinking pipelines are the inverse:
lfm was relieved (37→0) and did not move; qwen3.5-think's hits *rose* (35→46) because deliberation
spends turns (§7). One v2b single-arm curiosity: a lone qwen2.5 run issued 308 tool calls inside the
32-turn budget (parallel calls per turn) — budgets bound turns, not calls, and long tails remain
possible.

*Severed channels.* Where both tracks are measurable (harness-v2 journals): granite 0→0, gemma4
pipeline —→0, lfm 20→17 empty data outputs, qwen3.5-think 6→34 (up — turn exhaustion mid-deliberation
leaves the data slot empty more often with a 16-turn ceiling it now reaches). qwen2.5 v2b lands at 32
empty data outputs (2.8%); its v2 rate is not journal-measurable (harness v1), so the published "fell"
is inferred from the cap proxy, not measured (§13).

*Dismissal collapse.* Recovery is real but partial and model-bound: granite's pipeline more than
doubled its dismiss share (9.9%→22.1%; run-level dismiss recall .177→.385) and that recovery *is* its
accuracy gain — escalate recall is unchanged at .076 and investigate recall dips .970→.948, so the
+0.104 is almost entirely reclaimed dismissals. lfm (12.5%→20.5%) and qwen3.5-off (3.3%→7.1%) move the
same direction without reaching health; qwen3.5-think (2.7%→3.3%) and gemma4 (0.1%→0.1%; literally 1
dismissal in 750 runs in both tracks) do not move. Budget headroom cannot restore a category the
model+architecture pair has lost — the anchor mechanism (Ch5 mechanism one) is untouched by resources.

*Where disclosure is verbalised.* Budget mentions in output are almost exclusively a pipeline-arm
phenomenon (S3c table below, §5): granite pipeline 79.7% of runs, qwen3.5-think 24.2%, qwen3.5-off
16.5%, qwen2.5 14.3% — vs ≤1% in every single arm. The stage-local agent, which cannot see the whole
task, is the one that takes the budget sentence up — exactly the asymmetry the CHANGELOG's disclosure
hypothesis predicts, and the arms where verbalisation is highest include the only surviving gain.

---

## 5. The gemma4 harm: anatomy of a backfired instruction

#### S3a. Per-case correct counts /15 (cases with the largest declines first; Δ != 0 only)

| case | label | v2 correct/15 | v2b correct/15 | Δ | v2 decision mix | v2b decision mix |
|---|---|---|---|---|---|---|
| TXN-2025-012 | dismiss | 13 | 3 | -10 | {'dismiss': 13, 'escalate': 1, 'investigate': 1} | {'investigate': 10, 'dismiss': 3, 'escalate': 2} |
| TXN-2025-022 | dismiss | 9 | 0 | -9 | {'dismiss': 9, 'investigate': 4, 'malformed': 1, 'escalate': 1} | {'investigate': 14, 'malformed': 1} |
| TXN-2025-005 | dismiss | 11 | 3 | -8 | {'dismiss': 11, 'investigate': 3, 'escalate': 1} | {'investigate': 11, 'dismiss': 3, 'escalate': 1} |
| TXN-2025-047 | investigate | 11 | 3 | -8 | {'investigate': 11, 'escalate': 4} | {'escalate': 11, 'investigate': 3, 'dismiss': 1} |
| TXN-2025-003 | dismiss | 7 | 0 | -7 | {'investigate': 7, 'dismiss': 7, 'escalate': 1} | {'investigate': 10, 'escalate': 4, 'malformed': 1} |
| TXN-2025-014 | dismiss | 7 | 0 | -7 | {'investigate': 8, 'dismiss': 7} | {'investigate': 13, 'escalate': 2} |
| TXN-2025-025 | investigate | 7 | 0 | -7 | {'investigate': 7, 'escalate': 7, 'malformed': 1} | {'escalate': 14, 'malformed': 1} |
| TXN-2025-036 | dismiss | 8 | 1 | -7 | {'dismiss': 8, 'investigate': 7} | {'investigate': 13, 'escalate': 1, 'dismiss': 1} |
| TXN-2025-048 | dismiss | 9 | 2 | -7 | {'dismiss': 9, 'investigate': 5, 'escalate': 1} | {'investigate': 12, 'dismiss': 2, 'malformed': 1} |
| TXN-2025-038 | dismiss | 8 | 2 | -6 | {'dismiss': 8, 'investigate': 7} | {'investigate': 13, 'dismiss': 2} |
| TXN-2025-024 | dismiss | 10 | 5 | -5 | {'dismiss': 10, 'investigate': 5} | {'investigate': 9, 'dismiss': 5, 'escalate': 1} |
| TXN-2025-030 | dismiss | 15 | 10 | -5 | {'dismiss': 15} | {'dismiss': 10, 'investigate': 4, 'escalate': 1} |
| TXN-2025-039 | escalate | 15 | 10 | -5 | {'escalate': 15} | {'escalate': 10, 'investigate': 3, 'malformed': 2} |
| TXN-2025-040 | dismiss | 7 | 2 | -5 | {'investigate': 8, 'dismiss': 7} | {'investigate': 11, 'dismiss': 2, 'malformed': 1, 'escalate': 1} |
| TXN-2025-050 | dismiss | 7 | 2 | -5 | {'dismiss': 7, 'investigate': 7, 'malformed': 1} | {'investigate': 13, 'dismiss': 2} |
| TXN-2025-046 | dismiss | 11 | 7 | -4 | {'dismiss': 11, 'investigate': 4} | {'dismiss': 7, 'investigate': 6, 'escalate': 1, 'malformed': 1} |
| TXN-2025-013 | investigate | 12 | 9 | -3 | {'investigate': 12, 'escalate': 3} | {'investigate': 9, 'escalate': 6} |
| TXN-2025-018 | dismiss | 3 | 0 | -3 | {'investigate': 10, 'dismiss': 3, 'escalate': 2} | {'investigate': 10, 'escalate': 5} |
| TXN-2025-020 | dismiss | 3 | 0 | -3 | {'investigate': 10, 'dismiss': 3, 'escalate': 2} | {'investigate': 11, 'escalate': 4} |
| TXN-2025-032 | dismiss | 8 | 5 | -3 | {'dismiss': 8, 'investigate': 7} | {'investigate': 9, 'dismiss': 5, 'escalate': 1} |
| TXN-2025-037 | investigate | 6 | 3 | -3 | {'escalate': 8, 'investigate': 6, 'malformed': 1} | {'escalate': 12, 'investigate': 3} |
| TXN-2025-042 | dismiss | 10 | 7 | -3 | {'dismiss': 10, 'investigate': 5} | {'investigate': 7, 'dismiss': 7, 'escalate': 1} |
| TXN-2025-007 | dismiss | 2 | 0 | -2 | {'investigate': 10, 'escalate': 2, 'dismiss': 2, 'malformed': 1} | {'investigate': 14, 'escalate': 1} |
| TXN-2025-008 | investigate | 4 | 2 | -2 | {'escalate': 11, 'investigate': 4} | {'escalate': 12, 'investigate': 2, 'malformed': 1} |
| TXN-2025-049 | escalate | 15 | 13 | -2 | {'escalate': 15} | {'escalate': 13, 'investigate': 2} |
| TXN-2025-021 | investigate | 10 | 9 | -1 | {'investigate': 10, 'dismiss': 5} | {'investigate': 9, 'escalate': 5, 'dismiss': 1} |
| TXN-2025-028 | dismiss | 6 | 5 | -1 | {'investigate': 9, 'dismiss': 6} | {'investigate': 10, 'dismiss': 5} |
| TXN-2025-031 | investigate | 13 | 12 | -1 | {'investigate': 13, 'escalate': 1, 'dismiss': 1} | {'investigate': 12, 'escalate': 2, 'dismiss': 1} |
| TXN-2025-033 | escalate | 13 | 12 | -1 | {'escalate': 13, 'investigate': 2} | {'escalate': 12, 'investigate': 2, 'malformed': 1} |
| TXN-2025-001 | dismiss | 4 | 5 | +1 | {'investigate': 9, 'dismiss': 4, 'escalate': 2} | {'investigate': 8, 'dismiss': 5, 'escalate': 1, 'malformed': 1} |
| TXN-2025-002 | escalate | 14 | 15 | +1 | {'escalate': 14, 'malformed': 1} | {'escalate': 15} |
| TXN-2025-004 | escalate | 14 | 15 | +1 | {'escalate': 14, 'investigate': 1} | {'escalate': 15} |
| TXN-2025-006 | escalate | 13 | 14 | +1 | {'escalate': 13, 'malformed': 2} | {'escalate': 14, 'malformed': 1} |
| TXN-2025-035 | escalate | 13 | 14 | +1 | {'escalate': 13, 'investigate': 2} | {'escalate': 14, 'malformed': 1} |
| TXN-2025-041 | escalate | 12 | 13 | +1 | {'escalate': 12, 'investigate': 3} | {'escalate': 13, 'investigate': 2} |
| TXN-2025-029 | escalate | 11 | 13 | +2 | {'escalate': 11, 'investigate': 4} | {'escalate': 13, 'investigate': 2} |
| TXN-2025-034 | dismiss | 11 | 13 | +2 | {'dismiss': 11, 'investigate': 3, 'escalate': 1} | {'dismiss': 13, 'investigate': 2} |
| TXN-2025-043 | investigate | 6 | 8 | +2 | {'escalate': 9, 'investigate': 6} | {'investigate': 8, 'escalate': 7} |
| TXN-2025-045 | escalate | 3 | 5 | +2 | {'investigate': 12, 'escalate': 3} | {'investigate': 9, 'escalate': 5, 'malformed': 1} |
| TXN-2025-027 | escalate | 5 | 8 | +3 | {'investigate': 10, 'escalate': 5} | {'escalate': 8, 'investigate': 7} |
| TXN-2025-019 | escalate | 7 | 13 | +6 | {'escalate': 7, 'investigate': 7, 'malformed': 1} | {'escalate': 13, 'investigate': 2} |
| TXN-2025-017 | investigate | 4 | 13 | +9 | {'escalate': 11, 'investigate': 4} | {'investigate': 13, 'escalate': 2} |

Cases worse: 29, better: 13, unchanged: 8 (of 50). Net run-level correct: 313 v2b vs 414 v2 (/750).
MV right->wrong cases: 11 ['TXN-2025-003', 'TXN-2025-005', 'TXN-2025-012', 'TXN-2025-022', 'TXN-2025-024', 'TXN-2025-032', 'TXN-2025-036', 'TXN-2025-038', 'TXN-2025-047', 'TXN-2025-048', 'TXN-2025-050']
MV wrong->right cases: 4 ['TXN-2025-017', 'TXN-2025-026', 'TXN-2025-027', 'TXN-2025-043']

Label breakdown of run-level losses (t07 single):
  escalate: v2 163/225 -> v2b 173/225 (+10)
  dismiss: v2 178/390 -> v2b 81/390 (-97)
  investigate: v2 73/135 -> v2b 59/135 (-14)

#### S3b. Behaviour shift (gemma4 single, all conditions pooled and t07)

  [t07-varied] tools/run 2.05->3.46 (+69%); completion tok 1506->1953 (+30%); total tok 3931->5930 (+51%)
  [all 1150] tools/run 2.05->3.57 (+74%); completion tok 1488->1967 (+32%); total tok 3931->6062 (+54%)

  Tool-call histogram, gemma4 single t07 (calls: v2 count -> v2b count):
    0:    6 ->    1
    1:  195 ->   16
    2:  329 ->   73
    3:  200 ->  280
    4:   19 ->  306
    5:    1 ->   73
    6:    0 ->    1

#### S3c. Budget mentions in raw_output (v2b runs; regex: budget|tool-use steps|steps remaining/left)

| model | arm | v2b runs mentioning budget | % | v2 runs mentioning (control) |
|---|---|---|---|---|
| qwen2.5-7b | single | 1/1150 | 0.1% | 0/1150 |
| qwen2.5-7b | mas | 164/1150 | 14.3% | 0/1150 |
| granite4.1-8b | single | 0/1150 | 0.0% | 0/1150 |
| granite4.1-8b | mas | 916/1150 | 79.7% | 1/1150 |
| qwen3.5-9b | single | 12/1150 | 1.0% | 0/1150 |
| qwen3.5-9b | mas | 190/1150 | 16.5% | 1/1150 |
| lfm2.5-8b-think | single | 0/1150 | 0.0% | 0/1150 |
| lfm2.5-8b-think | mas | 36/1150 | 3.1% | 0/1150 |
| qwen3.5-9b-think | single | 0/1150 | 0.0% | 0/1150 |
| qwen3.5-9b-think | mas | 278/1150 | 24.2% | 0/1150 |
| gemma4 | single | 0/1150 | 0.0% | 0/1150 |
| gemma4 | mas | 0/1150 | 0.0% | 0/1150 |

#### S3d. gemma4 single decision shares at t07: v2 vs v2b (per label)

  label=escalate (n=225): v2 {'escalate': 163, 'malformed': 5, 'investigate': 57} -> v2b {'escalate': 173, 'malformed': 6, 'investigate': 46}
  label=dismiss (n=390): v2 {'investigate': 182, 'dismiss': 178, 'escalate': 27, 'malformed': 3} -> v2b {'dismiss': 81, 'investigate': 252, 'escalate': 51, 'malformed': 6}
  label=investigate (n=135): v2 {'investigate': 73, 'escalate': 54, 'dismiss': 6, 'malformed': 2} -> v2b {'escalate': 71, 'malformed': 2, 'investigate': 59, 'dismiss': 3}

**Mechanism answer.** Four facts pin it down:

1. **The harm is a decision-mix shift, not a competence loss on hard cases.** It is concentrated
almost entirely on dismiss-labelled runs: −97 of the net −101 correct runs (dismiss recall .456→.208).
Escalate recall *improved* (.724→.769). The model did not get worse at finding risk; it lost the
ability to say a case is fine — 26 of the 29 deteriorating cases and 10 of the 11 MV right→wrong flips
are dismiss-labelled (TXN-047 being the investigate-labelled exception, herded up to escalate).
2. **It checked more and judged worse.** v2 gemma4 was the corpus's most efficient configuration —
fewest tool calls of any model (2.05/run). Under v2b it runs 3.46 calls/run (+69%), the modal count
moves 2→4, total tokens +51% at t07 — and every extra check is another chance to surface an "unusual" datum
that pushes the decision up the escalation ladder. On dismiss-labelled runs the mass moves precisely
one rung: dismiss 178→81, investigate 182→252, escalate 27→51. That is rulebook-herding toward
investigate, now induced in a *single* agent by an instruction, where the corpus had only ever
produced it in pipelines via the risk-anchor mechanism.
3. **The budget number is almost certainly not the active ingredient.** gemma4 references the budget
in 0 of 1,150 runs in either arm (regex over raw_output + node_outputs; granite, for contrast: 916 of
1,150 pipeline runs). What the b32 single prompt adds beyond the number is a strategy clause — "plan
your investigation so the most decisive checks come first, and stop…" — and gemma4's observed change
(more, earlier, broader checking) is exactly compliance with that clause. This model followed the
instruction faithfully and was damaged by it.
4. **The damage replicates across conditions** — worse at t0-fixed (0.648→0.360) than t07, and its
pert-block MV accuracy halves (0.70/0.70/0.60 → 0.40/0.40/0.40) — so it is not a sampling or seed
artefact, and the pure serving-stack bound (§1.2, ≤0.025) cannot produce it.

**Owner takeaway:** the corpus's best configuration succeeded by *checking little and deciding
decisively*. A generic planning/rationing instruction displaced that policy. This is the strongest
evidence in the whole corpus that prompt-level "process hygiene" is a live intervention with a sign
that depends on the model's incumbent strategy.

---

## 6. The disclosure-vs-size confound

v2b changed two things at once: (a) per-role budget *sizes* (8-uniform → 32/4/16/8/4) and (b)
*disclosure* of the budget (one added sentence per prompt, bundling the number with a
plan-and-stop strategy clause). The track cannot separate them; here is everything that bears on
which one acts.

| evidence | size (a) | disclosure (b) |
|---|---|---|
| granite pipeline +0.104*** with caps inert in both tracks (5→0 hits) | inert by construction | entire gain attributable to (b) |
| granite disclosure verbalised in 79.7% of pipeline runs; single arm 0 mentions, +0.017 ns | — | verbalisation co-located with the gain |
| qwen2.5 pipeline, the only genuinely starved arm (33.1% cap hits), gained *less* (+0.045, ns after Holm) | relief not sufficient | — |
| lfm pipeline relieved 37→0 hits, +0.039 ns | relief not sufficient | model ignores the sentence (3.1% mentions) |
| gemma4 single −0.135*** with zero cap involvement in either track | (a) cannot harm what it never touched | harm attributable to the prompt side; 0 verbalisation points at the strategy clause, not the number |
| thinking models: headroom consumed (cap hits 35→46), no accuracy response | more size ≠ accuracy | sentence present, outcome unmoved |

**What CAN be concluded:** the arm differences are not artefacts of the binding constraint (all six
orderings survive; the only sign change is toward the pipeline, on a model whose cap never bound);
cap-size relief is neither necessary (granite) nor sufficient (qwen2.5, lfm) for accuracy movement;
the prompt-side manipulation is behaviourally active (gemma4's +69% tool calls; granite's verbalised
rationing) and model-specific in sign.

**What CANNOT be concluded:** that disclosure *caused* any specific model's gain (size moved
simultaneously everywhere); that the gemma4 harm is due to the budget number rather than the bundled
strategy clause; anything about magnitude transfer beyond this benchmark and stack.

**The separating design (pre-register before any run):**

- `"<tag>@d8"` — *disclosure-only*: uniform `max_iterations = 8` in both arms exactly as v2, plus the
  b32-style sentence with the TRUE numbers ("at most 8 tool-use steps" per agent; single likewise 8).
  Prompts hashed into the manifest; everything else byte-identical to v2 (cases, conditions, seeds,
  num_predict, parsing, ports, journal discipline).
- `"<tag>@b32-silent"` — *size-only*: the v2b per-role budgets with the v2 prompts untouched.
- This completes the 2×2: v2 = (8, silent), v2b = (32-sized, disclosed), @d8 = (8, disclosed),
  @b32-silent = (32-sized, silent). Primary contrast per cell vs v2, paired per-case as here.
- **Order by information value:** (1) granite@d8 — prediction: the pipeline gain reproduces at the old
  cap if disclosure is the active manipulation; a null instead means size×disclosure interaction.
  (2) gemma4@d8 — prediction: the single-arm harm reproduces (its caps never bind, so @d8 vs v2 is a
  pure prompt contrast on the model with the largest effect). (3) qwen2.5@b32-silent — pure starvation
  relief on the one genuinely starved pipeline. Each is ~5 h / 2,300 runs.
- **Refinement worth pre-registering at the same time:** split the disclosure sentence into
  number-only ("You have a budget of at most N steps.") vs number+strategy (the current clause). The
  gemma4 evidence (§5, fact 3) is that the strategy clause, not the number, carries the harm; a
  two-level disclosure factor tests it directly.
- Power note: with n=50 cases the observed CI half-widths are ≈±0.04; effects half the size of
  granite's are detectable, and the paired seed schedule keeps the contrast variance at the level that
  made +0.104 a p<.001 result.

---

## 7. Thinking × budget: where the headroom went

#### S5a. Token decomposition per arm (all 1,150 runs; mean per run)

| model | arm | v2 prompt | v2b prompt | Δ% | v2 completion | v2b completion | Δ% | v2 total | v2b total | Δ% | Δtools/run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | single | 1887 | 2130 | +13% | 210 | 208 | -1% | 2098 | 2338 | +11% | +0.27 |
| qwen2.5-7b | mas | 5496 | 7305 | +33% | 1009 | 1184 | +17% | 6505 | 8490 | +31% | -0.30 |
| granite4.1-8b | single | 4189 | 4456 | +6% | 282 | 346 | +23% | 4472 | 4802 | +7% | +0.08 |
| granite4.1-8b | mas | 7264 | 7878 | +8% | 1017 | 864 | -15% | 8281 | 8743 | +6% | -0.41 |
| qwen3.5-9b | single | 3879 | 5158 | +33% | 394 | 529 | +34% | 4273 | 5687 | +33% | +0.59 |
| qwen3.5-9b | mas | 6261 | 6958 | +11% | 1456 | 1336 | -8% | 7717 | 8294 | +7% | -0.25 |
| lfm2.5-8b-think | single | 2897 | 3459 | +19% | 1574 | 1896 | +20% | 4471 | 5355 | +20% | +0.30 |
| lfm2.5-8b-think | mas | 5225 | 5730 | +10% | 4839 | 4773 | -1% | 10064 | 10502 | +4% | +0.09 |
| qwen3.5-9b-think | single | 7452 | 12077 | +62% | 2096 | 2638 | +26% | 9548 | 14716 | +54% | +1.50 |
| qwen3.5-9b-think | mas | 9257 | 16191 | +75% | 7811 | 7956 | +2% | 17068 | 24147 | +41% | +3.21 |
| gemma4 | single | 2443 | 4095 | +68% | 1488 | 1967 | +32% | 3931 | 6062 | +54% | +1.51 |
| gemma4 | mas | 4988 | 6490 | +30% | 4417 | 4790 | +8% | 9405 | 11280 | +20% | -0.58 |

#### S5b. Per-node output length (chars, mean over MAS runs with node_outputs)

| model | track | orchestrator | data | policy_risk | reporting |
|---|---|---|---|---|---|
| qwen2.5-7b | v2 | (harness v1) | | | |
| qwen2.5-7b | v2b | 384 | 564 | 1254 | 968 |
| granite4.1-8b | v2 | 1738 | 776 | 1348 | 309 |
| granite4.1-8b | v2b | 1374 | 705 | 1282 | 85 |
| qwen3.5-9b | v2 | (harness v1) | | | |
| qwen3.5-9b | v2b | 825 | 1117 | 1788 | 1335 |
| lfm2.5-8b-think | v2 | 990 | 1031 | 1130 | 644 |
| lfm2.5-8b-think | v2b | 790 | 795 | 1133 | 617 |
| qwen3.5-9b-think | v2 | 1018 | 1707 | 2186 | 1352 |
| qwen3.5-9b-think | v2b | 832 | 1339 | 2116 | 1244 |
| gemma4 | v2 | (harness v1) | | | |
| gemma4 | v2b | 717 | 642 | 1351 | 941 |

#### S5c. Headroom-absorption test: Δcompletion tokens vs Δtool calls vs Δpass^1 (t07, single+mas)

| model | think | arm | Δcompl tok/run | Δtool calls/run | Δpass^1 | Δ significant? |
|---|---|---|---|---|---|---|
| qwen2.5-7b | off | single | -4 | +0.03 | +0.028 | no (p=0.279) |
| qwen2.5-7b | off | mas | +198 | +0.63 | +0.045 | yes (p=0.035) |
| granite4.1-8b | off | single | +57 | +0.08 | +0.017 | no (p=0.249) |
| granite4.1-8b | off | mas | -154 | -0.45 | +0.104 | yes (p=0.000) |
| qwen3.5-9b | off | single | +157 | +0.69 | +0.071 | yes (p=0.018) |
| qwen3.5-9b | off | mas | -41 | -0.23 | +0.035 | yes (p=0.038) |
| lfm2.5-8b-think | on | single | +351 | +0.31 | +0.009 | no (p=0.790) |
| lfm2.5-8b-think | on | mas | -27 | +0.12 | +0.039 | no (p=0.223) |
| qwen3.5-9b-think | on | single | +526 | +1.55 | -0.025 | no (p=0.256) |
| qwen3.5-9b-think | on | mas | +250 | +3.37 | +0.035 | no (p=0.210) |
| gemma4 | off | single | +448 | +1.42 | -0.135 | yes (p=0.001) |
| gemma4 | off | mas | +374 | -0.55 | +0.011 | no (p=0.464) |

#### S5d. qwen3.5-think MAS: completion tokens on data-cap-hit runs vs others (v2b)

  cap-hit runs n=46: mean completion 8692, mean decision dist {'investigate': 26, 'dismiss': 10, 'escalate': 10}
  non-hit runs n=1104: mean completion 7925
  v2 cap-hit runs n=35: decisions {'investigate': 23, 'escalate': 10, 'dismiss': 1, 'malformed': 1}

**Quantifying "deliberation absorbs headroom".**

- *The tokens went to turns, and the turns went to reprocessing.* qwen3.5-think's extra
  ~5,200 (single) and ~7,100 (pipeline) tokens per run are 89% and 98% prompt-side respectively:
  more turns (tool calls +1.5/+3.2 per run) mean the growing context is re-read more times. Completion
  growth is modest (+26% single, +2% pipeline), and the per-node *answer* text got shorter (data node
  1,707→1,339 chars) — the model is not saying more, it is cycling more.
- *Turns are the currency deliberation spends.* The data node under thinking now reaches even the
  demand-sized 16-turn ceiling in 46 runs (vs 35 at the old 8-turn cap) — headroom raised the ceiling
  and the node rose to meet it, and empty data outputs went up (6→34), not down. On cap-hit runs the
  completion side runs ~10% hotter than non-hit runs (8,692 vs 7,925 tokens); the v2→v2b change in
  cap-hit decision mix (dismiss 1→10 of the hit runs) shows the extra turns change *which* failure is
  reached, not whether the answer improves — pass^1 is flat in both arms.
- *The contrast with the responders is clean.* Non-thinking responders moved accuracy with small or
  negative completion deltas (granite pipeline: −154 completion tokens/run alongside +0.104), while
  both thinking models pair the largest cost deltas in the track with null accuracy movement. lfm is
  the boundary case: it neither spends the headroom (tool calls +0.3/+0.1) nor responds — thinking
  models either absorb the budget (qwen3.5-think) or ignore it (lfm); neither exploits it.
- Two models are not a law. gemma4 (thinking off) also burned +54% tokens for negative return — the
  claim that survives is narrower: **no reasoning-enabled model converted headroom into accuracy, and
  the headroom's cost lands mostly on the prompt side, which scales with context length and is
  invisible to completion-token accounting.**

---

## 8. T=0 determinism under v2b

| model | arm | cond | track | groups | byte-identical | decision-flipping | byte-id excl. repeat 0 |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b | single | t0-fixed | v2 | 50 | 4 | 6 | 50 |
| qwen2.5-7b | single | t0-fixed | v2b | 50 | 10 | 18 | 50 |
| qwen2.5-7b | single | pert-t0 | v2 | 10 | 0 | 3 | 10 |
| qwen2.5-7b | single | pert-t0 | v2b | 10 | 1 | 0 | 10 |
| qwen2.5-7b | mas | t0-fixed | v2 | 50 | 0 | 19 | 0 |
| qwen2.5-7b | mas | t0-fixed | v2b | 50 | 0 | 26 | 5 |
| qwen2.5-7b | mas | pert-t0 | v2 | 10 | 0 | 4 | 0 |
| qwen2.5-7b | mas | pert-t0 | v2b | 10 | 0 | 5 | 1 |
| granite4.1-8b | single | t0-fixed | v2 | 50 | 7 | 5 | 50 |
| granite4.1-8b | single | t0-fixed | v2b | 50 | 5 | 9 | 50 |
| granite4.1-8b | single | pert-t0 | v2 | 10 | 1 | 1 | 10 |
| granite4.1-8b | single | pert-t0 | v2b | 10 | 0 | 0 | 10 |
| granite4.1-8b | mas | t0-fixed | v2 | 50 | 12 | 14 | 20 |
| granite4.1-8b | mas | t0-fixed | v2b | 50 | 34 | 15 | 44 |
| granite4.1-8b | mas | pert-t0 | v2 | 10 | 3 | 4 | 5 |
| granite4.1-8b | mas | pert-t0 | v2b | 10 | 6 | 4 | 8 |
| qwen3.5-9b | single | t0-fixed | v2 | 50 | 50 | 0 | 50 |
| qwen3.5-9b | single | t0-fixed | v2b | 50 | 50 | 0 | 50 |
| qwen3.5-9b | single | pert-t0 | v2 | 10 | 10 | 0 | 10 |
| qwen3.5-9b | single | pert-t0 | v2b | 10 | 10 | 0 | 10 |
| qwen3.5-9b | mas | t0-fixed | v2 | 50 | 50 | 0 | 50 |
| qwen3.5-9b | mas | t0-fixed | v2b | 50 | 50 | 0 | 50 |
| qwen3.5-9b | mas | pert-t0 | v2 | 10 | 10 | 0 | 10 |
| qwen3.5-9b | mas | pert-t0 | v2b | 10 | 10 | 0 | 10 |
| lfm2.5-8b-think | single | t0-fixed | v2 | 50 | 50 | 0 | 50 |
| lfm2.5-8b-think | single | t0-fixed | v2b | 50 | 50 | 0 | 50 |
| lfm2.5-8b-think | single | pert-t0 | v2 | 10 | 10 | 0 | 10 |
| lfm2.5-8b-think | single | pert-t0 | v2b | 10 | 10 | 0 | 10 |
| lfm2.5-8b-think | mas | t0-fixed | v2 | 50 | 49 | 0 | 50 |
| lfm2.5-8b-think | mas | t0-fixed | v2b | 50 | 50 | 0 | 50 |
| lfm2.5-8b-think | mas | pert-t0 | v2 | 10 | 10 | 0 | 10 |
| lfm2.5-8b-think | mas | pert-t0 | v2b | 10 | 10 | 0 | 10 |
| qwen3.5-9b-think | single | t0-fixed | v2 | 50 | 50 | 0 | 50 |
| qwen3.5-9b-think | single | t0-fixed | v2b | 50 | 50 | 0 | 50 |
| qwen3.5-9b-think | single | pert-t0 | v2 | 10 | 10 | 0 | 10 |
| qwen3.5-9b-think | single | pert-t0 | v2b | 10 | 10 | 0 | 10 |
| qwen3.5-9b-think | mas | t0-fixed | v2 | 50 | 49 | 0 | 50 |
| qwen3.5-9b-think | mas | t0-fixed | v2b | 50 | 48 | 0 | 49 |
| qwen3.5-9b-think | mas | pert-t0 | v2 | 10 | 10 | 0 | 10 |
| qwen3.5-9b-think | mas | pert-t0 | v2b | 10 | 9 | 0 | 10 |
| gemma4 | single | t0-fixed | v2 | 50 | 1 | 15 | 46 |
| gemma4 | single | t0-fixed | v2b | 50 | 7 | 20 | 26 |
| gemma4 | single | pert-t0 | v2 | 10 | 1 | 3 | 5 |
| gemma4 | single | pert-t0 | v2b | 10 | 0 | 3 | 1 |
| gemma4 | mas | t0-fixed | v2 | 50 | 0 | 20 | 0 |
| gemma4 | mas | t0-fixed | v2b | 50 | 0 | 27 | 0 |
| gemma4 | mas | pert-t0 | v2 | 10 | 0 | 7 | 0 |
| gemma4 | mas | pert-t0 | v2b | 10 | 0 | 6 | 0 |

**Reading.** Determinism class is a model property and the budget regime does not change it: the three
configurations that were byte-identical under v2 (qwen3.5-off, lfm single, qwen3.5-think single, ≈50/50
groups) remain so under v2b; the cache-sensitive ones (qwen2.5, granite pipeline, gemma4) remain
sensitive. Within the sensitive class the longer regime mildly *amplifies* decision consequences:
flip groups rise for qwen2.5 single (6→18/50), qwen2.5 pipeline (19→26), gemma4 single (15→20) and
pipeline (20→27) — more turns per run means more first-evaluation exposures per fixed-seed group, the
same exposure-multiplication argument as Ch5 mechanism two. Two counter-movements are worth noting:
granite's pipeline became *more* byte-stable (12→34 identical groups; its reporting output shrank
309→85 chars — shorter text, fewer divergence points), and gemma4 single's repeat-0-only signature
weakened (byte-identity excluding repeat 0: 46→26/50), i.e. under the longer budget its divergence is
no longer confined to the cold-cache first repeat. Fixed-seed determinism remains unclaimable either
way; v2b does not rescue it and slightly worsens its decision-level footprint.

---

## 9. Perturbation block under v2b

| model | arm | track | pert-t0 | pert-t05 | pert-t10 | pert MV acc t0/t05/t10 (base 0.600) |
|---|---|---|---|---|---|---|
| qwen2.5-7b | single | v2 | 1/10 | 3/10 | 0/10 | 0.10/0.20/0.00 |
| qwen2.5-7b | single | v2b | 4/10 | 2/10 | 2/10 | 0.00/0.00/0.00 |
| qwen2.5-7b | mas | v2 | 3/10 | 2/10 | 1/10 | 0.10/0.00/0.10 |
| qwen2.5-7b | mas | v2b | 5/10 | 3/10 | 0/10 | 0.20/0.10/0.10 |
| granite4.1-8b | single | v2 | 3/10 | 1/10 | 0/10 | 0.20/0.10/0.00 |
| granite4.1-8b | single | v2b | 3/10 | 1/10 | 2/10 | 0.30/0.10/0.20 |
| granite4.1-8b | mas | v2 | 0/10 | 1/10 | 2/10 | 0.00/0.00/0.10 |
| granite4.1-8b | mas | v2b | 2/10 | 1/10 | 1/10 | 0.10/0.10/0.10 |
| qwen3.5-9b | single | v2 | 4/10 | 6/10 | 5/10 | 0.40/0.40/0.30 |
| qwen3.5-9b | single | v2b | 7/10 | 6/10 | 5/10 | 0.40/0.40/0.20 |
| qwen3.5-9b | mas | v2 | 1/10 | 1/10 | 1/10 | 0.00/0.10/0.10 |
| qwen3.5-9b | mas | v2b | 1/10 | 0/10 | 0/10 | 0.10/0.00/0.00 |
| lfm2.5-8b-think | single | v2 | 8/10 | 6/10 | 8/10 | 0.60/0.50/0.70 |
| lfm2.5-8b-think | single | v2b | 5/10 | 8/10 | 6/10 | 0.40/0.60/0.40 |
| lfm2.5-8b-think | mas | v2 | 6/10 | 4/10 | 6/10 | 0.10/0.30/0.20 |
| lfm2.5-8b-think | mas | v2b | 7/10 | 6/10 | 5/10 | 0.20/0.40/0.20 |
| qwen3.5-9b-think | single | v2 | 7/10 | 8/10 | 9/10 | 0.60/0.70/0.60 |
| qwen3.5-9b-think | single | v2b | 7/10 | 7/10 | 6/10 | 0.40/0.40/0.20 |
| qwen3.5-9b-think | mas | v2 | 5/10 | 4/10 | 3/10 | 0.20/0.20/0.10 |
| qwen3.5-9b-think | mas | v2b | 3/10 | 3/10 | 4/10 | 0.20/0.30/0.20 |
| gemma4 | single | v2 | 9/10 | 9/10 | 8/10 | 0.70/0.70/0.60 |
| gemma4 | single | v2b | 7/10 | 6/10 | 8/10 | 0.40/0.40/0.40 |
| gemma4 | mas | v2 | 7/10 | 7/10 | 7/10 | 0.30/0.30/0.30 |
| gemma4 | mas | v2b | 5/10 | 6/10 | 7/10 | 0.40/0.20/0.40 |

**Reading.** No systematic gain in input sensitivity: across 36 movement cells (6 models × 2 arms × 3
conditions), v2b moves more pairs in 11 cells, fewer in 16, and ties in 9 — if anything a slight *decrease*
in movement, well within noise at n=10 per cell. The models that were already perturbation-responsive under v2 (gemma4, qwen3.5-think singles at
7–9/10) stay responsive but their pert-block MV *accuracy* falls (gemma4 single 0.70/0.70/0.60 →
0.40/0.40/0.40; qwen3.5-think single 0.60/0.70/0.60 → 0.40/0.40/0.20): under v2b they move on the
perturbed cases but land on the wrong verdicts more often — on gemma4 this is the §5 harm expressed on
the perturbation set. The collapsed pipelines (granite, qwen3.5) remain nearly immobile (≤2/10).
Budget headroom is not an input-sensitivity intervention.

---

## 10. Cross-track synthesis: everything is a model property

| model | v2 arch Δ (MAS−single) | v2 arch p | v2b arch Δ | v2b arch p | budget Δ single (p) | budget Δ mas (p) |
|---|---|---|---|---|---|---|
| qwen2.5-7b | +0.156 | 0.0003 | +0.173 | 0.0001 | +0.028 (p=0.279) | +0.045 (p=0.035) |
| granite4.1-8b | -0.009 | 0.6754 | +0.077 | 0.0108 | +0.017 (p=0.249) | +0.104 (p=0.000) |
| qwen3.5-9b | -0.084 | 0.0196 | -0.120 | 0.0005 | +0.071 (p=0.018) | +0.035 (p=0.038) |
| lfm2.5-8b-think | -0.147 | 0.0005 | -0.117 | 0.0004 | +0.009 (p=0.790) | +0.039 (p=0.223) |
| qwen3.5-9b-think | -0.284 | 0.0001 | -0.224 | 0.0002 | -0.025 (p=0.256) | +0.035 (p=0.210) |
| gemma4 | -0.255 | 0.0000 | -0.109 | 0.0033 | -0.135 (p=0.001) | +0.011 (p=0.464) |

**Master exhibit** (architecture effect = pipeline − single, t07 pass^1; budget effect = v2b − v2 per
arm; thinking effect per the sealed corpus where a same-stack comparator exists):

| model | arch effect (v2) | arch effect (v2b) | budget: single | budget: pipeline | thinking effect (corpus) |
|---|---|---|---|---|---|
| qwen2.5:7b | **pipeline +0.156*** | **pipeline +0.173*** | +0.028 ns | +0.045 nominal-only | n/a (no thinking mode) |
| granite4.1:8b | none (−0.009, p=.68) | **pipeline +0.077 (p=.011)** | +0.017 ns | **+0.104 Holm-survives** | n/a |
| qwen3.5:9b (off) | **monolith +0.084 (p=.020)** | **monolith +0.120 (p<.001)** | +0.071 nominal-only | +0.035 nominal-only | see think row (4-factor confound vs sealed off-sweep; clean b32 comparator used here) |
| lfm2.5:8b (think) | **monolith +0.147*** | **monolith +0.117*** | +0.009 ns | +0.039 ns | no thinking-off twin (gated) |
| qwen3.5:9b (think) | **monolith +0.284*** | **monolith +0.224*** | −0.025 ns | +0.035 ns | thinking consumed headroom (cap hits ↑, tokens +41–54%) |
| gemma4 | **monolith +0.255*** | **monolith +0.109 (p=.003)** | **−0.135 Holm-survives** | +0.011 ns | n/a |

Six models, six response profiles — and the three effect families land on different models each time:
decomposition helps only qwen2.5; the budget regime helps only granite's pipeline and harms only
gemma4's monolith; thinking's budget interaction appears only on qwen3.5. No property predicts another.
The corpus's central claim — *architecture effects are model properties, measured not assumed* — now
holds for the resource regime by an independent route, with the sharpest possible illustration:
the same one-sentence manipulation produced the track's only Holm-surviving gain on one model and its
only Holm-surviving harm on another. Note also what the budget regime does to the *architecture*
question: it never reverses a significant ordering, but it created one (granite) and halved another
(gemma4, via harm to the stronger arm) — arm-effect magnitudes are conditional on the resource regime.

---

## 11. Practical implications, rewritten in light of the track

1. **Multi-agent reliability cannot be assumed from architecture — nor from the resource regime.**
   The per-model measurement obligation now extends to budgets: the same equalise-size-disclose change
   helped one model's pipeline (+0.104), broke another's monolith (−0.135), and did nothing twice.
   Any vendor claim of the form "we fixed it with bigger/explicit budgets" requires the same paired,
   seed-matched, per-model validation as the architecture claim itself.
2. **Budget sizing to measured role demand is cheap, real hygiene — but expect it to fix failures,
   not accuracy.** Sizing removed a genuine, silent starvation mode (qwen2.5 data node 33.1%→2.9% cap
   hits; severed channel at 2.8%) and cost nothing. What it did not do, anywhere, is buy
   corrected-significant accuracy on its own. Size for integrity; do not size for correctness.
3. **Budget disclosure is an active intervention, not metadata — A/B it per model before shipping.**
   The disclosure sentence (number + plan-and-stop strategy clause) is the track's best candidate for
   both its gain and its harm. It acts most on stage-local pipeline agents (verbalised in up to 80% of
   pipeline runs vs ~0% of monolith runs), and it can displace an incumbent efficient strategy
   (gemma4). Never bundle a rationing instruction into a compliance agent's prompt without a paired
   trial on that model, and monitor the *decision mix* (dismiss share especially) during rollout —
   raw accuracy monitoring would have surfaced gemma4's regression late, the mix shift immediately.
4. **For reasoning-enabled models, budget headroom is spend, not medicine.** Both thinking models
   converted the equalised budget into +41–54% tokens (mostly prompt-side reprocessing, invisible to
   completion accounting) and more cap exhaustion, with zero accuracy return. Cost models for thinking
   deployments must price turns × context growth, and iteration ceilings for thinking pipelines need
   to be set from measured turn demand *under thinking*, not inherited from the non-thinking profile.
5. **Repetition-based QA gets more expensive exactly when you give agents room to work.** The track's
   most uniform corrected finding is the repeatability cost: DAR fell in 10/12 arms (6 surviving
   correction) while accuracy mostly stood still. Longer investigations are more variable ones, so any
   control built on N-run agreement (as this project's Tier-1 is) must re-baseline after any budget
   change — the old agreement thresholds will fail against the new regime even when nothing is wrong.

---

## 12. Limitations of the track itself

1. **The size×disclosure confound is by construction** (pre-declared 2026-08-18) — and the disclosure
   sentence itself bundles two ingredients (the number; the plan-and-stop strategy clause), so even a
   disclosure-only follow-up needs the two-level split in §6 to be fully diagnostic.
2. **One benchmark, small case set, one domain.** 50 primary + 10 perturbation cases of compliance
   triage; MV-movement cells are /10; the label prior (52% dismiss) makes constant-dismiss a strong
   baseline and couples "dismiss recall" tightly to headline accuracy. The gemma4 harm, in particular,
   is a harm *on a dismiss-heavy distribution*; a triage stream with different priors would weigh the
   same behavioural shift differently.
3. **One serving stack, and three pairs cross versions of it.** granite, lfm, qwen3.5-think pairs are
   same-stack clean; qwen2.5, qwen3.5-off, gemma4 pairs cross Ollama 0.31.1/0.32.6→0.32.9 and harness
   journal schema v1→v2 (which also blinds the v2 side of severed-channel accounting). The pure-stack
   bound (§1.2, ≤0.025 ns) covers 0.31.1→0.32.6 only; 0.32.6→0.32.9 was never isolated.
4. **Seeds are shared with v2 — deliberately, and it is a strength worth stating:** planned_runs()
   derives seeds from MASTER_SEED independently of model and track, so every contrast in this document
   is paired at (condition, case, repeat, seed) and no difference can come from different random
   draws. The corresponding cost: all conclusions are conditional on this one seed schedule; nothing
   here estimates variance over seed schedules.
5. **Multiplicity, honestly.** 36 paired tests were run (6 models × 2 arms × {pass^1, DAR, alpha}).
   Under Holm–Bonferroni, 9 survive (§3). Casualties include three of the five nominal accuracy gains
   — qwen2.5 pipeline +0.045, qwen3.5-off single +0.071 and pipeline +0.035 — and both nominal alpha
   movements except qwen3.5-think single. The dissertation's §4.3.6 narrative and Figure 10 colouring
   currently reflect nominal significance and should carry a correction sentence (§13).
6. **Cap-hit accounting is a proxy** (tool-call count ≥ cap). Parallel tool calls can overshoot a turn
   cap (observed up to 670 calls under an 8-turn cap), so "hits" approximates turn exhaustion from the
   journalled call list rather than reading a turn counter.
7. **The qwen3.5-think pair inherits the pre-declared num_predict 8192 override** on both sides — the
   clean comparator was used, but its conclusions do not transfer to 2,048-budget thinking deployments.
8. **Wall-clock is contention-contaminated** wherever arms co-ran on one GPU (corpus-wide caveat);
   tokens are the cost metric throughout this document.

---

## 13. Explicit check against dissertation-v3.tex §4.3.6

Verified as written (recomputed value matches the text): qwen2.5 33.1%→2.9% cap hits and 2.8% severed
channel; pass^1 0.293→0.321 / 0.449→0.495 and advantage +0.156→+0.174; MV 0.560 vs 0.520 baseline with
modal share 64.5%→60.3%; escalations 38→75 / 34→51; tokens +11%/+29%; DAR 0.719→0.591 / 0.647→0.620;
granite 0.289→0.393, +0.104 CI [+0.061,+0.149] p<.001, MV 0.220→0.320, single +0.017 CI [−0.009,+0.044]
p=.25; qwen3.5 +0.071 [+0.015,+0.127] p=.018 / +0.035 [+0.005,+0.065] p=.038 (text: .019/.034 — MC
noise); lfm +0.009 p=.79 / +0.039 p=.22 with cap relief 37→0; qwen3.5-think −0.025 p=.26 / +0.035
p=.21, tokens +55%/+44%, cap hits 35→46; gemma4 0.552→0.417, −0.135 CI [−0.205,−0.063] p=.001, tokens
+51%, fewest tool calls (2.05/run); arch gaps granite −0.010→+0.077, qwen3.5 0.084→0.120, lfm
0.147→0.117.

**Items that do NOT reproduce or need rewording:**

1. **gemma4 pipeline "( +0.011, p=0.34)": the p-value does not reproduce.** Recomputed under the
   corpus's own convention (paired per-case, two-sided sign-flip): p = 0.456–0.457 stable across three
   seeds at 200,000 permutations (one-sided would be 0.229). The Δ (+0.011) matches; the conclusion
   (ns) is unchanged; the printed number appears wrong. Fix to p=0.46 or re-derive.
2. **"Repeatability fell in seven of the eight arms"** (four-model paragraph): recomputed DAR at t07
   fell in **all eight** of those arms (qwen2.5 −0.128/−0.027; granite −0.025/−0.102; qwen3.5
   −0.112/−0.094; lfm −0.010/−0.078). Under alpha it would be six of eight. Neither metric yields
   seven. Suggest "in all eight arms (significantly in five)" if DAR is meant.
3. **"Every model preserves its arm ordering … and no model reverses"** is in tension with the
   paragraph's own granite numbers: granite's arm difference crosses zero, −0.009 (p=.68) → +0.077
   (p=.011). Defensible only because the v2 ordering was null; suggest "no model with a significant v2
   arm difference reverses it, and one null (granite4.1) becomes a significant pipeline advantage".
4. **"Both arms escalated roughly twice as often" (qwen2.5):** single 38→75 is ×1.97, but pipeline
   34→51 is ×1.5. "Roughly twice" overstates the pipeline; suggest "the single arm twice as often, the
   pipeline half again".
5. **Multiplicity is unaddressed.** §4.3.6 states qwen2.5-pipeline, qwen3.5-single and qwen3.5-pipeline
   gains with significance markers; none survives Holm over either the 12-test pre-registered family or
   the 36-test family (§3). Figure 10's caption ("significantly helps one arm on three models") counts
   nominal results — and is also internally imprecise, since on qwen3.5 *both* arms are nominally
   significant, not one. Recommend one added sentence: "Under a Holm correction across the track's
   twelve pre-registered contrasts, the granite pipeline gain and the gemma4 single-arm harm survive;
   the qwen2.5 and qwen3.5 gains do not, and are reported as nominal."
6. **"Its severed evidence channel fell to 2.8 per cent of runs":** the v2b value (32/1,150) is
   correct, but the v2 qwen2.5 journal is harness-v1 and records no node_outputs, so no v2 severed
   rate exists to have "fallen" from; the sentence silently substitutes the cap-exhaustion proxy for
   the v2 side. Suggest "and severed evidence channels occurred in only 2.8 per cent of runs".
7. *(Minor, Chapter 6 forward-reference)*: the fifth practice implication ("size budgets to role
   demand **and disclose them to the agent**") now overclaims — the completed track shows disclosure
   can be net-harmful (gemma4) and inert-but-costly (thinking models). §11.3 above has the corrected
   formulation.

---

*Compute provenance: `backend/experiments/analysis/budget_track_analysis.py` @ seed 20260821;
journals read-only; no GPU, no LLM calls, no serving ports touched. Raw stdout retained at the
scratchpad copy used to assemble this document; rerunning the script reproduces every table verbatim.*
