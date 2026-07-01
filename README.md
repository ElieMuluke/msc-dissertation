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
uvicorn app.main:app --reload          # http://localhost:8000  (docs at /docs)

# Frontend (new terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Evaluation

Run from `backend/` (venv activated). Both log to a local SQLite MLflow store (`backend/mlflow.db`).

```bash
# Retrieval eval (sample corpus, throwaway store)
python -m app.evaluation.run --k 5

# RAGAS generation eval over the golden set (requires Ollama running)
python -m app.evaluation.ragas_run --k 4
python -m app.evaluation.ragas_run --k 4 --limit 6   # quick bounded run

# View results
mlflow ui --backend-store-uri sqlite:///mlflow.db    # http://localhost:5000
```

## Features

- **AML RAG system** — ingest AML policies and financial actions, then search them
  semantically (LangChain + Chroma + sentence-transformers). PDF ingestion supported.
  See [docs/rag.md](docs/rag.md).
- **REST API** — upload documents and search via FastAPI. See [backend/README.md](backend/README.md).
- **Web UI** — import documents and search. See [frontend/README.md](frontend/README.md).
