# Defect impact analysis — deepseek-r1:14b@think and granite4.1:8b

*Written 2026-08-14, after the two independent audits landed
(`backend/experiments/results-deepseek-r1-14b-thinking/audit-independent.md`,
`backend/experiments/results-granite4.1-8b/audit-independent.md`). Read-only over the
sealed corpus; corrected rankings recomputed from the committed per-sweep reports by
`backend/experiments/analysis/eval_impact_rankings.py`. The `results-muse-glimmer-30b`
sweep is in flight and untouched.*

## 0. The two defects, one line each

- **Defect A — deepseek-r1:14b@think:** the Ollama chat template for this model lacks
  `.Tools`; the model never saw a tool schema. 2,300/2,300 runs made **zero tool calls**
  (every other sealed sweep: 9,316–17,236). The MAS `data` node **fabricated evidence in
  all 1,150 MAS runs**; TAR/Jaccard/nLCS = 1.000 are ∅-vs-∅ conventions, not
  measurements. The sweep measured a *tool-free variant of the task* and is not
  comparable to any tool-using sweep.
- **Defect B — granite4.1:8b:** severe mode collapse — 85.6% (single) / 86.9% (MAS) of
  primary runs answer `investigate` against an 18% label prior; every arm×condition cell
  is below the constant-`dismiss` baseline **0.520**; the MAS majority vote moved on
  **0/10** perturbation controls (the sweep's own degeneracy instrument); reported
  entropy is deflated 20.75% by ln 4 normalisation; the only significant arm effects sit
  in the *untested* t0-fixed condition and all favour single.

Both sweeps passed their 8/8 gates. Neither gate contains a tool-call assertion or a
degeneracy check — that hole is itself a finding (§4).

> **Disposition update (owner decision 2026-08-14, option a).** The adversarial
> re-verification (`docs/ADVERSARIAL-FINDINGS-VERDICT.md`) showed the degeneracy
> criteria that excluded granite4.1 are failed equally or worse by retained headline
> cells (qwen2.5-14b-MAS 93.1% modal `investigate`; qwen3.5-MAS 86.0% modal).
> Applying the standard uniformly, **granite4.1 is re-admitted as a fifth
> arm-difference data point with a degeneracy annotation**, and the identical
> annotation is applied to the qwen2.5-14b-MAS and qwen3.5-MAS cells wherever their
> reliability numbers appear (FINAL-RESULTS, SUPERVISOR-PACK, ANALYSIS-INSIGHTS).
> **deepseek-r1:14b remains excluded** — its defect is infrastructure-caused (the
> serving template never rendered tools; the model never saw them), not model
> behaviour, and is not repaired by any annotation. Classifications below marked
> "superseded" are retained for the record with their corrections inline.

---

## 1. Claim inventory

Classification: **DEAD** = must delete/retract; **REVISE** = survives with re-scoping
(corrected text given); **UBC** = unaffected-but-check (true today, breaks on the next
regeneration or on a scope change).

### 1.1 Claims that consumed the defective sweeps

| # | Claim (verbatim or condensed) | Location | Class | Corrected text / action |
|---|---|---|---|---|
| C1 | "deepseek-r1:14b@think is the best configuration measured anywhere in the project: single-arm t07 pass¹ **0.628** … *This invalidates the .tex's claim that gemma4's 0.552 is 'the best label agreement in the experiment'*" | `docs/SESSION-HANDOFF.md:584–588` (§5.2 item 11) | **DEAD** | Delete the whole item. 0.628 was earned on a task with no tool channel; it is not comparable to any tool-using sweep. The gemma4 superlative is **restored** (§2). Replace with the Defect A summary and a pointer to the audit. |
| C2 | "Perfect trajectory metrics (TAR 1.000 in both arms)" for deepseek | `docs/SESSION-HANDOFF.md:586–587` | **DEAD** | TAR/Jaccard/nLCS are vacuous over 2,300 empty trajectories. Report as **N/A** everywhere; never let this row into a cross-model trajectory table. |
| C3 | "roughly 10× cheaper than qwen3.5-thinking (1,050 vs 9,092 tokens/run)" | `docs/SESSION-HANDOFF.md:585–586` | **DEAD** | Cost of a tool-free pipeline vs a tool-using one is not a model comparison. Also T11 (audit): thinking-token accounting is not on the same footing as thinking-off sweeps. |
| C4 | "The single arm beats MAS on all **three** thinking models — lfm2.5 (0.491/0.344), qwen3.5-budget (0.548/0.264), deepseek-r1 (0.628/0.571)" | `docs/SESSION-HANDOFF.md:589–590` (item 12) | **REVISE** | "The single arm beats MAS on **both valid** thinking sweeps — lfm2.5 (0.491/0.344) and qwen3.5-budget (0.548/0.264). The same direction appears in the defective deepseek sweep (0.628 vs 0.571, p=0.024), where the MAS deficit has a known mechanism: with the tool channel dead, the data node fabricated evidence in 1,150/1,150 MAS runs and downstream nodes conditioned on it." |
| C5 | "granite4.1:8b is the redemption test that succeeded … Its arms barely differ (DAR −0.015, p=0.531): a fifth 'no significant arm difference' data point" | `docs/SESSION-HANDOFF.md:610–613` (item 17) | **REVISE** *(superseded 2026-08-14 — owner decision, option a: re-admitted)* | Replace with: "granite4.1:8b gates 8/8 and completed 2,300/2,300 cleanly, and is **re-admitted as a fifth 'no meaningful arm difference' data point, with a degeneracy annotation applied uniformly** — granite4.1 answers `investigate` on 87.7% of MAS / 85.6% of single primary runs, exactly the annotation that also attaches to qwen2.5-14b-MAS (93.1% modal) and qwen3.5-MAS (86.0% modal); in all these cells majority-vote accuracy sits below the 0.520 constant-dismiss baseline. Its t07 arms do not differ meaningfully (pass¹ 0.299 vs 0.289; ΔDAR −0.015, p=0.531); its only significant arm effects sit in the *untested* t0-fixed condition and all favour single (ΔDAR −0.092 p=.019; flip +0.180 p=.047; entropy +0.098 p=.018 — one underlying quantity, uncorrected, suggestive only). With granite included, **5 models show no meaningful arm advantage in accuracy** (qwen3.5, qwen2.5:14b, gemma4, lfm2.5, granite4.1 — MAS gains accuracy only on qwen2.5:7b)." |
| C6 | "Measured cost of deliberation: **1.4–2.1×**, not the 3–5× we assumed" | `docs/WHERE-WE-ARE.md:192`, echoed `docs/SESSION-HANDOFF.md:591–592` (item 13) | **REVISE** | Keep only comparisons not resting on deepseek: "muse-glimmer 76.4→106.6 s MAS (1.40×), 3,604→5,132 tokens (1.42×)" (gate-level). Any deliberation-cost range that included deepseek must be re-derived without it. |
| C7 | Gate table rows "granite4.1:8b … **PASS**", "deepseek-r1:14b … **PASS**" presented as admissibility | `docs/WHERE-WE-ARE.md:182–189`; `docs/SESSION-HANDOFF.md:501,504`; `backend/experiments/CHANGELOG.md:290,297` | **REVISE** | The 8/8 facts stand; the inference "PASS ⇒ admissible" is dead. Annotate both rows: "gate passed; sweep subsequently failed post-hoc validity checks the gate does not contain (tool-call liveness / degeneracy)." |
| C8 | "granite4.1 (3.7 h) — a cheap fifth thinking-off model and a clean redemption test" | `docs/WHERE-WE-ARE.md:268` | **REVISE** | Past-tense correction when the doc is next touched: the redemption ran and failed at workload level (Defect B). |
| C9 | "gemma4 … pass¹ 0.552 … **Already false — deepseek-r1@think single reached 0.628**" (planned .tex fix) | `docs/TEX-FIXES-APPLIED.md:359`; `docs/SESSION-HANDOFF.md:931` (§7.4 row) | **DEAD** | **Cancel this planned correction.** With deepseek excluded, gemma4-single 0.552 is again the best label agreement among valid sweeps. The row should instead instruct: scope the superlative (see §5, line 647). |
| C10 | CHANGELOG queue entry framing: deepseek "Admissible only in this track"; granite "redemption test" | `backend/experiments/CHANGELOG.md:60–66` | **UBC** | Pre-registration prose; leave as history. Both sweeps need **seal + defect entries** in the CHANGELOG (currently absent — the newest entry predates their completion). |

### 1.2 Pooled / cross-model claims that must not silently absorb the defective sweeps

| # | Claim | Location | Class | Action |
|---|---|---|---|---|
| C11 | Cross-model Tier-1 table (13 registry keys, contexts 1–2 only) | `backend/experiments/cross-model-comparison.md` | **UBC** | Currently contains neither defective sweep — safe. When regenerated for 11+ sweeps: deepseek trajectory columns **N/A**, its pass/DAR cells labelled "tool-free variant — not comparable"; granite row carries a "degenerate (below 0.520 baseline)" flag; drop Jaccard from cross-architecture comparison (structurally saturated for MAS — granite audit §2.2). |
| C12 | "Perturbation cases: all models flip decisions when the decisive detail is flipped — high repeatability is not the model ignoring the input" | `docs/FINAL-RESULTS.md:113–114`; `docs/SUPERVISOR-PACK.md:63–65`; `docs/SESSION-HANDOFF.md:569–571` (item 10); `.tex:711` | **REVISE** *(corrected 2026-08-14 — adversarial recompute refuted the earlier "scope to the four sealed models" fix)* | **False even inside the sealed corpus**: qwen2.5-14b's MAS arm — the highest-DAR cell (0.914) — moved its majority vote on **0/10** perturbations at both T>0 conditions and flipped 2/100 runs, *less* responsive than the granite MAS arm (0/10 pert-t0, 17/100 flips). Do not state any universal; report the per-arm movement table (ADVERSARIAL-FINDINGS-VERDICT §C4). FINAL-RESULTS, SUPERVISOR-PACK and `.tex:657` corrected accordingly on 2026-08-14. |
| C13 | "7 completed sweeps, 16,100 scored runs" corpus totals | `docs/FINAL-RESULTS.md:40–41`; `docs/SUPERVISOR-PACK.md:80–81`; `.tex:147,161,542,751` | **UBC** | Accurate for the sealed contexts 1–2 corpus. The planned update to "11 sweeps, 25,300 runs" (`SESSION-HANDOFF.md:930`) must **not** count deepseek/granite as valid headline sweeps: correct framing is "9 valid + 2 capability-gating negative results" (muse pair pending). |
| C14 | "Majority voting buys accuracy back … voting rescues the unstable configurations most" | `docs/ANALYSIS-INSIGHTS.md:27–30`; `docs/SESSION-HANDOFF.md:564–566`; `.tex:695` | **UBC** | Survives for the sealed corpus. Add the new boundary condition: voting cannot rescue a *degenerate* policy — granite MV (0.22–0.34) sits below the 0.520 baseline in every cell; deepseek maj-acc 0.60–0.64 is +0.08–0.12 over baseline at best. Voting converts variance into accuracy only when the underlying distribution discriminates. |
| C15 | "Tool diligence anti-correlates with escalation (all models)" | `docs/ANALYSIS-INSIGHTS.md:23–26`; `.tex:691` | **UBC** | Scope "(all models)" to the four sealed sweeps. deepseek cannot join any tool-diligence pooling (zero tool calls is not "low diligence", it is a dead channel). |
| C16 | Thinking-vs-non-thinking statements citing deepseek as a thinking-track data point | `docs/SESSION-HANDOFF.md:582–590`; `docs/WHERE-WE-ARE.md:255–257,281–283` | **REVISE** | Audit T6: deepseek's `think=true` stamp is nominal — the model reasons structurally regardless; membership in the thinking track is a classification, not a treatment. On top of Defect A, deepseek supports **no** thinking-on/off claim. The muse-glimmer pair remains the only within-model contrast (already stated at `CHANGELOG.md:24,73–77`). |
| C17 | "granite4 … cannot reliably operate tools" in the six-exclusions finding | `docs/FINAL-RESULTS.md:37–39`; `docs/SUPERVISOR-PACK.md:19–20`; `.tex:510` | **UBC** | Refers to granite4:latest (old model), still true. Ensure no future edit conflates it with granite4.1:8b, whose failure mode is different (gates pass, output degenerate). |

### 1.3 Sealed-corpus headline claims (checked, clean)

The four context-1/2 sweeps (qwen3.5:9b, qwen2.5:7b, qwen2.5:14b, gemma4 + the three
0.32.6 replications) are the sole inputs to: the FINAL-RESULTS headline table and all
five findings; SUPERVISOR-PACK findings 1–5 and the winner selection; ANALYSIS-INSIGHTS
items 1–6; `.tex` Chapters 4–6 results content. **Grep-verified: none of these documents
cites a deepseek or granite4.1 number anywhere.** All are **UNAFFECTED**, with the three
scope-hygiene exceptions C12–C15 above.

---

## 2. Recomputed rankings

From `eval_impact_rankings.py` (parses each sweep's committed `analysis-report.md`,
t07-varied, 50 cases × 15 repeats):

| rank | sweep | single pass¹ | mas pass¹ | alpha (s/m) | status |
|---|---|---|---|---|---|
| — | deepseek-r1:14b@think (ctx3) | 0.628 | 0.571 | .425/.304 | **STRUCK — Defect A (tool-free task)** |
| 1 | **gemma4 (ctx2)** | **0.552** | 0.297 | .387/.406 | valid — best label agreement, **statistical tie with rank 2 (see tie disclosure below)** |
| 2 | qwen3.5:9b@think-budget (ctx3) | 0.548 | 0.264 | .413/.277 | valid (cross-context caveat: 4-factor confound vs sealed qwen3.5); **statistically tied with rank 1** |
| 3 | lfm2.5:8b@think (ctx3) | 0.491 | 0.344 | .159/.130 | valid (0.13% contamination disclosed) |
| 4 | qwen2.5:7b (ctx1/2) | 0.293/0.299 | **0.449/0.456** | .10/.28 | valid — best **MAS** label agreement |
| 5 | qwen3.5:9b (ctx1/2) | 0.364/0.339 | 0.253/0.255 | .21/.20 | valid — headline |
| — | granite4.1:8b (ctx3) | 0.299 | 0.289 | .328/.297 | **re-admitted (owner decision 2026-08-14) as fifth arm-difference data point, with degeneracy annotation** (87.7% MAS / 85.6% single modal `investigate`; MV below the 0.520 baseline — same annotation as qwen2.5-14b-MAS and qwen3.5-MAS); unranked for superlatives |
| 6 | qwen2.5:14b (ctx1/2) | 0.248 | 0.221 | .38/.34 | valid |

**Corrected headline superlatives:**

- **Best label agreement: gemma4-single, pass¹ = 0.552 — a statistical tie with
  qwen3.5:9b@think-budget-single (0.548), and it must be stated as one.** The gap is
  +0.004, bootstrap 95% CI [−0.096, +0.111], and the ordering *inverts* (0.546 vs
  0.553) when repeat 0 is excluded from both contenders; the qwen number additionally
  carries the cross-context confound caveat (context, serving version, thinking mode
  and token budget all differ from the sealed qwen3.5 sweep). Within the sealed
  thinking-off corpus the gemma4 superlative is real (0.552 vs 0.364 next-best) —
  `.tex:647` is scoped to that corpus with a tie footnote; the planned 0.628
  correction remains cancelled.
- Best MAS label agreement: qwen2.5:7b, 0.449 (0.456 at ctx2) — unchanged.
- Best repeatability with discrimination intact: qwen2.5:14b (DAR ~0.9, alpha .34–.38) —
  unchanged, with the mode-collapse caveat now stated as the uniform degeneracy
  annotation (its MAS arm is 93.1% modal `investigate`, MV 11/50 vs the 0.520
  constant-dismiss baseline, pert MV moved 0/10 at both T>0 conditions — the same
  annotation granite4.1 carries; ANALYSIS-INSIGHTS item 1).
- granite's DAR 0.83–0.96 and deepseek's TAR 1.000 must never appear in a "best
  repeatability" or "best trajectory stability" ranking: the former is mode collapse,
  the latter is an empty-sequence convention.
- Perspective on the struck 0.628: it is only **+0.108** over the constant-dismiss
  baseline, majority-class-carried (escalate agreement 0.27–0.37), on a task variant
  with no evidence retrieval.

---

## 3. Survival verdicts — headline conclusions

| conclusion | derived from | verdict |
|---|---|---|
| Decomposition changes repeatability; direction is model-dependent (no universal answer) | 4 ctx1/2 sweeps | **SURVIVES** — untouched by either defect. *(Superseded 2026-08-14, owner decision:)* granite **is** re-admitted as the fifth "no arm difference" data point, carrying the uniform degeneracy annotation (C5): its t07 null is a null between two degenerate arms — stated as part of the annotation, exactly as the equally-degenerate qwen2.5-14b-MAS and qwen3.5-MAS cells are annotated — and its t0-fixed effects (all favouring single) remain suggestive-only. |
| T=0 fixed-seed is not deterministic; cache-state effect is a model property, version-invariant | 4 sweeps + 6,900-run replication | **SURVIVES, strengthened** — deepseek adds the cleanest decomposition yet (warm-state single arm exactly deterministic, 1.000 vs MAS 0.930); granite adds the workload-scale gate failure (canary passes 5/5, workload 14%/0% byte-identical). |
| Decomposition redistributes the decision spectrum; dismiss collapse in 3/4 models | 4 sweeps | **SURVIVES** — no dependency. |
| Escalation suppression under MAS in the qwen family | 4 sweeps | **SURVIVES** — no dependency. deepseek's MAS under-escalation (escalate agreement 0.27) is corroborating but must be cited as the tool-free variant if cited at all. |
| gemma4 escalation competence is model character | 4 sweeps | **SURVIVES** — no dependency; gemma4's overall standing improves (best-label-agreement title restored). |
| Majority-vote rescue (self-consistency converts variance to accuracy) | 4 sweeps | **SURVIVES with new boundary condition** (C14): voting cannot rescue a degenerate policy — granite is the proof. |
| "DAR without alpha is misleading" (qwen2.5:14b exhibit) | 4 sweeps | **SURVIVES, strengthened** — granite is the second and sharper exhibit: DAR 0.96 beside accuracy 0.30 beside a 0.52 baseline, and alpha alone catches it (0.848 → 0.226 across cells while DAR stays ≥0.71). |
| Capability gating must precede reliability measurement | gate-failure record | **SURVIVES, strengthened and sharpened** — the two defects show the *current* gates are necessary but not sufficient: both failure modes passed 8/8. |
| Winner selection (MAS platform default via qwen3.5 Tier-1 hierarchy) | qwen3.5 sweep | **SURVIVES with an added caveat** — the deciding DAR advantage (0.802 vs 0.618) coexists with 86.0% modal collapse, MV 11/50 vs the 0.520 baseline, and a 0–1/10 perturbation response in the winning arm; FINAL-RESULTS now carries this annotation beside the number. **Owner decision point:** the platform's `mas` default (`backend/app/deps.py` `get_default_pipeline` docstring cites DAR 0.802 vs 0.618) rests on a number that now carries the degeneracy annotation — whether the default stands is for the owner; `deps.py` deliberately left unchanged. |
| deepseek is the best configuration in the project | deepseek sweep | **DEAD** (C1–C3). |
| Single beats MAS on all three thinking models | thinking track | **REVISE** to two valid models (C4). |
| granite4.1 redemption succeeded / fifth null data point | granite sweep | **REVISE per C5 (superseded 2026-08-14)** — gate-level redemption stands, and the fifth-null-data-point claim is **re-admitted with the uniform degeneracy annotation** (owner decision, option a). |

---

## 4. The reframe — negative results, not silent drops

*Draft prose for the dissertation (Chapter 5 addition or a short §5.x "Two sweeps the
gates should have failed"; register in the CHANGELOG as the disposition of both sweeps).*

> Two further sweeps completed the full 2,300-run protocol, passed every pre-registered
> gate, and produced internally clean journals — and both must be excluded from the
> cross-model comparison, for opposite and instructive reasons. The deepseek-r1:14b
> sweep is a case of *silent tool-channel death*: the serving stack's chat template for
> this model does not render tool schemas, so the model never saw its tools, and all
> 2,300 runs completed without a single tool call while six other models on the
> identical harness made nine to seventeen thousand. Nothing failed loudly. The runs
> parsed, the decisions extracted, the trajectory metrics returned 1.000 — a perfect
> score on a dimension the model never participated in, produced by the empty-versus-
> empty convention. Most seriously, the pipeline's data-gathering node responded to the
> missing channel by *fabricating* the evidence it was built to retrieve — sanctions
> screening outcomes, transaction histories, numeric risk scores — in every one of its
> 1,150 runs, and downstream nodes conditioned on the fabrications. In a compliance
> setting, that is the finding: a multi-agent decomposition without enforced grounding
> does not degrade gracefully when a capability disappears; it invents the capability
> and proceeds with unwarranted confidence.
>
> The granite4.1:8b sweep is the mirror image: every channel alive, every integrity
> check green, and a measured system that had collapsed to a near-constant answer. The
> model replied `investigate` on 86% of runs against an 18% base rate, scoring
> repeatability figures (decision agreement up to 0.96) that a naive reading would call
> excellent — while losing to the one-line predictor "always answer dismiss" in every
> cell, and while the experiment's own degeneracy control, ten cases whose decisive
> facts were flipped, moved its multi-agent majority vote zero times out of ten. This is
> the strongest exhibit this project can offer for its methodological claim that raw
> agreement without chance correction is misleading: Krippendorff's alpha flags the
> collapse (falling to 0.23 where agreement still reads 0.71) and the decision-
> distribution table makes it unmistakable. High repeatability is only evidence of
> reliability when the thing being repeated discriminates.
>
> Both sweeps therefore enter this dissertation as capability-gating results rather
> than reliability measurements, and they close a hole the gate design left open. The
> pre-registered gates checked format compliance, determinism on a short canary, and
> pilot decision extraction — and both of these failure modes pass all of them. Two
> assertions would have caught them, and are proposed here as part of the gating
> method: a **tool-liveness assertion** (any model whose registry entry claims tool
> support must record at least one executed tool call in the pilot, and any node whose
> output asserts tool-derived evidence must have made one), and a **degeneracy gate**
> read at seal time (no single outcome above a pre-registered share of runs, majority-
> vote accuracy at or above the majority-class baseline, and the perturbation block's
> primary readout — did the decision move — reported, not just its agreement
> statistics). Capability gating must precede reliability measurement; these two sweeps
> show it must also *surround* it, because a gate that only inspects the first three
> probes cannot see a channel that dies silently or a distribution that collapses at
> scale.

---

## 5. `docs/dissertation-corrected.tex` — line-by-line

The .tex currently contains **no** deepseek or granite4.1 numbers (grep-verified); its
results chapters are scoped to the sealed 7-sweep corpus. Impact splits into three
groups.

### 5.1 Must change regardless of the thinking-track decision (2 lines + 1 cancellation)

| line | current | replacement |
|---|---|---|
| **647** | "…the single agent is more accurate (pass\^{}1 0.552, the best label agreement in the experiment)…" | *(Updated 2026-08-14 per the adversarial C3 verdict:)* "…the single agent is more accurate (pass\^{}1 0.552, the best label agreement among the sealed thinking-off sweeps)…" **plus a tie footnote**: across the full valid corpus 0.552 vs qwen3.5:9b@think-budget-single's 0.548 is a statistical tie (+0.004, 95% CI [−0.096, +0.111]; ordering inverts, 0.546 vs 0.553, with repeat 0 excluded; cross-context confound on the qwen number). **The planned replacement citing 0.628 (TEX-FIXES-APPLIED.md "Not fixed" table, SESSION-HANDOFF §7.4) is cancelled: deepseek's 0.628 is struck.** |
| **759** | "Run the pre-registered thinking-on condition, already registered under a third infrastructure context, to test whether the decomposition effect survives deliberation being enabled." | "Complete the pre-registered thinking-on condition under the third infrastructure context; two of its sweeps additionally exposed gate holes now closed by a tool-liveness assertion and a degeneracy gate (Chapter 3), and the matched muse-glimmer pair remains the decisive within-model test of whether the decomposition effect survives deliberation." *(If the owner keeps the track wholly out of the dissertation, the minimal edit is to leave 759 as-is — it remains true — but the gate-hole clause is cheap and honest.)* |
| **cancel** | TEX-FIXES-APPLIED.md:359 row instructing that 0.552 "must be updated or removed" | Retract; annotate the row "superseded 2026-08-14 — deepseek sweep invalid (Defect A), superlative restored, scope wording per DEFECT-IMPACT-ANALYSIS §5.1". |

### 5.2 Must change only if the context-3 track (including the two defective sweeps as negative results) enters the dissertation (10 lines + insertions)

| line | current anchor | change |
|---|---|---|
| 161 | "Four locally served models passed pre-registered capability gates and were swept; six failed, which is itself a finding. … seven sealed sweeps and 16,100 scored runs" | Update totals to the valid-sweep count and add one sentence: "Two further sweeps completed all runs but failed post-hoc validity checks — a silent tool-channel failure and a mode collapse — and are reported as capability-gating findings, not reliability measurements." |
| 163 | "three of four models still changed decisions…"; "1.8 to 3.1 times the tokens" | Re-derive both ranges over valid sweeps only; deepseek and granite must not move either endpoint. |
| 510 | "Ten locally served open-weight models were candidates. Each faced pre-registered gates…" | Append the gate-hole closure: "Two later sweeps showed these gates are necessary but not sufficient: a dead tool channel and a degenerate output distribution both passed 8/8. The gating method therefore gains a tool-liveness assertion (pilot runs must record executed tool calls for any tool-claiming model; nodes asserting tool-derived evidence must have called a tool) and a seal-time degeneracy gate (modal-outcome share cap; majority-vote accuracy at or above the majority-class baseline; the perturbation block's decision-movement readout reported first-class)." |
| 532 | Limitations of Method paragraph | Add: "Gate coverage is itself a limitation: the pre-registered gates probe capability at pilot scale and cannot detect failures that only manifest at workload scale, as two context-3 sweeps demonstrated." |
| 542 | "16,100 scored runs" (methodology recap) | Same totals treatment as 161. |
| 653 | "two-version replication" / serving-stack count | "three serving-stack versions" once context 3 is in scope. |
| 691 | "tool diligence anti-correlates with label agreement in every model" | Scope to "every sealed-corpus model" (deepseek made zero tool calls — a dead channel, not low diligence). |
| 695 | majority-vote paragraph | Append boundary condition: "Voting converts variance into accuracy only where the underlying distribution discriminates; a degenerate policy votes its way to the same wrong answer (granite4.1: majority-vote accuracy below the constant-class baseline in every cell)." |
| 711 | "The perturbation block behaved as designed: flipped cases flipped decisions at T>0 in both arms of every model." | *(Corrected 2026-08-14 — the previously proposed "every sealed-corpus model" scoping is itself false: qwen2.5-14b-MAS moved 0/10 at both T>0 conditions.)* Replace with the journal-supported statement: flipped cases flipped decisions at T>0 in every arm except qwen2.5-14b's MAS arm, which moved its majority vote 0/10 at both T>0 conditions (2/100 run flips) — report the per-arm movement table (ADVERSARIAL-FINDINGS-VERDICT §C4). Applied to `.tex:657` on 2026-08-14. |
| 731 / 747 / 751 / 755 | "Four models…", "Across four models…", contributions & limitations model counts | Roster updates per TEX-FIXES-APPLIED "Not fixed" table, with deepseek/granite counted on the *negative-result* side, never in the valid-model denominator. |
| insertion | after 653 (results) or as new §5.x | The three-paragraph reframe from §4 of this document. |

### 5.3 Verified unaffected

Lines 641 (headline numbers), 645–647 comparative logic, 651–653 determinism mechanism,
679, 715, and the whole of Chapters 1–3 results-independent prose: none cites either
defective sweep. Line 319 (Granite-3-8B 100%-consistency citation) refers to the
published Khatchadourian & Franco figure, not to this project's granite sweep — no
change, though the granite4.1 T=0 result (14%/0% byte-identity at workload scale) is a
natural additional refinement of that citation if the track goes in.

**Count: 2 lines must change now (647, 759) plus one cancelled pending fix; 10 further
lines + 1 insertion if the context-3 track enters the dissertation.**

---

## 6. Actions checklist (for the owner / next session)

1. Cancel the 0.628 correction (C9) in `TEX-FIXES-APPLIED.md` and SESSION-HANDOFF §7.4.
2. Rewrite SESSION-HANDOFF §5.2 items 11, 12, 13, 17 per C1–C6.
3. Add CHANGELOG seal + defect-disposition entries for both sweeps (none exists yet).
4. Regenerate `cross-model-comparison.md` with the C11 flags when the roster next moves.
5. Apply the §5.1 .tex edits; hold §5.2 pending the owner's thinking-track decision.
6. Before sealing `muse-glimmer:30b` (in flight): run the tool-liveness assertion and
   degeneracy readout over its journals at seal time — both checks are read-only and
   cheap, and this is the first sweep that can be gated by the corrected method.
7. Adopt §4 as the dissertation reframe; the gate-hole fixes are methodology
   contributions, not confessions.
