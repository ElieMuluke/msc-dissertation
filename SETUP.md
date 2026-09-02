# Setup

Everything below is run from a clone of this repository.

## Prerequisites

| Tool | Version | Needed for | Check |
|---|---|---|---|
| Python | 3.14 or newer | Backend, experiment harness | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) | any recent | Python venv + dependencies | `uv --version` |
| [Ollama](https://ollama.com/) | any recent | Answer generation, RAGAS eval, sweeps | `ollama --version` |
| Node.js | 18 or newer | Frontend (Vite 5) | `node --version` |
| Yarn | any recent | Frontend (`frontend/yarn.lock`) | `yarn --version` |

The experiment harness additionally needs a clone of the DFAH benchmark, which
supplies the case fixtures and ground-truth labels. See
[Experiment harness](#experiment-harness) below.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc            # or restart the shell; uv lands in ~/.local/bin
```

### Install Ollama and pull the models

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                          # http://localhost:11434
ollama pull llama3.2:3b qwen2.5:3b      # generator + RAGAS judge defaults
```

## Backend

```bash
cd backend
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn app.main:app --reload           # http://localhost:8000, docs at /docs
```

Configuration is read from the environment, so there is nothing to copy. Every
variable has a working default; set only what you want to change.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.2:3b` | Generator model |
| `OLLAMA_NUM_PREDICT` | `2048` | Generation token budget |
| `OLLAMA_REASONING` | off | Send `think=true` to the generator |
| `RAGAS_JUDGE_MODEL` | `qwen2.5:3b` | RAGAS judge (a different family, to avoid self-evaluation bias) |
| `RAG_COLLECTION_NAME` | see `app/ingestion/rag/config.py` | Chroma collection |
| `RAG_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedder |
| `RAG_PERSIST_DIR` | `chroma_db/` | Chroma store location |
| `RAG_CHUNKER` / `RAG_PARENT_CONTEXT` | section-aware, on | Chunking strategy |
| `SCOPE_GATE_THRESHOLD` | per-embedder (`0.638` for bge-small) | Refusal gate cut-off |
| `ANALYSIS_MODEL` / `ANALYSIS_OLLAMA_URL` / `ANALYSIS_TEMPERATURE` / `ANALYSIS_PIPELINE` | see `app/` | Compliance analysis pipeline |

### Tests

```bash
cd backend
python -m pytest            # 306 passed, 1 skipped
```

## Frontend

```bash
cd frontend
yarn install
yarn dev                    # http://localhost:5173
```

The backend must be running; CORS allows `http://localhost:5173`. Point the UI
at a different backend with `VITE_API_URL`.

## Experiment harness

The repeatability sweeps (PRD-A) need the DFAH benchmark clone for case
fixtures and ground-truth labels. Clone it, then point `DFAH_REPO` in
`backend/experiments/config.py` at it. The path is not part of the hashed
experiment configuration, so changing it does not invalidate any sealed sweep.

Regenerating the dissertation figures from the sealed journals needs only the
labels, and takes the path from `--alerts` or `$DFAH_ALERTS` without editing
config:

```bash
cd backend
python -m experiments.analysis.figures --out ../docs/final-figs
```

See [docs/figures.md](docs/figures.md) for the figures and
[docs/PRD-A-experiment.md](docs/PRD-A-experiment.md) for the locked design.
