# Dissertation Project

Multi-Agent Systems for Regulatory Risk and Compliance for Banking Workflows.

The codebase is split into a **backend** (FastAPI over the RAG/ingestion code) and a
**frontend** (React + Vite + TS) for interacting with the platform.

```
backend/    FastAPI API + RAG/ingestion code   (see backend/README.md)
frontend/   React + Vite + TS UI               (see frontend/README.md)
docs/       Feature docs                        (see docs/rag.md)
```

## Quickstart

```bash
# Backend
cd backend && uv pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000  (docs at /docs)

# Frontend (new terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Features

- **AML RAG system** — ingest AML policies and financial actions, then search them
  semantically (LangChain + Chroma + sentence-transformers). PDF ingestion supported.
  See [docs/rag.md](docs/rag.md).
- **REST API** — upload documents and search via FastAPI. See [backend/README.md](backend/README.md).
- **Web UI** — import documents and search. See [frontend/README.md](frontend/README.md).
