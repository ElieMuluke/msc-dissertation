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
| POST | `/rag/documents/pdf` | Upload one or more PDFs (`files`); ingests one doc per page. Streams progress as SSE (`text/event-stream`), not a single JSON response. |
| GET | `/rag/search?q=&k=` | Semantic search; returns scored hits. |
| POST | `/rag/answer` | Grounded answer + citations from a local LLM (`{query, k}`). Needs Ollama. |
| POST | `/rag/answer/stream` | Same as above, streamed token-by-token as SSE. |
| GET | `/rag/documents` | List ingested source files (filename, pages, ingested_at). |
| DELETE | `/rag/documents` | Clear the entire corpus (resets the collection). |
| DELETE | `/rag/documents/{filename}` | Delete all documents from one source file. |
| POST | `/tabular/ingest` | Upload HI-Large accounts/transactions/patterns CSV/TXT (`data_type`, `files`) into SQLite. Streams byte-based progress as SSE. |
| POST | `/tabular/ingest/local` | Ingest a file already on the server's disk by path (`data_type`, `path`) — no upload; for very large files. Streams progress as SSE. |
| POST | `/tabular/ingest/text` | Ingest pasted/typed CSV or TXT text (`data_type`, `csv_text`); fully validated before any DB write — `422` with a list of every error and no partial insert if malformed. |
| GET | `/tabular/counts` | Ingested row counts (`{accounts, transactions}`). |
| DELETE | `/tabular/data` | Clear all ingested tabular data (accounts + transactions). |

## Layout

```
app/
  main.py            # FastAPI app + CORS + routers
  deps.py            # shared RagSystem (built once)
  api/
    routes/rag.py    # endpoints
    schemas.py       # Pydantic request/response models
  ingestion/rag/     # RAG feature (see ../docs/rag.md)
  ingestion/tabular/ # HI-Large AML tabular ingestion into SQLite (see ../docs/tabular.md)
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
python -m app.ingestion.rag.cli ingest-pdf data/aml_policies/
python -m app.ingestion.rag.cli search "enhanced due diligence"
```
