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

Generation metrics (faithfulness, answer-relevancy) come later, once an LLM answer step
exists — they plug into the same `evaluate` runner (e.g. via Ragas).

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
