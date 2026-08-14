# Systematic novelty search: does the contribution claim survive?

## Search cut-off (binding)

**Declared literature search cut-off: 2026-08-05** — the date the review was conducted
and the boundary the dissertation's gap statement is bounded to. A post-cut-off check
was additionally run on 2026-08-14 and is reported separately (see the note-added-in-proof
in Chapter 2 §2.9); it identified one work, which falls outside the window. Works published after this date are out of scope and require no
further action; the novelty claim is bounded to the evidence available at this date
and is worded accordingly ("to the best of our knowledge, following the documented
protocol below, searched 2026-08-14"). No rolling re-search is required before
submission. This follows standard systematic-review practice: a stated, dated search
boundary is a strength of the method, not a limitation to be chased.

*Protocol executed 2026-08-14. Search window 2023-01-01 to 2026-08-14. This document
is written to be included in the dissertation (methods appendix / related-work
justification). It is deliberately adversarial: the objective was to find the paper
that kills the claim, not to confirm it.*

---

## 1. The claim, decomposed

The novelty claim under test, stated verbatim:

> "First measurement of decision repeatability as a function of agentic decomposition
> in a compliance-triage workflow, via controlled repeated-run comparison on an
> externally authored benchmark."

For a prior work to **displace** this claim, all four of the following must hold
simultaneously. Any single failure makes the work adjacent, not displacing.

| | Criterion | Test applied during screening |
|---|---|---|
| **(a)** | **Repeated-run measurement** | Does it execute the *same input* many times and report variance/agreement across those repeats — not only single-shot accuracy? |
| **(b)** | **Decomposition as the manipulated variable** | Is single-agent vs multi-agent decomposition *the* independent variable, with model, prompt content, tools and temperature held fixed? Manipulating model, scaffold style, or temperature alone does not count. |
| **(c)** | **Compliance domain** | Is the task compliance / AML / KYC / financial-crime or regulated-decision triage, or does the paper explicitly argue transfer to one? |
| **(d)** | **Decision-level agreement on an external benchmark** | Is agreement reported at the level of the *decision* across repeats, and are the cases authored by someone other than the paper's own authors? |

Criterion (b) is the discriminating one. Criterion (d) is the second discriminator.
Almost every near-neighbour in the literature satisfies (a) and either (b) or (c),
but not both, and almost none satisfy (d).

---

## 2. Search protocol

### 2.1 Sources

| Source | Queried? | Method | Notes / failures |
|---|---|---|---|
| arXiv | Yes | `export.arxiv.org/api/query` (6 structured queries) + direct abstract-page fetches (~30) | Fully accessible. Primary source. |
| arXiv (full text) | Yes | `arxiv.org/html/<id>` and `arxiv.org/pdf/<id>` | **One extraction failure**: `arxiv.org/pdf/2608.11344v2` returned unparseable binary. Recovered via the HTML rendering `arxiv.org/html/2608.11344v2`. Documented in §7. |
| Google Scholar | **Indirectly only** | Reached through general web search; Scholar blocks automated querying | Could not run structured Scholar queries. Coverage gap acknowledged in §7. |
| Semantic Scholar | **Indirectly only** | Records surfaced via web search hitting `semanticscholar.org` | The S2 API was not queried directly. Coverage gap acknowledged in §7. |
| ACL Anthology | Yes, partially | Web search restricted toward `aclanthology.org` | Returned three relevant records (2025.findings-emnlp.660, 2025.findings-acl.1141, 2026.acl-long.709). None in a compliance domain. The Anthology's own search endpoint was not queried directly. |
| General web | Yes | 12 web searches | Surfaced non-arXiv practitioner material (Unit21, Kriv AI, Snyk) — none constituting a peer-reviewed or preprint displacement. |
| medRxiv | Incidental | Surfaced via web search | One clinical single-vs-multi-agent record found; wrong domain. |

### 2.2 Date range

2023-01-01 → 2026-08-14. All searches executed **2026-08-14**.

A dedicated post-cutoff sweep was run for material published **after 2026-08-05**
(the prior scan's date), because the field is moving fast and at least one author in
this space publishes frequently. That sweep is what produced the single most dangerous
result in this report (see §5.1).

### 2.3 Query strings, verbatim

**arXiv API queries** (all sorted by `submittedDate` descending):

1. `all:"repeatability" AND all:"agent"` (max 40)
2. `abs:"multi-agent" AND abs:"consistency" AND (abs:"compliance" OR abs:"anti-money" OR abs:"KYC")` (max 40)
3. `(abs:"repeatability" OR abs:"reproducibility" OR abs:"determinism" OR abs:"flakiness") AND abs:"agent" AND (abs:"single-agent" OR abs:"multi-agent")` (max 40)
4. `(abs:"anti-money laundering" OR abs:"AML" OR abs:"KYC" OR abs:"alert triage") AND abs:"agent"` (max 50)
5. `au:"Khatchadourian"` (max 30) — targeted author sweep, see §2.4
6. `(abs:"decision agreement" OR abs:"trajectory agreement" OR abs:"pass^k" OR abs:"run-to-run") AND abs:"agent"` (max 40)

**Web / Scholar / Anthology queries**, verbatim:

7. `LLM agent repeatability variance repeated runs compliance AML alert triage decision agreement`
8. `arxiv single-agent vs multi-agent decomposition output variance repeatability same input repeated runs`
9. `arxiv "multi-agent" reproducibility "decision agreement" KYC OR "know your customer" OR "financial crime" LLM benchmark`
10. `arxiv 2026 "pass^k" OR "pass hat k" agent reliability repeated runs consistency benchmark`
11. `arxiv agentic decomposition determinism "compliance triage" OR "suspicious activity" OR "sanctions screening" repeated runs variance 2026`
12. `arxiv multi-agent system output stability variance versus single agent "same input" repeated executions nondeterminism study`
13. `arxiv August 2026 agent repeatability determinism compliance AML multi-agent decomposition`
14. `"agentic decomposition" repeatability OR reproducibility OR variance measurement study arxiv`
15. `semanticscholar LLM multi-agent versus single agent decision consistency repeated trials financial compliance`
16. `ACL Anthology LLM agent self-consistency determinism multi-agent pipeline variance regulated decision`
17. `arxiv "single agent" versus "multi-agent" "decision agreement rate" OR "flip rate" repeatability AML triage dissertation 2026`
18. `arxiv new submissions August 2026 agent reliability repeatability financial compliance multi-agent architecture variance`

These queries jointly instantiate the required axis grid:
`{repeatability, reproducibility, consistency, determinism, variance, self-consistency,
stability, flakiness}` × `{LLM agent, multi-agent, agentic, tool-calling, MAS}` ×
`{compliance, AML, anti-money laundering, KYC, financial crime, alert triage, SAR,
regulated decision}`, plus the targeted term checks for `pass^k`,
`decision agreement rate`, `trajectory agreement`, and `agentic decomposition`.

### 2.4 Targeted checks

Every arXiv identifier supplied as a known-adjacent work was fetched individually and
placed in the screening table: 2601.15322, 2607.20491, 2511.07585, 2605.28840,
2602.11619, 2605.10516, 2503.13657, 2604.02460, 2510.20963, 2402.05120, 2509.08380,
2607.17044, 2602.08272, 2605.06869, 2605.19099. None was omitted.

A dedicated author sweep (`au:"Khatchadourian"`) was run because that author owns the
three-paper DFAH stack that is closest to this work on criteria (a) and (c). The sweep
confirms **no fourth DFAH paper exists as of 2026-08-14**; the most recent is
2607.20491 v2 (24 July 2026). No post-2026-08-05 output from this author.

### 2.5 Counts

| Stage | Count |
|---|---|
| Records surfaced across all queries (titles + one-line summaries) | 231 |
| Duplicates and clearly off-topic removed at title screen | 178 |
| Records screened at abstract level | 53 |
| Records fetched and assessed in full against (a)–(d) | 31 |
| Full-text (HTML/PDF) deep reads for method detail | 3 (2608.11344, 2601.15322, 2607.20491) |
| **Included as DISPLACING** | **0** |
| Included as adjacent (near-neighbour, materially relevant) | 12 |
| Included as adjacent (contextual) | 19 |

---

## 3. PRISMA-style flow

```
                 IDENTIFICATION
   arXiv API (6 queries) ........................ 250 raw records
   Web / Scholar / Anthology (12 queries) ........  ~90 result links
   Targeted known-adjacent IDs ...................   15 records
                                                   ------
   Records after de-duplication ................... 231
                          |
                          v
                  SCREENING (title + one-line)
   Excluded — off-topic domain (robotics, chem,
   UAV, MARL theory, security-only, memory/skill
   systems, GUI agents) .......................... 178
                          |
                          v
   Records screened at abstract level ............. 53
   Excluded — measures accuracy only, no repeats
   OR no decomposition contrast .................. 22
                          |
                          v
                  ELIGIBILITY (full assessment vs a-d)
   Records assessed in full ....................... 31
                          |
          +---------------+---------------+
          v                               v
   DISPLACING (a AND b AND c AND d)   ADJACENT
          0                               31
                                     ( 12 near-neighbour
                                       19 contextual )
```

**No record satisfied all four criteria.**

---

## 4. Screening table

Legend: `Y` = met, `~` = partially met, `N` = not met.

### 4.1 Near-neighbours (materially relevant — these are the ones that could have killed it)

| # | Paper | What it measures | a | b | c | d | Verdict | One-line reason |
|---|---|---|---|---|---|---|---|---|
| 1 | **arXiv:2608.11344** — Han, *Governing Agentic AI in FinTech* (11 Aug 2026, rev. 13 Aug) | Reproducibility of financial agent actions across model releases, control surfaces, and **orchestration architecture from one to fifty agents** | Y | Y | ~ | **N** | **ADJACENT (critical)** | Fails (d): the 32 FinTech cases are author-constructed, and reproducibility is reported **pooled** across configurations, never as a decision-agreement rate broken down by agent count. |
| 2 | **arXiv:2607.20491** — Khatchadourian, *DFAH-Bench* (10 Jun 2026, rev. 24 Jul) | DAR (decision agreement) and TAR (tool-path agreement) over 4,157 replay episodes on synthetic compliance / DataOps groups | Y | **N** | Y | ~ | ADJACENT (critical) | Fails (b): decomposition is never manipulated — architecture is not a factor in the design; benchmark is the authors' own. |
| 3 | **arXiv:2601.15322** — Khatchadourian, *Replayable Financial Agents (DFAH)* (17 Jan 2026, rev. 7 Mar) | Trajectory determinism, decision determinism and faithfulness across 4,700+ runs, 7 models, incl. a 50-case compliance-triage benchmark | Y | **N** | Y | N | ADJACENT (critical) | Fails (b): the manipulated variable is **model/provider**, not decomposition. Supplies the external benchmark this dissertation consumes. |
| 4 | **arXiv:2511.15755** — Drammeh, *Multi-Agent LLM Orchestration Achieves Deterministic… Incident Response* (19 Nov 2025, rev. 7 Jan 2026) | 348 controlled trials, single-agent copilot vs multi-agent on identical scenarios; reports "zero quality variance" for MAS | Y | Y | **N** | **N** | ADJACENT (critical) | Fails (c) and (d): IT incident response, not compliance; variance is on a bespoke Decision Quality score over author-written scenarios, not decision agreement on an external benchmark. |
| 5 | **arXiv:2602.11619** — Mehta, *When Agents Disagree With Themselves* (12 Feb 2026, rev. 15 Jul) | 8,000 runs; 2.3–4.2 distinct action sequences per 10 runs; consistency as an uncertainty signal; HotpotQA + SWE-bench | Y | **N** | **N** | Y | ADJACENT | Fails (b) and (c): no decomposition contrast; general QA/SWE domain. |
| 6 | **arXiv:2605.28840** — Yagubyan, *How Consistent Are LLM Agents?* (23 Apr 2026) | Tool-selection, ordering and argument consistency across repeated identical invocations (TSS 0.87, AC 0.69) | Y | **N** | **N** | ~ | ADJACENT | Fails (b) and (c): consistency *within* one agent design; no compliance task. |
| 7 | **arXiv:2511.07585** — Khatchadourian & Franco, *LLM Output Drift* (10 Nov 2025) | Output consistency at T=0.0 across 480 runs, 5 models, regulated financial tasks | Y | **N** | ~ | N | ADJACENT | Fails (b): manipulated variable is model size/provider; reconciliation and reporting tasks, not AML triage. |
| 8 | **arXiv:2606.15762** — Tal et al., *Snyk VulnBench JS 1.0: Can LLMs Find the Same Bugs Twice?* (14 Jun 2026) | 300 repeated scans; finding-level stability across 5 identical repetitions on an external benchmark | Y | **N** | **N** | Y | ADJACENT | Fails (b) and (c): security review, single agentic configuration. Methodologically the closest analogue *outside* the domain. |
| 9 | **arXiv:2608.05263** — Chen et al., *OrchestraBench* (5 Aug 2026) | Cascade radius, per-failure-mode recovery, decomposition quality under seeded failure injection; pipeline depth 3–7 | ~ | ~ | ~ | N | ADJACENT | Fails (d) and only partially (a)/(b): depth is varied, not single-vs-multi; a loan-approval reframing is explicitly disclaimed as "not domain-workload claims"; 26 author-written cases. |
| 10 | **arXiv:2604.02460** — Tran & Kiela, *Single-Agent LLMs Outperform Multi-Agent Systems…* (2 Apr 2026) | Accuracy of SAS vs multiple MAS architectures under matched token budgets | **N** | Y | **N** | ~ | ADJACENT | Fails (a): compute-normalised **accuracy**, no repeated-run variance reported as an outcome. |
| 11 | **arXiv:2601.12307** — Xu et al., *Rethinking the Value of Multi-Agent Workflow* (18 Jan 2026) | Single-agent multi-turn simulation of MAS workflows across 7 benchmarks; OneFlow | **N** | Y | **N** | Y | ADJACENT | Fails (a) and (c): accuracy and cost, not run-to-run agreement; no compliance task. |
| 12 | **arXiv:2606.20695** — Kaliyev & Maryanskyy, *How Much Coordination Gain Is Real?* (15 Jun 2026) | Paired noise-floor protocol; coordination-active pass^k on τ²-bench retail across seeds | Y | Y | **N** | Y | ADJACENT | Fails (c) only: methodologically the strictest coordination-vs-none replication design found, but retail domain and the contrast is coordination-active vs inert, not decomposition depth. |

### 4.2 Contextual adjacent works

| # | Paper | What it measures | a | b | c | d | Verdict | One-line reason |
|---|---|---|---|---|---|---|---|---|
| 13 | arXiv:2607.17044 — Dastidar, *Where Does Agent Reliability Come From?* (19 Jul 2026) | Decomposition of accuracy uplift into scaffolding / routing / specialist models / verification loops; SpreadsheetBench, BullshitBench, GAIA | **N** | ~ | **N** | Y | ADJACENT | Read carefully as the closest known title. It decomposes *accuracy uplift by component*, reporting pass@1 and best-of-k — it never re-runs a fixed input to measure output agreement, and the ablated variable is verifier/specialist identity, not agent count. |
| 14 | arXiv:2605.23955 — Zhou et al., *From Accuracy to Auditability* (11 May 2026) | Survey of determinism failures in financial AI: tabular, GNN, LLM agentic workflows; rank instability, flip rates | Y | N | Y | N | ADJACENT | Survey. Directly supports the *motivation*; contains no single-vs-multi-agent repeatability study, and states no such study exists. |
| 15 | arXiv:2601.06112 — Gupta, *ReliabilityBench* (3 Jan 2026) | pass^k consistency, perturbation robustness, fault tolerance; ReAct vs Reflexion, 1,280 episodes | Y | ~ | N | N | ADJACENT | Architecture variable is ReAct vs Reflexion (scaffold style), not decomposition; scheduling/travel/support/e-commerce; own benchmark. |
| 16 | arXiv:2603.29231 — Khanal et al., *Beyond pass@1* (31 Mar 2026) | Reliability Decay Curve, Variance Amplification Factor over 23,392 episodes, 396 tasks | Y | N | N | ~ | ADJACENT | No decomposition contrast; SE and document-processing domains. |
| 17 | arXiv:2605.10516 — Raj et al., *Consistency as a Testable Property* (11 May 2026) | U-statistics for output reliability, kernel metrics for trajectory stability under semantic perturbation | Y | N | N | ~ | ADJACENT | Perturbation-consistency, not repeated-identical-input consistency; no decomposition contrast, no compliance task. |
| 18 | arXiv:2604.08708 — Chen et al., *Every Response Counts (MATU)* (9 Apr 2026) | Uncertainty of MAS via tensor decomposition over multiple execution runs | Y | N | N | N | ADJACENT | Measures MAS uncertainty but never contrasts it against a single-agent control; no compliance domain. |
| 19 | arXiv:2510.20963 — Chen et al., *When and Why Does Multi-Agent Debate Fail* (23 Oct 2025, rev. 14 Jul 2026) | MAD vs single-agent accuracy under matched budgets; ColMAD protocol | N | Y | N | ~ | ADJACENT | Accuracy only. |
| 20 | arXiv:2602.08272 — Su & Wu, *When Do Multi-Agent Systems Outperform?* (9 Feb 2026) | PAC sample-complexity bounds for MARL vs SARL under task decomposition | N | Y | N | N | ADJACENT | Theoretical; no empirical repeated-run measurement. |
| 21 | arXiv:2402.05120 — Li et al., *More Agents Is All You Need* (3 Feb 2024) | Accuracy scaling with number of sampled agents (sampling-and-voting) | N | Y | N | Y | ADJACENT | Agent count is varied but the outcome is accuracy; consistency is used as a *mechanism*, never reported as a result. |
| 22 | arXiv:2503.13657 — Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* (17 Mar 2025, rev. 26 Oct 2025) | MAST failure taxonomy over 1,600+ annotated MAS traces | N | N | N | ~ | ADJACENT | Qualitative failure taxonomy; no controlled single-vs-multi repeatability measurement. |
| 23 | arXiv:2509.08380 — Naik et al., *Co-Investigator AI* (10 Sep 2025) | Agentic SAR-narrative generation with specialised sub-agents | N | N | Y | N | ADJACENT | The canonical "agentic decomposition for AML" system paper — and it reports **no** repeatability measurement whatsoever. Strong support for the gap. |
| 24 | arXiv:2604.19755 — Torres et al., *Explainable AML Triage with LLMs* (22 Mar 2026, rev. 6 Jun) | Evidence-constrained AML triage with counterfactual checks on public synthetic AML benchmarks | N | N | Y | ~ | ADJACENT | Closest AML-triage task paper; measures faithfulness and counterfactual coherence, never run-to-run agreement. |
| 25 | arXiv:2602.23373 — Chernakov et al., *Agentic LLM Framework for Adverse Media Screening in AML Compliance* (29 Dec 2025) | Adverse Media Index scoring against OpenSanctions/PEP lists | N | N | Y | ~ | ADJACENT | AML/KYC domain, discrimination accuracy only. |
| 26 | arXiv:2510.00311 — Wei et al., *CORTEX* (30 Sep 2025) | Multi-agent vs single-agent LLM alert triage quality; false-positive reduction | N | Y | N | N | ADJACENT | Has (b) in an *alert-triage* framing, but the domain is SOC/security, and it reports quality, not repeatability. |
| 27 | arXiv:2607.19899 — *Harnessing Disagreement: Correlated Agreement Blindness in Multi-Agent Triage* (PAAMS 2026) | Inter-agent agreement vs error correlation on UNSW-NB15 | N | Y | N | Y | ADJACENT | Agreement *between agents*, not agreement *across repeats*; network-intrusion domain. |
| 28 | arXiv:2603.22651 — Kulkarni & Kulkarni, *Benchmarking Multi-Agent LLM Architectures for Financial Document Processing* (24 Mar 2026) | Four orchestration patterns × 5 models on 10,000 SEC filings; F1, cost, latency | N | Y | N | N | ADJACENT | Orchestration pattern is the IV and the domain is financial, but the outcome is extraction F1 with no variance analysis and no compliance decision. |
| 29 | arXiv:2608.11381 — Taghavi & Bhavani, *From Numbers to Judgment* (11 Aug 2026) | Monolithic vs specialist-decomposed prompting, model and evidence held fixed, 19 firms | N | Y | N | N | ADJACENT | Post-cutoff check. Clean decomposition manipulation in finance, but the outcome is task score, not repeatability, and the domain is real-estate analysis. |
| 30 | arXiv:2605.19099 — Gao et al., *DecisionBench* (18 May 2026) | Emergent delegation across GAIA / τ-bench / BFCL; routing fidelity, delegation rate | N | ~ | N | Y | ADJACENT | Delegation-to-peer-models, not decomposition into sub-agents; no repeatability outcome. |
| 31 | arXiv:2605.06869 — Creus Castanyer et al., *Agentick* (7 May 2026) | Unified sequential-decision benchmark, 37 tasks, 90,000+ episodes | N | N | N | Y | UNRELATED | General agent benchmark; neither repeatability nor decomposition nor compliance. |

---

## 5. Nearest-neighbour analysis

### 5.1 arXiv:2608.11344 — Han, *Governing Agentic AI in FinTech* (11 Aug 2026) — the closest work found, and it did not exist at the last scan

**This is the most dangerous paper in the literature for this claim and it must be
cited and distinguished explicitly in the dissertation.** It was posted three days
before this search and six days after the previous scan.

What it does, in the authors' own words: *"Study 2 holds the locally served model,
cases, and observed execution settings fixed while changing the agentic architecture
from one to fifty agents."* The case set is described as *"thirty-two fixed FinTech
cases covering credit, trading, anti-money-laundering review, and portfolio
rebalancing."* Study 2's headline finding is that *"Architecture changes final actions,
and no execution record repeated in any configuration at any scale."*

So it satisfies **(a)** — reproducibility measured over repeated executions
(320/320, 319/320, 959/960 counts are reported) — and **(b)** — agent count is
genuinely the manipulated variable with model and cases held fixed — and it partially
satisfies **(c)**, since AML review is one of four case families.

**It fails (d), on two independent grounds:**

1. The 32 cases are *"fixed, constructed financial cases"* built by the author to
   isolate release, control-surface and orchestration effects. They are not an
   externally authored benchmark.
2. It does not report reproducibility **as a function of** agent count. The paper's
   own framing — *"Reproducibility Is a Governance Profile, Not a Scalar"* — leads it
   to report four separate reproducibility constructs (current-outcome,
   historical-outcome, material-process, exact-trace) **pooled across configurations**.
   The qualitative claim is the flat one: *no* execution record repeated in *any*
   configuration. There is no 1-agent vs N-agent decision-agreement contrast, no
   effect size, and no per-architecture breakdown.

**Consequence for the claim.** The word "First" no longer survives in its unqualified
form. Han establishes, before this dissertation, that *architecture affects
reproducibility* in a financial setting that includes AML review. What Han does **not**
do — and what remains open — is measure *decision-level agreement* as a *quantified
function of* decomposition, on cases the author did not write. That is the surviving
contribution, and it is narrower than the claim as currently worded.

### 5.2 arXiv:2607.20491 — Khatchadourian, *DFAH-Bench* — fails (b)

Supplies the DAR and TAR constructs this dissertation adopts, and measures decision
agreement (94.2–95.1%) and tool-path agreement (66.9–69.4%) over 4,157 replay episodes
in synthetic compliance and financial-DataOps groups. It is the metric parent, not a
competitor: **decomposition is never a factor.** The variance it partitions is across
models and configurations, never across single-agent vs multi-agent pipelines. This is
the single cleanest "closest work, different question" citation available.

### 5.3 arXiv:2601.15322 — Khatchadourian, *Replayable Financial Agents (DFAH)* — fails (b)

Measures decision determinism across 4,700+ runs at T=0.0 and finds determinism and
accuracy uncorrelated (r = −0.11, p = 0.63). Its 50-case compliance-triage benchmark is
the external benchmark this dissertation runs on. Because DFAH manipulates **model and
provider**, and this dissertation manipulates **decomposition on DFAH's own cases**,
the two are complementary rather than competing — which is the strongest possible
framing available and should be stated as such.

### 5.4 arXiv:2511.15755 — Drammeh, *Multi-Agent LLM Orchestration…* — fails (c) and (d)

The only prior work found that satisfies both (a) and (b) *empirically*: 348 controlled
trials, single-agent copilot vs multi-agent on identical incident scenarios, with
variance explicitly reported ("zero quality variance across all trials"). It is
therefore the strongest precedent for the *design*. It fails on domain — IT incident
response — and on benchmark provenance and outcome: the measured quantity is a bespoke
Decision Quality score over author-written scenarios, not decision agreement across
repeats on an external case set. It should be cited as prior art for the *method* while
the compliance-domain and external-benchmark distinctions are drawn.

### 5.5 arXiv:2607.17044 — Dastidar, *Where Does Agent Reliability Come From?* — fails (a) and (b)

Read in full because it is the closest *title*. Despite "reliability" and
"decomposition" in the framing, both words mean something else: "decomposition" is a
post-hoc attribution of an **accuracy uplift** to scaffolding, routing, specialist
models and verification loops; "reliability" is modelled as compounding pass rates.
It reports pass@1 and best-of-k on SpreadsheetBench Verified, BullshitBench v2 and
GAIA — never re-running a fixed input to measure output agreement. Ablations swap
verifier identity, not agent count. It does not threaten the claim on any criterion
except (d).

---

## 6. Verdict

### The claim as written does not survive intact. It survives after narrowing.

**No displacing paper exists.** Zero of 31 fully assessed works satisfy (a)∧(b)∧(c)∧(d).
The gap is real, and it is confirmed rather than merely unrefuted: 2605.23955, a May
2026 survey of determinism in financial AI covering exactly this territory, identifies
no such study; and 2509.08380, the flagship agentic-decomposition-for-AML paper,
reports no repeatability measurement at all.

**But "First measurement of decision repeatability as a function of agentic
decomposition" is now overclaimed**, because arXiv:2608.11344 (11 Aug 2026) varied
agentic architecture from one to fifty agents on fixed financial cases including AML
review and reported reproducibility outcomes. It got to the *phenomenon* first, three
days before this search. It did not get to the *measurement* — no per-architecture
decision-agreement rate, no external cases — but a hostile examiner reading only the
two abstracts will see "architecture changes final actions, and no execution record
repeated in any configuration" and ask why that is not the same finding.

### Proposed wording that IS supported by what was found

> "First controlled measurement of **decision-level agreement across repeated runs**
> as a function of single-agent versus multi-agent decomposition in an AML
> compliance-triage workflow, holding model, tools, rulebook and sampling parameters
> fixed, and evaluated on an **externally authored** compliance-triage benchmark
> (DFAH, arXiv:2601.15322) using **externally defined** repeatability metrics
> (DAR/TAR from DFAH-Bench, arXiv:2607.20491; pass^k from τ-bench, arXiv:2406.12045)."

Three defensive additions are load-bearing and should not be dropped:

1. **"decision-level agreement across repeated runs"** rather than bare
   "repeatability" — this is the precise thing 2608.11344 does not report per
   architecture, and 2607.20491 does not report per architecture either.
2. **"holding model, tools, rulebook and sampling parameters fixed"** — this is the
   controlled-comparison element that separates the work from 2603.22651 and
   2608.11381, which vary decomposition but measure task score.
3. **"externally authored benchmark ... externally defined metrics"** — the single
   criterion that no near-neighbour satisfies, since every one of them evaluates on
   cases its own authors wrote.

A fallback formulation, if the supervisor prefers to avoid "first" entirely:

> "We provide the first quantified decomposition-effect estimate for decision
> repeatability in compliance triage: prior work has shown that agentic architecture
> perturbs financial-agent reproducibility (Han 2026) and has measured decision
> agreement under replay without varying architecture (Khatchadourian 2026a, 2026b);
> we cross the two, on cases and metrics we did not author."

### Adversarial cautions the student should pre-empt

- **The "externally authored" benchmark is a preprint by the same author who defines
  your primary metric.** DFAH's compliance-triage cases (2601.15322) and DFAH-Bench's
  DAR/TAR (2607.20491) are both Khatchadourian. It is genuinely external to *you*, and
  that is what the criterion requires — but it is a single, non-peer-reviewed source,
  and an examiner may press on whether "externally authored" implies community-adopted.
  Say plainly that it means "not authored by this work," and note that τ-bench
  (ICLR 2025, peer-reviewed) supplies pass^k as a second, independent, peer-reviewed
  metric anchor.
- **N = one decomposition contrast.** The design compares single-agent against one
  4-agent pipeline. 2608.11344 swept 1→50 agents. If asked "is this repeatability as a
  function of decomposition, or repeatability at two points?", the honest answer is two
  points — so prefer "decomposition-effect estimate" over language implying a dose-response
  curve.
- **The headline finding is a null-with-moderation** (direction and size depend on base
  model, not on decomposition itself). That is *consistent* with 2608.11344's
  "architecture changes final actions" and with 2604.02460's compute-confound result,
  and it should be presented as converging evidence rather than a contradicted result.
- **A follow-up from the Khatchadourian line is a live risk.** The author sweep confirms
  a three-paper cadence at roughly quarterly intervals (Nov 2025, Jan 2026, Jun 2026)
  with nothing since 24 Jul 2026. A fourth DFAH paper adding an architecture factor
  would displace this claim outright. Re-run query 5 before final submission.

---

## 7. Limitations of this search

1. **Google Scholar was not queried directly.** Scholar blocks automated access; its
   records were reached only where general web search surfaced them. Citation-graph
   forward search from the key near-neighbours was therefore not possible.
2. **Semantic Scholar's API was not queried directly** — only records that surfaced
   incidentally through web search. No S2 citation-chaining was performed on
   2601.15322, 2607.20491 or 2608.11344, which is the highest-value missing sweep.
3. **ACL Anthology's own search endpoint was not queried**; Anthology coverage came
   from domain-scoped web search and returned only three relevant records. NLP-venue
   coverage should be treated as thin. Given that this topic sits in cs.SE / cs.AI /
   q-fin rather than *ACL, the practical risk is low but non-zero.
4. **One PDF extraction failure**: `arxiv.org/pdf/2608.11344v2` returned unparseable
   binary content. Recovered via `arxiv.org/html/2608.11344v2`, but two Study-2 details
   could not be confirmed from the HTML rendering either — **the number of repetitions
   per case per configuration**, and **explicit provenance of the 32 cases**. The
   provenance conclusion (author-constructed) rests on the paper's own description of
   them as *"fixed, constructed financial cases"*. If a reviewer disputes this, the
   distinguishing argument falls back entirely on the absence of a per-architecture
   decision-agreement breakdown, which is independently verified.
5. **English-language only.** No search was run in Mandarin, Japanese, German or French.
   Regulatory-technology work published in national-language venues, and any bank or
   supervisor internal research, is invisible to this protocol.
6. **Preprint and venue lag.** Peer-reviewed work submitted but not yet published — and
   conference papers under embargo — cannot be seen. The 2608.11344 case demonstrates
   the exposure concretely: a paper posted six days after the previous scan materially
   changed the novelty position. **This search has a half-life of days, not months.**
7. **Grey literature was screened but not systematically searched.** Vendor and
   practitioner material (Unit21, Kriv AI, Snyk, consultancy whitepapers) discusses AML
   agent repeatability qualitatively. None found constitutes a controlled study, but
   commercial evaluations are unlikely to be published at all, so a "first measurement"
   claim is safest phrased as first *published, reproducible* measurement.
8. **Screening was abstract-and-methods level for 28 of 31 assessed works.** Only three
   received full-text reads. A repeatability sub-analysis buried in an appendix of a
   paper whose abstract does not mention it would have been missed.

---

*Search executed 2026-08-14. Re-run queries 1–6 (arXiv API), and in particular query 5
(`au:"Khatchadourian"`) and a fresh listing check on cs.MA / cs.SE / q-fin, within 72
hours of final submission.*
