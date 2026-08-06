# Owner review checklist — before Thursday launch

Compiled 2026-08-06 after: conformance review, adversarial verification (both passed, nothing sweep-invalidating), LangGraph port + re-review (passed, byte-equivalence to be re-evidenced at Thursday gates), and goals audit (all chains SOLID; one evidence gap = item 2).

## A. Launch-blocking — must be done before Thursday evening

1. **Review the 10 perturbation cases** — `backend/experiments/perturbation_cases.json`. Check each `ground_truth` and `edit` field; correct anything; set `meta.owner_reviewed: true`. PRD-A hard requirement. (~30 min)
2. **Approve the pre-registration commit.** The entire implementation (harness, agents, manifest, gate evidence, rulebook, watchlists, perturbation file) is uncommitted — the manifest's recorded git sha does not pin the code that will run, and "pre-registered" currently rests on local files. Review the working tree, then commit + push everything with a dated CHANGELOG note. (~5 min once reviewed)
3. **Machine free Thursday daytime** for the pinned-server gate run (I drive it): kill stale tmux/dev servers → `scripts/serve-armA.sh` / `serve-armB.sh` → G0 (n=10), G1 + recorded raw-output hashes (this becomes the port's determinism evidence), full G3 (5 cases × 3 repeats per arm, ≥13/15 extraction, both arms concurrently to measure contention + recompute sweep ETA), G4 re-drill → `launch-sweep.sh` Thursday evening.

## B. Confirm decisions (defaults applied; veto now or they stand)

4. **tokens ÷ pass^k reported at k ∈ {1, 5, 15}** (all three columns, no post-hoc choice) — replaces the k=15-only version that would likely render "—".
5. **Weekend demo rule:** any production/API use during the sweep must set `ANALYSIS_OLLAMA_URL=http://localhost:11436` (production default currently points at arm A's sweep server). Alternative: leave the API down all weekend.
6. **49 GB sqlite** (`backend/tabular_data_db.sqlite`): (a) back it up — it exists nowhere else and the viva demo depends on it; (b) checkpoint the 3.7 GB WAL; (c) decide composite `(account, timestamp)` indexes (hours-long build; only needed for demo speed, irrelevant to the experiment). None of this blocks Thursday.

## C. Content review — before the draft, ideally this week

7. **Rulebook** — `backend/data/rulebook.md`: 22 rules; 5 tagged `[citation unverified]` need your JMLSG/FATF check.
8. **FATF high-risk list** — `backend/data/watchlists/fatf_high_risk.json`: hand-authored from the June 2026 FATF statements (fatf-gafi.org blocks automated fetches); verify against the official page.
9. **G2 gate evidence footnote** — `results/gates/g2-report.json` self-reports "partial" from DFAH's replay protocol (decision-parse ineligibilities); the gate's stated criterion is met, but pre-empt it with one sentence in PILOT-NOTES so an examiner opening the file isn't surprised.

## D. Process items (from the original plan, still yours)

10. **Ethics pro-forma** — secondary synthetic data, no human participants; must be on file.
11. **Pre-registration memo to supervisor** — one page: design table + run matrix + metric hierarchy, dated before launch. Doubles as scoop-proofing.
12. **Mobile push is disabled** in Claude Code /config — enable Remote Control push if you want phone alerts from these sessions.

## Post-experiment (not now)

- Tuesday: flip `ANALYSIS_PIPELINE` default to the experiment winner; record its Tier-1 numbers in the report footer.
- G-Pass@k appendix script (post-hoc from journal) if wanted.
- PDF export: install pandoc or soften PRD-B "PDF" wording; "one command starts backend+frontend" is currently two.
- HI-Large provenance record (dataset version + download date) for the already-loaded 49 GB store.
