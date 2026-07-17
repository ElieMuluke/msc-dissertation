# Evaluation Pipeline

Assesses RAG performance and accuracy, with results visualized in MLflow. Lives in
`backend/app/evaluation/`. Designed to grow: every new feature gets its own evaluation
here. Metrics are computed in-repo (transparent, dissertation-defensible) and logged to a
**local** MLflow store (regulatory data never leaves the machine).

## Scope

The RAG system is currently **retrieval-only**, so evaluation covers retrieval quality:

| Metric | Meaning |
| --- | --- |
| `precision@k` | Fraction of the top-k that are relevant. |
| `recall@k` | Fraction of relevant docs found in the top-k. |
| `mrr` | Mean reciprocal rank of the first relevant doc. |
| `ndcg@k` | Rank-weighted relevance (binary). |
| `hit_rate@k` | Share of queries with ≥1 relevant doc in top-k. |

Generation quality is covered by **RAGAS** (below), now that an LLM answer step exists.

## Dataset

A labeled retrieval set: JSONL, one object per line —
`{"query": "...", "relevant_ids": ["id", ...]}`. Default:
`backend/app/evaluation/datasets/retrieval.jsonl` (queries against `data/aml_sample.json`).
Add rows as the corpus grows; keep ids in sync with ingested document ids.

## Run

```bash
# from backend/
python -m app.evaluation.run --k 5
mlflow ui --backend-store-uri sqlite:///mlflow.db    # dashboard at http://localhost:5000
```

Each run logs params (`k`, `n_queries`, `embedding_model`) and the metrics above to a local
SQLite MLflow store (`backend/mlflow.db`), so runs are comparable over time. Evaluation
ingests the corpus into a throwaway store — it never touches the live database.

## RAGAS (generation quality)

LLM-as-judge evaluation of generated answers via the [`ragas`](https://docs.ragas.io)
library (v0.2.x) rather than hand-rolled metrics. Answers are generated against the **real
ingested corpus** (the persisted Chroma store built from the JMLSG/FATF/sanctions PDFs), so
the evaluation exercises the actual retriever — not a throwaway toy store.

### Core-4 metrics

Scored in `[0, 1]` over the golden set, using each row's ground-truth answer as the RAGAS
`reference`:

| Metric | Question |
| --- | --- |
| `faithfulness` | Is the answer supported by the retrieved context (no hallucination)? |
| `answer_relevancy` | Does the answer address the original question? |
| `context_precision` | Are the retrieved contexts relevant, ranked against the reference? |
| `context_recall` | Do the retrieved contexts cover the reference answer? |

### Topic adherence (agentic scope control)

RAGAS `TopicAdherenceScore` measures whether the agent stays within the KYC/AML domain.
Precision, recall and F1 are all emitted per query (one `TopicAdherenceScore` instance per
mode, renamed `topic_adherence_{precision,recall,f1}`). Answers are classified against
`REFERENCE_TOPICS` (the AML domain scope, in `ragas_eval.py`). The dataset is **in-scope
golden questions only**.

Out-of-scope behavior is reported separately, split by which layer does the refusing (RAGAS's
precision formula scores a *correct refusal* as 0.0 — true positives = answered∧on-topic = 0,
false positives = 0 → 0/(0+1e-10) — so mixing out-of-scope queries into the topic-adherence
dataset pinned ~20% of the mean at 0 regardless of agent behavior):

- `retrieval_scope_confidence` / `gated_by_retrieval_confidence_rate` — the F25 out-of-scope
  gate (`RagSystem.scope_confidence`, raw top-1 vector relevance) short-circuits generation
  *before* any retrieval is surfaced or LLM call made, whenever confidence is below
  `SCOPE_GATE_THRESHOLD`. Detected here by the generator returning the exact fixed refusal
  string, so the two metrics are pure retrieval-layer signal.
- `generation_refusal_rate` — for queries the gate did *not* catch, the answer is judged with
  RAGAS's own `TopicRefusedPrompt` for whether the model declined anyway. NaN when the gate
  caught every out-of-scope query (nothing reaches generation to judge).
- `out_of_scope_refusal_rate` — combined figure (gate ∨ generation-refusal), kept for
  continuity with pre-gate runs; not a single layer's number.

### Metrics by layer

Every run prints/persists a **"Metrics by layer"** table (`build_layer_summary` in
`ragas_run.py`) grouping every metric above by which layer produced it and which question
population it was scored over:

| Layer | 57 golden (core-4) | 51 in-scope (topic adherence) | 13 out-of-scope |
| --- | --- | --- | --- |
| Retrieval | `context_precision`, `context_recall` | — | `retrieval_scope_confidence`, `gated_by_retrieval_confidence_rate` |
| Generation | `faithfulness`, `answer_relevancy` | `topic_adherence_{precision,recall,f1}` | `generation_refusal_rate` |
| Combined | — | — | `out_of_scope_refusal_rate` |

**Chunking is not a fourth layer** — RAGAS has no standalone chunk-quality metric. Chunking
is a retrieval *design variable*, only observable as a shift in the retrieval-layer numbers
when comparing collections (`--collection`/`--bm25-weight` A/B runs, all logged to MLflow
experiment `rag-ragas`) — see the retrieval-config comparison table maintained alongside the
dissertation write-up.

### Golden dataset

- `datasets/golden_set_v1.jsonl` — versioned, hand-verified `{id, category, question,
  ground_truth, reference_context, source}` triples grounded in the real corpus. Categories:
  `clear`, `ambiguous`, and `no_answer` (questions with no supporting answer in the corpus,
  to test context-recall failure honestly). 57 rows (≥50 for stable metrics per RAGAS
  guidance).
- `datasets/out_of_scope_v1.jsonl` — off-topic queries with `expected_outcome:
  refuse_or_deflect`, used only for the out-of-scope refusal rate.

The runner populates `retrieved_contexts` **live** from the real retriever each run — they
are not hardcoded in the dataset.

### Judge model (independence + reproducibility)

The RAGAS judge is a **different model family** than the answer generator to avoid
self-evaluation bias: `RAGAS_JUDGE_MODEL` (default `qwen2.5:3b`) vs the generator
(`OLLAMA_MODEL`). The judge model and temperature are logged to MLflow so results are
reproducible. The judge runs with Ollama's `format="json"` (grammar-constrained decoding):
every RAGAS judge prompt expects structured JSON, and small local judges otherwise emit
invalid escape sequences that fail parsing and NaN the sample.

context_recall's judge instruction is hardened (`_BINARY_JUDGE_SUFFIX` in
`ragas_eval.default_metrics`): attribute on **meaning** (not exact wording) and answer
strictly 0/1, never 0.5. A 2026-07-07 diagnosis of all fractional verdicts found they came
from exact-phrase literalism and "partially attributed" hedging; on the previously-failing
cases the hardened prompt cut fractional emissions 12 → 1 and corrected the
literalism-driven hedges to correct binary verdicts.

