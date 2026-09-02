# Dissertation Project

Multi-Agent Systems for Regulatory Risk and Compliance for Banking Workflows.

The codebase is split into a **backend** (FastAPI over the RAG/ingestion code) and a
**frontend** (React + Vite + TS) for interacting with the platform.

```
backend/                FastAPI API + RAG/ingestion code   (see backend/README.md)
backend/experiments/    Repeatability sweep harness + analysis (PRD-A)
frontend/               React + Vite + TS UI               (see frontend/README.md)
docs/                   Feature docs and analysis reports
```

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.14+ | Backend, experiment harness |
| [uv](https://docs.astral.sh/uv/) | recent | Python venv + dependencies |
| [Ollama](https://ollama.com/) | recent | Answer generation, RAGAS eval, sweeps |
| Node.js | 18+ | Frontend (Vite 5) |
| Yarn | recent | Frontend (`frontend/yarn.lock`) |

Full install steps, including the environment variables the backend reads, are
in [SETUP.md](SETUP.md).

## Quickstart

```bash
# Ollama (once)
ollama serve &
ollama pull llama3.2:3b qwen2.5:3b     # generator + RAGAS judge defaults

# Backend
cd backend
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000  (docs at /docs)

# Frontend (new terminal)
cd frontend && yarn install && yarn dev   # http://localhost:5173
```

Every backend setting has a working default and is read from the environment,
so there is no `.env` to copy. See [SETUP.md](SETUP.md) for the variables.

## Tests

```bash
cd backend && python -m pytest         # 306 passed, 1 skipped
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

## Repeatability experiment (dissertation)

`backend/experiments/` holds the PRD-A harness that produced the dissertation's
results: 18 sealed sweeps of 2,300 runs each, comparing a single compliance
agent against a four-agent pipeline on the DFAH compliance-triage benchmark.
The locked design is in [docs/PRD-A-experiment.md](docs/PRD-A-experiment.md).

Running a sweep needs a clone of the DFAH benchmark and two Ollama servers, one
per architecture. Run everything from `backend/` with the venv active.

```bash
python -m experiments.harness.gates g0        # capability + determinism gates
python -m experiments.harness.gates g1
python -m experiments.harness.manifest        # freeze the run matrix + seeds
python -m experiments.harness.runner --arm single   # one process per arm
python -m experiments.harness.runner --arm mas
```

The runner is checkpointed: it skips runs already journalled, so an interrupted
sweep resumes losslessly by re-running the same command.

Analysis reads the journals only and needs no Ollama:

```bash
python -m experiments.analysis.report                    # per-sweep report + figures
python -m experiments.analysis.compare --models <keys>   # cross-model table
python -m experiments.analysis.seal_checks <results_dir> # tool-liveness + degeneracy
python -m experiments.analysis.figures --out ../docs/final-figs   # Figures 5-13
```

See [docs/figures.md](docs/figures.md) for what each figure shows and which
sweep feeds it.

## Features

- **AML RAG system** — ingest AML policies and financial actions, then search them
  semantically (LangChain + Chroma + sentence-transformers). PDF ingestion supported.
  See [docs/rag.md](docs/rag.md).
- **REST API** — upload documents and search via FastAPI. See [backend/README.md](backend/README.md).
- **Web UI** — import documents and search. See [frontend/README.md](frontend/README.md).
- **Repeatability harness** — checkpointed repeated-run sweeps over both
  architectures, with pre-registered metrics and seal-time validity checks.
  See [docs/PRD-A-experiment.md](docs/PRD-A-experiment.md).

## Documentation

| Doc | Covers |
|---|---|
| [SETUP.md](SETUP.md) | Prerequisites, install, environment variables |
| [docs/rag.md](docs/rag.md) | Retrieval pipeline |
| [docs/generation.md](docs/generation.md) | Grounded answers and the refusal gate |
| [docs/evaluation.md](docs/evaluation.md) | Retrieval and RAGAS evaluation |
| [docs/tabular.md](docs/tabular.md) | HI-Large tabular ingestion |
| [docs/PRD-A-experiment.md](docs/PRD-A-experiment.md) | Locked experiment design |
| [docs/figures.md](docs/figures.md) | Regenerating the dissertation figures |
