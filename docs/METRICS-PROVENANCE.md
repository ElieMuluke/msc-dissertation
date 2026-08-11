# Metrics provenance table

Every metric used in the experiment: what it means, what it tells you, and where it
comes from in the literature. Sources marked **[spine]** are in the verified 30-entry
reference set (`dissertation-review-03-references.md`); sources marked **[classical]**
are the canonical primary citations for textbook methods (added here because the spine
covered agent-evaluation literature, not classical statistics). Peer-review tier
stated per entry. Derived metrics defined by this project are marked **[this work]**
with their motivating citation.

## Tier 1 — decision-level (winner criterion, pre-registered order)

| Metric | What it measures (plain) | How it is computed | Source & citation |
|---|---|---|---|
| **pass^k** | The probability that *all k* independent runs of the same case agree with the benchmark label — reliability, not one-shot accuracy. Punishes "sometimes right". | For a case with n repeats and c label-agreeing runs: C(c,k)/C(n,k); averaged over cases. Reported at k∈{1,5,15}. | τ-bench: Yao, Shinn, Razavi & Narasimhan, *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*, ICLR 2025 (peer-reviewed), arXiv:2406.12045 **[spine]** |
| **DAR** (Decision Agreement Rate) | How often two runs of the same case reach the same decision — raw repeatability, ignoring the label. | Fraction of agreeing run-pairs within a case's repeats; averaged over cases. (Convention: two malformed outputs count as agreeing — same outcome category.) | DFAH-Bench: Khatchadourian, *DFAH-Bench: Benchmarking Observable Agent Instability in Financial Decision-Making*, 2026, preprint, arXiv:2607.20491 **[spine]** |
| **Krippendorff's alpha** | Agreement *corrected for chance*: a system that always answers "investigate" gets high DAR but alpha near 0. The guard against mode collapse. | 1 − (observed disagreement / expected disagreement), nominal level, computed from the coincidence matrix over repeats-as-raters. | Krippendorff, *Estimating the reliability, systematic error and random error of interval data*, Educational and Psychological Measurement 30(1), 1970; canonical treatment: Krippendorff, *Content Analysis: An Introduction to Its Methodology*, 4th ed., SAGE 2019 **[classical]** |
| **Flip rate** | The share of cases where at least one re-run produced a different verdict — the number a regulator quotes. | Cases with >1 distinct decision across repeats ÷ total cases. | **[this work]** — direct simplification of DAR for interpretability; same data, cites DFAH-Bench (arXiv:2607.20491) as the parent construct **[spine]** |

## Tier 2 — explanatory

