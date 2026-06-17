"""Run the RAG retrieval evaluation and log results to local MLflow.

    python -m app.evaluation.run            # uses the sample corpus + dataset
    python -m app.evaluation.run --k 3
    mlflow ui                               # view runs at http://localhost:5000

The corpus is ingested into a throwaway store so evaluation never touches the live
database.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import mlflow

from app.evaluation.dataset import load_queries
from app.evaluation.runner import evaluate
from app.ingestion.rag import Document, DocumentType, RagConfig, build_rag

_BACKEND = Path(__file__).resolve().parents[2]
_DEFAULT_CORPUS = _BACKEND / "data" / "aml_sample.json"
_DEFAULT_QUERIES = Path(__file__).resolve().parent / "datasets" / "retrieval.jsonl"


def _load_corpus(path: Path) -> list[Document]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        Document(r["id"], r["text"], DocumentType(r["doc_type"]), r.get("metadata", {}))
        for r in rows
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval and log to MLflow.")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument("--queries", type=Path, default=_DEFAULT_QUERIES)
    parser.add_argument("--experiment", default="rag-retrieval")
    args = parser.parse_args(argv)

    corpus = _load_corpus(args.corpus)
    queries = load_queries(args.queries)

    with tempfile.TemporaryDirectory() as tmp_dir:
        rag = build_rag(RagConfig(persist_dir=tmp_dir, collection_name="rag_eval"))
        rag.ingest(corpus)
        metrics = evaluate(lambda q: [hit.id for hit in rag.search(q, k=args.k)], queries, k=args.k)

    # MLflow 3.x requires a DB backend; use a local SQLite file (view with
    # `mlflow ui --backend-store-uri sqlite:///mlflow.db` from backend/).
    mlflow.set_tracking_uri(f"sqlite:///{_BACKEND / 'mlflow.db'}")
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run():
        mlflow.log_params(
            {"k": args.k, "n_queries": len(queries), "embedding_model": RagConfig().embedding_model}
        )
        # MLflow metric keys disallow "@"; keep human-readable names in the printout.
        mlflow.log_metrics({name.replace("@", "_at_"): value for name, value in metrics.items()})

    print(f"Evaluated {len(queries)} queries (k={args.k}):")
    for name, value in metrics.items():
        print(f"  {name}: {value:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
