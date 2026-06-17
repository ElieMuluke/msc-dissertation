# Backend — AML Compliance Platform API

FastAPI layer over the ingestion/RAG code in `app/ingestion`.

## Run

```bash
# from this backend/ directory
uv pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000  (docs at /docs)
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check. |
| POST | `/rag/documents/pdf` | Upload one or more PDFs (`files`, `doc_type=policy\|action`); ingests one doc per page. |
| GET | `/rag/search?q=&k=&doc_type=` | Semantic search; returns scored hits. |
| POST | `/rag/answer` | Grounded answer + citations from a local LLM (`{query, k, doc_type}`). Needs Ollama. |
| GET | `/rag/documents` | List ingested source files (filename, doc_type, pages, ingested_at). |
| DELETE | `/rag/documents` | Clear the entire corpus (resets the collection). |
| DELETE | `/rag/documents/{filename}` | Delete all documents from one source file. |
| WS | `/ws` | Realtime ingestion progress frames (`event: ingestion_progress`). |

## Layout

```
app/
  main.py            # FastAPI app + CORS + routers
  deps.py            # shared RagSystem (built once)
  api/
    routes/rag.py    # endpoints
    schemas.py       # Pydantic request/response models
  ingestion/rag/     # RAG feature (see ../docs/rag.md)
  generation/        # augmented generation via Ollama (see ../docs/generation.md)
  evaluation/        # retrieval eval + MLflow (see ../docs/evaluation.md)
tests/               # python -m pytest
```

## Tests

```bash
python -m pytest
```

## CLI (still available)

```bash
python -m app.ingestion.rag.cli ingest-pdf data/aml_policies/ --type policy
python -m app.ingestion.rag.cli search "enhanced due diligence" --type policy
```
