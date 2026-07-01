# Dissertation Project

Multi-Agent Systems for Regulatory Risk and Compliance for Banking Workflows.

The codebase is split into a **backend** (FastAPI over the RAG/ingestion code) and a
**frontend** (React + Vite + TS) for interacting with the platform.

```
backend/    FastAPI API + RAG/ingestion code   (see backend/README.md)
frontend/   React + Vite + TS UI               (see frontend/README.md)
docs/       Feature docs                        (see docs/rag.md)
```

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) (Python package/venv manager):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quickstart

```bash
# Backend
cd backend
uv venv .venv                 # create virtual environment
source .venv/bin/activate     # activate it
uv pip install -r requirements.txt
cp .env.example .env          # config (models, Ollama URL); edit as needed
uvicorn app.main:app --reload          # http://localhost:8000  (docs at /docs)

# Frontend (new terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Evaluation

Two independent evals for two different layers. They do **not** call each other — run
whichever you need (or both). Run from `backend/` (venv activated); both log to a local
SQLite MLflow store (`backend/mlflow.db`).

| | `app.evaluation.run` | `app.evaluation.ragas_run` |
|---|---|---|
| **Layer** | Retrieval only | Full RAG generation (retrieve → answer → judge) |
| **Asks** | Does vector search return the right doc? | Is the generated answer faithful, relevant, on-topic? |
| **Corpus** | Synthetic `aml_sample.json` (toy, throwaway store) | Real `chroma_db` from `corpus_pdfs/` + `golden_set_v1.jsonl` |
| **Metrics** | recall@k / precision@k | RAGAS Core-4 (faithfulness, answer relevancy, context precision/recall) + topic adherence |
| **LLM** | None | Ollama generator + judge (LLM-scored) |
| **Speed** | Seconds | Minutes (slow on CPU) |
| **MLflow experiment** | `rag-retrieval` | `rag-ragas` |

```bash
# Retrieval eval — fast, no Ollama
python -m app.evaluation.run --k 5

# RAGAS generation eval — requires Ollama running; slow on CPU
python -m app.evaluation.ragas_run --k 4 --limit 2 --skip-topic   # quick smoke test
python -m app.evaluation.ragas_run --k 4                          # full run

# View results
mlflow ui --backend-store-uri sqlite:///mlflow.db    # http://localhost:5000
```

The two `ragas_run` lines are the same program: `--limit 6` just caps questions per set for
a faster bounded run.

RAGAS uses local Ollama models. Defaults: generator `llama3.2:3b`, judge `qwen2.5:3b`
(different families → no self-evaluation bias). Pull them first (`ollama pull llama3.2:3b
qwen2.5:3b`) and override via `backend/.env` (`OLLAMA_MODEL` / `RAGAS_JUDGE_MODEL`) — no
code edits needed. Per-query results land in `backend/eval_results/` (timestamped per run).

## Features

- **AML RAG system** — ingest AML policies and financial actions, then search them
  semantically (LangChain + Chroma + sentence-transformers). PDF ingestion supported.
  See [docs/rag.md](docs/rag.md).
- **REST API** — upload documents and search via FastAPI. See [backend/README.md](backend/README.md).
- **Web UI** — import documents and search. See [frontend/README.md](frontend/README.md).