| Metric | What it measures (plain) | How it is computed | Source & citation |
|---|---|---|---|
| **Majority-vote accuracy** | If you ran the agent k times and took the most common answer, would it agree with the label? Separates "noise around the right answer" from "genuinely wandering". | Modal decision per case vs label (ties broken by first-observed decision — documented convention). | Self-consistency: Wang et al., *Self-Consistency Improves Chain of Thought Reasoning in Language Models*, ICLR 2023 (peer-reviewed), arXiv:2203.11171 **[spine]** |
| **Normalised decision entropy** | How spread out the decisions are per case: 0 = always the same answer, 1 = maximally scattered. | Shannon entropy of the per-case decision distribution ÷ log₂(4) (4 outcome categories incl. malformed). | Entropy: Shannon, *A Mathematical Theory of Communication*, Bell System Technical Journal 27, 1948 **[classical]**; normalised-decision-entropy form as used for agent decisions: Khatchadourian, arXiv:2601.15322 §6.2, ICLR 2026 FinAI workshop **[spine]** |
| **TAR** (Trajectory Agreement Rate) | Did the agent take the *same tool-call path*, not just reach the same answer? Same-answer-different-path is hidden instability. | Fraction of run-pairs whose ordered tool-call name sequences are exactly equal. | DFAH-Bench, arXiv:2607.20491 **[spine]** |
| **Jaccard similarity** (tool sets) | Overlap of *which* tools two runs used, ignoring order. | \|A∩B\| / \|A∪B\| over tool-name sets, mean over run-pairs. | Origin: Jaccard, *The distribution of the flora in the alpine zone*, New Phytologist 11(2), 1912 **[classical]**; application to agent traces: MAESTRO, Ma et al., 2026, preprint, arXiv:2601.00481 (adaptation from interaction-edge sets to tool sequences stated, per review) **[spine]** |
| **Normalised LCS** | How much of the tool-call *order* two runs share. | Longest common subsequence of the two ordered tool-name sequences ÷ length of the longer; mean over run-pairs. | LCS algorithmics: Wagner & Fischer, *The String-to-String Correction Problem*, Journal of the ACM 21(1), 1974 **[classical]**; trace application: MAESTRO, arXiv:2601.00481 **[spine]** |
| **Malformed rate** | How often the agent failed to produce a parseable decision — an outcome, never an exclusion. | Malformed runs ÷ total runs (per arm × condition). | **[this work]** — pre-registered handling rule (PRD-A); motivated by structured-output nondeterminism evidence (ollama#12559) **[spine]** |

## Tier 3 — cost and inference

| Metric | What it measures (plain) | How it is computed | Source & citation |
|---|---|---|---|
| **Tokens per run** | The compute price of one decision, per arm — the honest answer to "MAS gains are just more compute". | Mean(prompt + completion tokens) per run, per arm × condition. | **[this work]**, answering the equal-token-budget critique: *Single-Agent LLMs Outperform Multi-Agent Systems… Under Equal Thinking Token Budgets*, 2026, preprint, arXiv:2604.02460 **[spine]** |
| **Tokens ÷ pass^k** | Cost per *reliable* decision — an unstable cheap system can be dearer than a stable expensive one. | tokens_per_run ÷ pass^k, reported at k∈{1,5,15} (all k pre-registered before results). | **[this work]** — composition of τ-bench's pass^k with per-arm cost accounting **[spine]** |
| **Wall-clock per run** | Latency per decision. Indicative only (shared-GPU contention windows are timestamped in the journal). | Mean seconds per run. | **[this work]**, standard operational measure |
| **Bootstrap 95% CI** | The uncertainty band around each arm-difference, resampling *cases* (the natural sampling unit). | Percentile bootstrap over cases, paired per-case differences, ≥10k resamples. | Efron, *Bootstrap Methods: Another Look at the Jackknife*, Annals of Statistics 7(1), 1979 **[classical]** |
| **Paired permutation test** | Whether the arm difference could plausibly be zero — nonparametric, no distributional assumptions. | Sign-flip permutation of per-case paired differences; two-sided p. | Fisher, *The Design of Experiments*, Oliver & Boyd, 1935 (origin of randomisation inference) **[classical]**; agent-consistency framing: Raj et al., *Consistency as a Testable Property*, 2026, preprint, arXiv:2605.10516 **[spine]** |

## Appendix tier

| Metric | What it measures (plain) | How it is computed | Source & citation |
|---|---|---|---|
| **ROUGE-L F1 (pairwise)** | How similar the *full text* of the answers is across repeats — surface wording stability, distinct from decision/trajectory stability. | Token-level LCS-based F1 between each pair of raw outputs, averaged (lowercase, whitespace tokens). BLEU rejected: reference-oriented, needs a designated reference; pairwise ROUGE-L is symmetric. | Lin, *ROUGE: A Package for Automatic Evaluation of Summaries*, Text Summarization Branches Out (ACL 2004 workshop) **[classical]**; pre-registered as appendix-tier before any results (CHANGELOG 2026-08-06) |
| **G-Pass@k** | Capability–stability interpolation (finer-grained than pass^k). Cited, not computed (appendix-optional per PRD-A). | — | Liu et al., *Are Your LLMs Capable of Stable Reasoning?*, ACL 2025 Findings (peer-reviewed), arXiv:2412.13147 **[spine]** |

---

*Conventions applied throughout (documented in each analysis report): malformed is an
outcome category included in every metric; malformed==malformed pairs agree in
DAR/alpha/entropy; majority ties break by first-observed decision; the canonical
trajectory is the ordered list of external tool-call names only (comparable across
arms). Winner criterion: Tier-1 order (pass^k primary, DAR next, alpha beside it),
pre-registered in PRD-A before run 1.*
