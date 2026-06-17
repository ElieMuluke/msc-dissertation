"""Run the RAG Triad evaluation (LLM-judge) and log to local MLflow.

    python -m app.evaluation.triad_run --k 3
    mlflow ui --backend-store-uri sqlite:///mlflow.db   # experiment: rag-triad

Requires Ollama running (used both to generate answers and to judge them). The corpus is
ingested into a throwaway store, so the live database is never touched.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import mlflow

from app.evaluation.triad import TriadRecord, evaluate_triad, make_llm_judge
from app.generation import GenerationConfig, build_answer_generator, build_completion
from app.ingestion.rag import Document, DocumentType, RagConfig, build_rag

_BACKEND = Path(__file__).resolve().parents[2]
_DATASETS = Path(__file__).resolve().parent / "datasets"


def _load_corpus(path: Path) -> list[Document]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [Document(r["id"], r["text"], DocumentType(r["doc_type"]), r.get("metadata", {})) for r in rows]


def _load_questions(path: Path) -> list[str]:
    return [json.loads(line)["question"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG generation with the LLM-judge triad.")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--corpus", type=Path, default=_DATASETS / "triad_corpus.json")
    parser.add_argument("--questions", type=Path, default=_DATASETS / "triad_questions.jsonl")
    parser.add_argument("--experiment", default="rag-triad")
    args = parser.parse_args(argv)

    corpus = _load_corpus(args.corpus)
    questions = _load_questions(args.questions)
    config = GenerationConfig()

    with tempfile.TemporaryDirectory() as tmp_dir:
        rag = build_rag(RagConfig(persist_dir=tmp_dir, collection_name="triad_eval"))
        rag.ingest(corpus)
        generator = build_answer_generator(rag, config)
        records = []
        for question in questions:
            answer = generator.generate(question, k=args.k)
            records.append(TriadRecord(question, answer.answer, answer.contexts))
        scores = evaluate_triad(records, make_llm_judge(build_completion(config)))

    mlflow.set_tracking_uri(f"sqlite:///{_BACKEND / 'mlflow.db'}")
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run():
        mlflow.log_params({"k": args.k, "n_questions": len(questions), "judge_model": config.model})
        mlflow.log_metrics(scores)

    print(f"RAG Triad over {len(questions)} questions (k={args.k}):")
    for name, value in scores.items():
        print(f"  {name}: {value:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