Judge completions are additionally passed through a repair layer (`_repair_judge_json`)
before RAGAS parses them: invalid/double-encoded JSON is fixed via `json-repair`, and
fractional binary verdicts (e.g. `"attributed": 0.5`, which RAGAS's `int` schema rejects)
are coerced with a **conservative rounding policy — 0.5 rounds down to 0**: an unsure
judge gives no credit, so faithfulness/context_recall are biased down, never up. This also
keeps RAGAS's own `FixOutputFormat` retry from engaging (it is incompatible with a
JSON-constrained judge and mangles output further). Unrepairable text passes through
unchanged into the normal NaN accounting.

### Output integrity

- Results come from RAGAS's public `to_pandas()` API (no private attributes).
- Per-query scores are persisted to `backend/eval_results/*.csv` and `*.json` (and logged as
  MLflow artifacts), so individual failure cases can be inspected — not just aggregate means.
- Each run also emits a detailed markdown diagnostic report,
  `eval_results/report_<run_tag>.md` (built by `build_report` in `ragas_run.py`, also
  printed and logged as an MLflow artifact): per-metric score **distributions**
  (min/p25/median/p75/max over valid samples), **per-category means** (clear / ambiguous /
  no_answer golden-set categories), the **worst-5 queries per metric**, and the list of
  **non-refused** out-of-scope queries.
- NaN scores (malformed input / judge parse failures) are counted per metric, excluded from
  the mean, warned about in logs, and logged to MLflow as `*_nan` — never silently averaged.
