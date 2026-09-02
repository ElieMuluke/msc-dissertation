# Backend — AML Compliance Platform API

FastAPI layer over the ingestion/RAG code in `app/ingestion`.

## Run

```bash
# from this backend/ directory
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000  (docs at /docs)
```

Needs Python 3.14+ and a running Ollama for the generation endpoints. Settings
come from the environment with working defaults; see [../SETUP.md](../SETUP.md).

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
experiments/
  config.py          # locked design constants + model registry
  harness/           # gates, manifest, checkpointed sweep runner, journals
  analysis/          # metrics, stats, reports, seal checks, figures
  results*/          # one sealed sweep per directory (journals + manifest)
  tests/             # harness + analysis tests
tests/               # app tests
```

## Tests

```bash
python -m pytest            # 306 passed, 1 skipped
```

## Experiment harness

`experiments/` is the PRD-A repeatability harness behind the dissertation
results. Sweeps need the DFAH benchmark clone (`experiments/config.py`,
`DFAH_REPO`) and one Ollama server per architecture; analysis reads the sealed
journals only and needs neither.

```bash
python -m experiments.harness.gates g0            # capability + determinism gates
python -m experiments.harness.manifest            # freeze run matrix + seeds
python -m experiments.harness.runner --arm single # one process per arm; resumable
python -m experiments.harness.runner --arm mas

python -m experiments.analysis.report                    # per-sweep report
python -m experiments.analysis.compare --models <keys>   # cross-model table
python -m experiments.analysis.seal_checks <results_dir> # validity checks
python -m experiments.analysis.figures --out ../docs/final-figs
```

See [../docs/PRD-A-experiment.md](../docs/PRD-A-experiment.md) for the locked
design and [../docs/figures.md](../docs/figures.md) for the figures.

## CLI (still available)

```bash
python -m app.ingestion.rag.cli ingest-pdf data/aml_policies/
python -m app.ingestion.rag.cli search "enhanced due diligence"
```