- The topic-adherence classification prompt is corrected: ragas's stock
  `TopicClassificationPrompt` ships a self-contradictory few-shot example ("General Theory
  of Relativity" classified as *not* falling under "Physics"), which our judge mirrored —
  near-uniform off-topic verdicts on single topics, coin-flip accuracy in batches. The
  metrics now carry a replacement instruction (classify by **meaning** against *any*
  reference topic) with coherent single-topic examples.
- The topic-adherence metrics are shape-safe: RAGAS's stock implementation classifies all
  N extracted topics against the reference topics in one judge call, and small judges
  return the wrong count (one verdict per *reference* topic, or off by one), crashing the
  confusion-matrix math. Our metrics classify **one topic per judge call** (same prompts,
  same scoring math), so a count mismatch is structurally impossible; the remaining
  unjudgeable cases (no topics extracted — e.g. a greeting — or an empty classification)
  are scored NaN with a warning naming the question, and flow into the NaN accounting
  above.
- The runner prints the **active retrieval config** at startup — collection, persist dir,
  chunk count, detected chunking style (`section` vs `page-window`), `bm25_weight`, `k`,
  generator — and logs `n_chunks`/`chunk_style` to MLflow, so a run can never silently
  evaluate the wrong index. An empty collection aborts immediately.
- `TopicAdherenceScore` instances expose both `.name` and `.mode`, so they structurally match
  ragas's internal `ModeMetric` protocol; `ragas.evaluate()` then writes their result column as
  `"<name>(mode=<mode>)"` instead of the plain name we assigned. `run_ragas` renames those
  columns back before summarizing, so `topic_adherence_{precision,recall,f1}` are read (and
  persisted) under their plain names.

```bash
# from backend/ — needs Ollama running (generation + judge)
python -m app.evaluation.ragas_run --k 4
python -m app.evaluation.ragas_run --k 4 --limit 6    # quick bounded run
# evaluate a specific retrieval variant (chunking collection + hybrid weight):
python -m app.evaluation.ragas_run --k 4 --collection aml_sections_b --bm25-weight 0.3
```

The retrieval side under test is chosen entirely by flags — `--collection` picks the
chunking variant (`aml_corpus` = page-window baseline, `aml_sections_a` = section chunks,
`aml_sections_b` = section chunks + parent-context prefix, MiniLM; `aml_sections_c` = section
chunks + parent-context prefix, `bge-small-en-v1.5`) and `--bm25-weight` enables hybrid
BM25+vector fusion. **Defaults are the baseline** (`aml_corpus`, weight `0.0`): running with
no flags evaluates the unchanged pipeline, not the new chunking/hybrid work.

**Production config** (`backend/.env`, consumed by `app.deps`): `aml_sections_c` +
`bge-small-en-v1.5` + `bm25_weight=0.2`, adopted 2026-07-17 from a 24-run sweep across all
four collections x six bm25 weights (`0.0`–`1.0`). At that weight, `aml_sections_c` beat
every other collection/weight combination on `context_precision`/`context_recall` with no
faithfulness/answer_relevancy cost; `0.2` and `0.4` were statistically indistinguishable from
each other and both clearly ahead of pure-vector (`bm25_weight=0.0`). `SCOPE_GATE_THRESHOLD`
auto-resolves to `0.638` for this embedder (`resolve_scope_gate_threshold`) and was not
touched by this sweep. Each of `RAG_COLLECTION_NAME`/`RAG_EMBEDDING_MODEL`/`RAG_BM25_WEIGHT`
is independently env-overridable without a code change.

Logs to MLflow experiment **rag-ragas** (params: k, n_golden, n_out_of_scope,
generator_model, judge_model, judge_temperature, embedding_model, ragas_version). Design:
`ragas_eval.py` has pure conversion helpers (`to_evaluation_dataset`,
`to_topic_adherence_sample`, `topic_adherence_metrics`) plus `run_ragas` (llm/embeddings
injected → unit-tested with fakes); `ragas_run.py` is the thin shell that wires the real
retriever, local Ollama judge, persistence and MLflow logging.

> **Performance note:** metrics call a local CPU Ollama judge sequentially; a single
> generation is ~80s on a CPU-only box and each judged sample adds several judge calls, so a
> full 57-row run takes hours. Use `--limit` for quick checks; run the full set on a
> GPU/faster host or overnight.

## Live search monitoring

Separate from offline eval: every real `/rag/search` call is logged to MLflow in the
background (FastAPI `BackgroundTasks`, so it adds no response latency and never breaks a
search). Experiment **rag-search-monitoring** in the same `backend/mlflow.db`.

Per search it logs metrics `latency_ms`, `n_results`, `top_score`, `mean_score`, `k` and
tags `query`, `doc_type`. View alongside the offline runs:

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db    # from backend/
```

Two experiments appear: `rag-retrieval` (offline accuracy) and `rag-search-monitoring`
(live usage/latency). Logging is best-effort (`app/evaluation/monitoring.py`).

## Design

- `metrics.py` — pure IR metric functions over ranked id lists (model/store-independent).
- `dataset.py` — `QueryExample` + `load_queries`.
- `runner.py` — `evaluate(search_fn, queries, k)`; depends only on a `search_fn`, so it is
  unit-tested with a fake searcher (no model download).
- `run.py` — wires the real RagSystem in, logs to MLflow.

## Extending (per new feature)

1. Add a labeled dataset under `datasets/`.
2. Add metric functions to `metrics.py` (or plug a library like Ragas for generation).
3. Extend `runner.evaluate` / add a runner; log to MLflow with a new experiment name.
